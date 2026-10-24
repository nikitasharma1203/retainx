# retainx

[![CI](https://github.com/nikitasharma1203/retainx/actions/workflows/ci.yml/badge.svg)](https://github.com/nikitasharma1203/retainx/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![dbt-postgres](https://img.shields.io/badge/dbt-postgres-orange.svg)](https://www.getdbt.com/)
[![MCP](https://img.shields.io/badge/MCP-FastMCP-green.svg)](https://modelcontextprotocol.io/)

Customer intelligence layer for a D2C-style retailer: churn, propensity, CLV, a customer health
score, behavioural personas, a product ranking that resists small samples, and a semantic layer an
AI agent can query without raw SQL access.

> Portfolio project on public data (UCI Online Retail II, CC BY 4.0). No live client, no A/B test.
> Problem statement and success metrics: [`docs/problem_statement.md`](docs/problem_statement.md).

## Status

| Piece | State |
|---|---|
| Raw load, cleaning, dbt models and tests | Done. 29/29 dbt checks pass on the real data |
| Churn, propensity, ranking, health score, personas | Done and evaluated on the real data. Results below |
| CLV | Ranks customers well. Its level follows the calendar, so it is used for ranking only |
| Demand baselines | Done. Product-week demand is very lumpy; totals are forecastable |
| Pricing (elasticity) | Run on the real data. The estimates cannot be told apart from a pricing-structure artifact, so the data does not identify elasticity. Reported as a limits case |
| Semantic layer and MCP tools | Built. Tested on synthetic data and over stdio. Not yet run on the real data |
| Agent evaluation | Harness built, answer key generated (20 of 20 reference answers found), roles created. The evaluation runs themselves are pending |
| Notebook | Written; its code runs on synthetic data. Outputs are not embedded until you run it on the real data |

## The problem

A retailer's orders say what happened, not who to act on. Three people feel it:

| Person | Pain |
|---|---|
| CRM manager | Campaigns go to everyone because nobody knows who will churn or buy |
| Merchandiser | The "top products" list is unreliable when it rewards products with few buyers |
| Growth lead | Answering a data question takes days, and raw tables are redundant and confusing |

## Data and cleaning

Source: Online Retail II, 1,067,371 invoice lines, 2009-12-01 to 2011-12-09, 5,942 customers.

| Issue | Rows | Decision |
|---|---|---|
| No customer ID | 243,007 (22.8%) | Excluded from customer models. These rows carry 13.3% of valid revenue (about £2.67M of £20.11M), so customer models cover about 87% of revenue |
| Cancellations (invoice starts with `C`) | 19,494 | Excluded, not netted against original orders |
| Quantity <= 0 | 22,950 | Excluded. About 3,450 are not cancellations, likely stock adjustments |
| Price <= 0 | 6,207 | Excluded |
| Non-product stock codes (POST, DOT, M, C2, D, S, BANK CHARGES ...) | 6,093 | Excluded. Rule: keep codes starting with five digits |
| Exact duplicate lines | 34,335 | Flagged in staging, dropped by default. 26,055 survive the other filters, worth £365,882 (about 2.1% of revenue with a customer ID). A toggle runs the pipeline without dedupe |
| Several descriptions per stock code | 1,232 codes | Latest description used |

Result after cleaning:

| Table | Rows |
|---|---|
| `fct_orders` (valid customer orders) | 36,594 |
| `dim_customer` | 5,852 |
| `dim_product` | 4,944 |
| `fct_product_customer` | 480,971 |
| `customer_rfm` (cutoff 2010-12-01) | 4,239 |

Every cleaning decision lives in one model, `int_valid_sales`, and is logged in
[`docs/data_quality_log.md`](docs/data_quality_log.md) and [`docs/decisions.md`](docs/decisions.md).

## Architecture

```mermaid
flowchart TD
    subgraph Ingestion["1. Data ingestion & quality"]
        FILE["UCI Online Retail II<br/>1.067M invoice lines"] --> PROFILE["Profile & quality audit"]
        FILE --> LOAD["Load raw data"]
        LOAD --> RAW[("PostgreSQL<br/>raw.online_retail")]
    end

    subgraph Transform["2. dbt transformations"]
        RAW --> STG["Staging<br/>typed fields + quality flags"]
        STG --> VALID["int_valid_sales<br/>single exclusion point"]
        VALID --> MARTS[("Analytics marts<br/>orders · customers · products · RFM")]
    end

    subgraph Intelligence["3. Cutoff-aware customer & product intelligence"]
        MARTS --> FEATURES["Leakage-safe features<br/>explicit historical cutoff"]
        FEATURES --> CHURN["Churn prediction<br/>rolling time backtests"]
        FEATURES --> PROP["Purchase propensity"]
        FEATURES --> CLV["Probabilistic CLV<br/>ranking use only"]
        MARTS --> HEALTH["Customer health score"]
        MARTS --> PERSONAS["Behavioural personas"]
        MARTS --> RANK["Wilson / Bayesian<br/>product ranking"]
        MARTS --> PRICING["Pricing & demand analysis<br/>observational limits documented"]
    end

    subgraph Agent["4. Governed analytics for AI agents"]
        MARTS --> SEM["Semantic definitions<br/>compiled metric queries"]
        SEM --> MCP["MCP server<br/>governed tools + read-only SQL baselines"]
        MCP --> EVAL["Agent evaluation harness<br/>20 questions · runs pending"]
    end
```

```
raw.online_retail  (untouched copy of the file)
      |
dbt staging        typed and renamed; cancellations, missing customers, duplicates only FLAGGED
      |
int_valid_sales    the single place rows are excluded
      |
dbt marts          fct_orders, dim_customer, dim_product, fct_product_customer, customer_rfm
      |
src/features.py    leakage-safe features; the cutoff date is always an explicit argument
      |
src/models         churn, propensity, CLV (BG/NBD or Pareto/NBD + Gamma-Gamma)
src/health.py      health score from a calibrated churn model, banded and validated
src/personas.py    behavioural K-Means segments + a prompt for persona cards
src/ranking.py     Wilson / Bayesian product ranking, judged as of each cutoff
src/pricing.py     exploratory elasticity and demand baselines
semantic/ + src/semantic.py   governed metric definitions, compiled to SQL
mcp_server         governed metric tools + read-only SQL baselines for the agent evaluation
```

## Results

All numbers are offline backtests on one dataset. Models are trained on one period and tested on the
next; a training label window never overlaps the test period, and the code raises an error if it does.

### Churn

**Definition.** Customers who ordered in the 180 days before a cutoff. Churned means no order in the next 90 days.

Rolling backtest, XGBoost, default settings (dedupe on):

| Train cutoff | Test cutoff | n_test | Base rate | AUC | Brier | Top-decile lift |
|---|---|---|---|---|---|---|
| 2010-06-01 | 2010-09-01 | 2,831 | 0.380 | 0.708 | 0.221 | 1.55 |
| 2010-09-01 | 2010-12-01 | 3,471 | 0.620 | 0.743 | 0.290 | 1.35 |
| 2010-12-01 | 2011-03-01 | 3,348 | 0.577 | 0.761 | 0.198 | 1.49 |
| 2011-03-01 | 2011-06-01 | 2,688 | 0.504 | 0.772 | 0.196 | 1.61 |
| 2011-06-01 | 2011-09-01 | 2,780 | 0.394 | 0.752 | 0.217 | 1.85 |

**Model comparison** (`python -m src.eval.experiments`), mean over the splits where each model could run:

| Model | AUC | Brier | Top-decile lift |
|---|---|---|---|
| Recency-only rule (no training) | 0.661 | n/a | 1.44 |
| Logistic regression | 0.755 | 0.218 | 1.61 |
| XGBoost, previous cutoff | 0.747 | 0.224 | 1.57 |
| XGBoost, pooled cutoffs + month features | 0.750 | 0.226 | 1.59 |
| XGBoost, pooled + recalibrated (isotonic) | 0.751 | 0.216 | 1.56 |
| Reference: always predict the previous cutoff's base rate | n/a | 0.259 | n/a |

The recalibrated model only runs on 4 of 5 splits (it needs two earlier cutoffs), so its row is not exactly comparable.

**Reading.**
- **The features carry real signal.** Every trained model beats the recency-only rule by about 0.09 AUC.
- **The complex model is not needed.** Logistic regression matches or beats XGBoost on average (AUC 0.755 vs 0.747, Brier 0.218 vs 0.224), so the health score uses logistic regression. Differences of this size are small, and it won 3 of 5 splits on AUC.
- **The base rate swings seasonally (0.38 to 0.62).** The Dec to Feb window is the worst: customers active before Christmas go quiet. Every model beats the "predict last period's rate" reference in every split, but only just in 2010-12 (XGBoost 0.290 vs 0.293; logistic 0.281). Pooling cutoffs with month features did not fix that; recalibration helped a little (0.268 in that split).
- **Dedupe does not matter.** Keeping duplicates gives AUC 0.741 vs 0.743 and Brier 0.239 vs 0.235 on the same split.
- **Lift is capped at 1 divided by the base rate**, so read it alongside the base rate.

### Propensity

Order in the next 30 days among all known customers. Single split, train 2010-06-01, test 2010-12-01: AUC 0.738, average precision 0.484, Brier 0.164, top-decile lift 3.04 at a 0.191 base rate.

| Train cutoff | Test cutoff | n_test | Base rate | AUC | Brier | Top-decile lift |
|---|---|---|---|---|---|---|
| 2010-06-01 | 2010-09-01 | 3,299 | 0.272 | 0.718 | 0.178 | 2.36 |
| 2010-09-01 | 2010-12-01 | 4,239 | 0.191 | 0.749 | 0.145 | 3.14 |
| 2010-12-01 | 2011-03-01 | 4,512 | 0.169 | 0.762 | 0.119 | 3.24 |
| 2011-03-01 | 2011-06-01 | 4,908 | 0.180 | 0.790 | 0.115 | 3.52 |
| 2011-06-01 | 2011-09-01 | 5,224 | 0.205 | 0.798 | 0.128 | 3.24 |

AUC rises over time as more purchase history accumulates. Not yet compared against baselines.

### CLV

BG/NBD was rejected: on daily data its parameters `a` and `b` collapsed to about 0, and on weekly data it did not converge. Pareto/NBD (daily) fitted and was used, with Gamma-Gamma for order value.

**Bias by calibration date** (90-day holdouts):

| Calibrated at | Customers | Actual purchase-days | Predicted | Predicted / actual | Correlation |
|---|---|---|---|---|---|
| 2010-06-01 | 2,684 | 2,820 | 3,043 | 1.08 | 0.75 |
| 2010-08-01 | 3,136 | 3,366 | 3,347 | 0.99 | 0.77 |
| 2010-10-01 | 3,538 | 4,218 | 3,590 | 0.85 | 0.74 |
| 2010-12-01 | 4,239 | 2,761 | 4,556 | 1.65 | 0.77 |
| 2011-02-01 | 4,387 | 2,689 | 4,059 | 1.51 | 0.78 |
| 2011-04-01 | 4,691 | 3,141 | 3,840 | 1.22 | 0.80 |
| 2011-06-01 | 4,908 | 3,144 | 3,743 | 1.19 | 0.82 |
| 2011-08-01 | 5,117 | 3,614 | 3,695 | 1.02 | 0.81 |

**Out-of-time correction test** (180-day windows; the previous window's actual / predicted factor is applied to the next window):

| Test window | Before | After one overall factor | After separate active and lapsed factors |
|---|---|---|---|
| 2010-12-01 | 1.62 | 1.69 | 1.71 |
| 2011-06-01 | 1.00 | 0.62 | 0.61 |

**Reading.**
- **Ranking is solid.** Correlation with actual purchases is 0.74 to 0.82 at every date.
- **The level follows the calendar.** The model under-predicts (0.85) when the holdout covers the pre-Christmas peak, over-predicts by 1.5 to 1.65 in the quiet months after it, and is back to about 1.0 by August.
- **The same months agree across the two years:** June 1.08 and 1.19, August 0.99 and 1.02. That supports the calendar explanation. It is not proof: there are only two years and the customer base grows.
- **A fixed correction from the previous window fails.** It does nothing for the bad window and breaks the good one.
- **A same-season correction** (divide by the ratio for the same month a year earlier) can be tested for only two months: June goes from 1.19 to 1.10, August from 1.02 to 1.03. Too few points to conclude; it needs three or more years.
- **Two earlier guesses were wrong.** The error does not grow with the horizon, and lapsed customers are not the cause (5.6% of predictions at the worst date).
- **Use:** rank customers; do not present £ CLV totals.

### Customer health score

100 x (1 - predicted churn probability) from a logistic regression, split into terciles (Green, Amber, Red) among active customers. Trained at 2011-03-01, scored at 2011-06-01, checked against what happened next: 2,688 active customers; 2,220 customers (45% of those with a past order) were lapsed and not scored.

| Band | Customers | Predicted churn | Observed churn |
|---|---|---|---|
| Green | 896 | 0.194 | 0.242 |
| Amber | 896 | 0.521 | 0.515 |
| Red | 896 | 0.774 | 0.754 |

**Reading.** Observed churn rises from Green to Red, and Red customers churn about 3.1 times as often as Green. Amber and Red are well calibrated; Green under-predicts by about 5 points. Longer tenure and more recent orders lower risk; a longer average gap between orders and longer recency raise it. The positive sign on 90-day revenue is probably collinearity with order count and spend, so individual coefficients should be read with care.

### Product ranking

Monthly cutoffs 2010-07-01 to 2011-09-01, top 20, repeat-purchase rate as the signal. "Repeat within 90 days" is out-of-sample: of buyers who had not yet repeated a product at the cutoff, the share who bought it again in the next 90 days.

| Method | Buyers behind the weakest top-20 product (avg) | New products in top 20 | Overlap with previous month | Buyers evaluated per month | Repeat within 90 days |
|---|---|---|---|---|---|
| Naive rate | 1 | 0 | 0.91 | 1,288 | 7.6% |
| Wilson lower bound | 69 | 0 | 0.87 | 4,504 | 12.0% |
| Bayesian shrinkage | 190 | 0 | 0.88 | 4,463 | 12.0% |
| All products (reference) | | | | | 5.2% |

**Reading.**
- **The "new product jumps to the top" failure did not occur** in this data. No method put a new product in the top 20.
- **The naive ranking is dominated by products with a single buyer.**
- **Evidence-aware ranking picks better products.** Buyers of the Wilson and Bayesian top 20 repeat at 2.3 times the all-product rate, against 1.5 times for the naive ranking.
- **Stability is not improved.** Month-to-month overlap is about the same for all methods.
- **Caveat:** the top 20 overlaps about 87% month to month, so the 15 months are not independent observations, and the naive result rests on fewer buyers.

### Personas

K-Means on log-scaled recency, frequency, spend, order value and tenure at 2011-12-01. Behaviour only; the data has no demographics.
Silhouette is 0.338 at k = 3 and 0.272 at k = 5, so the structure is moderate. k = 5 is used because it splits the high-value group.

| Persona | Customers | Share of revenue | Last order | Orders |
|---|---|---|---|---|
| Top accounts | 1,020 (18%) | 74% | 21 days ago | 14 |
| Solid regulars | 1,527 (26%) | 14% | 56 days ago | 5 |
| Recent newcomers | 1,376 (24%) | 6% | 45 days ago | 2 |
| Lapsed repeat buyers | 993 (17%) | 6% | 423 days ago | 2 |
| Lapsed small one-timers | 908 (16%) | 1% | 425 days ago | 1 |

The headline: the top two groups (44% of customers) generate 88% of revenue; the two lapsed groups (33%) generate 7%.
Cards with suggested actions: [`docs/personas.md`](docs/personas.md).

## Semantic layer and agent evaluation

*Built; real run pending.* The question: does a governed semantic layer make an AI agent more accurate on a messy database than raw SQL access, and what does it cost in flexibility?

- **Governed definitions** live in [`semantic/semantic_layer.yml`](semantic/semantic_layer.yml) in dbt MetricFlow style: five metrics (revenue, orders, active customers, average order value, customers), time grouping, and country through the customer entity. `src/semantic.py` compiles queries from it. It is a minimal compiler, not MetricFlow.
- **dbt compatibility:** dbt 1.12.5 accepts the YAML once a time-spine model is added (`semantic/dbt_metricflow/`), and the full build passes. The files sit outside `dbt/models` so a dbt version difference cannot break the build. Not tested on dbt 1.13 beta.
- **Running it:** `python agent_eval/make_desktop_configs.py` writes Claude Desktop configs for each condition with your own paths. A headless Claude Code runner exists but is experimental and needs the `claude` CLI.
- **Three conditions** ([protocol](agent_eval/PROTOCOL.md)): `raw` (every table, no definitions), `documented` (marts only, column meanings), `metrics` (governed tools).
- **Enforced by the database, not by the prompt:** read-only roles `agent_raw` and `agent_marts`; the documented and metrics conditions cannot read the raw schema.
- **20 questions:** 12 answered by governed metrics, 3 single-customer lookups, 5 the metric tools cannot answer. For those 5 the right behaviour in `metrics` is to decline.
- **Expected trade-off, to be measured:** `raw` gives plausible but wrong figures (cancellations, postage, missing customers and duplicates counted); `metrics` gives governed answers but declines what is not defined.

## Pricing and demand

`python -m src.pricing`, run on the real data (4,619 products, 172,340 product-weeks).

**Elasticity** (ln units on ln price, product and week fixed effects, standard errors clustered by product). Exploratory.

| Group | Elasticity | 95% interval | Products |
|---|---|---|---|
| All products, median price | -1.26 | -1.42 to -1.09 | 277 |
| All products, mean price | -3.44 | -3.89 to -2.99 | 891 |
| Low-price products | -1.12 | -1.35 to -0.89 | 74 |
| Mid-price products | -1.22 | -1.49 to -0.94 | 105 |
| High-price products | -1.70 | -1.99 to -1.42 | 98 |

**Sensitivity to the minimum sales lines per product-week:**

| Minimum lines | Elasticity | Products |
|---|---|---|
| 1 | -1.80 | 2,235 |
| 5 (default) | -1.26 | 277 |
| 10 | -0.99 | 100 |
| 20 | +0.17 (interval -0.89 to 1.23) | 22 |

**Price-quantity link.** Within the same product and week, ln(price) on ln(quantity) has a slope of -0.029 (se 0.001, 720,769 lines, 4,098 products): a line 10% bigger sells about 0.3% cheaper. Volume discounts exist but look small.

**A simulation shows why small can still matter.** In a simulated world where demand ignores price (true elasticity 0) but bigger lines are 0.03 cheaper per log unit, the estimator returns -1.9 to -3.0 on median price and -3.8 on mean price when prices vary by about 10% within a week. That is the same range as the real estimates. With tighter prices the artifact is far larger. The 10% spread is my assumption; the command now prints the real spread and the line-level "elasticity" that the price structure alone produces, to compare with the estimates above.

**Reading.**
- **The estimates are not stable.** They run from -1.80 to +0.17 as thin weeks are dropped, and from -1.26 to -3.44 depending on how price is measured.
- **They cannot be told apart from an artifact.** A pricing structure with a tiny quantity discount, and no true price response at all, produces estimates in the same range.
- **The revenue scenarios are not credible.** The -1.26 estimate implies that a 10% price cut raises revenue by 2.7%. Do not use it.
- **Conclusion:** this dataset cannot identify price elasticity. The module demonstrates the method and its limits. A credible answer needs a controlled price test.

**Demand baselines** (top 50 products, 4 weeks ahead, last 26 weeks; WAPE, lower is better):

| Model | Per product: WAPE | Per product: bias | Total of the 50: WAPE |
|---|---|---|---|
| Naive (last week) | 0.80 | -0.19 | 0.34 |
| 4-week average | 0.70 | -0.21 | 0.30 |
| Same week last year | 0.97 | +0.07 | 0.46 |
| Average of the last two | 0.78 | -0.07 | 0.33 |

Product-week demand is very lumpy: the best baseline misses 70% of volume. Summed over the 50 products the error drops to 30%, so forecast at the aggregate level. The seasonal baseline is the worst at both levels, with only one prior year of history.

## Reproduce

Needs Python 3.11 or 3.12, Docker Desktop, and the dataset (`data/raw/online_retail_II.xlsx`, see `data/raw/README.md`).
Use a virtual environment. The pins `numpy<2` and `scipy<1.13` (needed by `lifetimes`) can conflict with other projects.

Windows (cmd):
```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

docker compose up -d
set DATABASE_URL=postgresql+psycopg2://retainx:retainx@127.0.0.1:5432/retainx
set PGHOST=127.0.0.1
set PGPORT=5432

python scripts/profile_data.py data/raw/online_retail_II.xlsx
python scripts/load_raw.py data/raw/online_retail_II.xlsx
cd dbt && dbt build --profiles-dir . && cd ..
pytest -q
```

macOS / Linux: same steps, with `source .venv/bin/activate` and `export` in place of `set`. `make` shortcuts exist in the `Makefile`.

If you already run Postgres locally on port 5432, change the host port in `docker-compose.yml` (for example `5434:5432`) and set `PGPORT` and `DATABASE_URL` to match. The variables only last for the current terminal window.

Models and checks:
```
python -m src.models.churn --train-cutoff 2010-06-01 --test-cutoff 2010-12-01
python -m src.eval.backtest --task churn          # or --task propensity
python -m src.eval.experiments                    # baselines, logistic, pooled, recalibrated
python -m src.models.clv --calibration-end 2010-12-01 --horizons 90,180,365
python -m src.eval.clv_recalibration              # does an out-of-time correction fix CLV's level? (it does not)
python -m src.eval.clv_recalibration --bias-by-date   # does the CLV bias follow the calendar?
python -m src.health --train-cutoff 2011-03-01 --score-cutoff 2011-06-01
python -m src.personas --cutoff 2011-12-01 --k 5
python -m src.eval.ranking_check
python -m src.pricing
```

Agent evaluation (see `agent_eval/PROTOCOL.md`):
```
python scripts/create_agent_roles.py              # rerun after every dbt build
python agent_eval/make_key.py
python agent_eval/score.py
```

Notebook: `pip install -r requirements-notebooks.txt`, then `jupyter lab` from the repo root and open `notebooks/walkthrough.ipynb`.

Dedupe sensitivity (rebuild without dropping duplicates, rerun a model, then rebuild with the default):
```
cd dbt && dbt build --profiles-dir . --vars "{dedupe_exact: false}" && cd ..
```

MCP server (from the repo root): `python -m mcp_server.server`. Pinned `mcp<2`, because v2 renamed `FastMCP`.

## Design decisions

| Decision | Choice | Why |
|---|---|---|
| Time handling | Features use only data before the cutoff. Splits are by time, never random | A random split leaks the future. Unit tests check that features and ranking ignore later data |
| Exclusions | One model (`int_valid_sales`), flags upstream | Every dropped row is traceable |
| Duplicates | Flag, drop by default, toggle | Probably double entries, but not provable. Measured: no effect on churn results |
| `dim_customer` | No last-order or lifetime totals | Those would leak the future |
| Churn vs propensity | Different windows on purpose | Churn: active customers, 90-day horizon. Propensity: all customers, 30-day horizon |
| Health score | Logistic regression, terciles of predicted churn | Matches XGBoost, readable, no arbitrary thresholds. Validated by observed churn per band |
| Ranking signal | Repeat-purchase rate, judged as of each cutoff | The dataset has no ratings. A buyer counts as a repeater only if the second purchase is before the cutoff |
| CLV | BG/NBD, falling back to Pareto/NBD, used for ranking only | BG/NBD's formula is invalid when it fits a <= 1; on this data it degenerated. The level of Pareto/NBD follows the calendar |
| Personas | K-Means, k chosen by silhouette | Moderate structure only. A larger k can be forced for finer segments |
| Agent access | Governed metric tools and read-only database roles | The agent cannot pick the wrong redundant table or write anything, and the database enforces it |
| Semantic layer | YAML in MetricFlow style, compiled by a small Python module, kept outside `dbt/models` | Gives the agent one definition of each metric without risking the dbt build |

## Limitations

- Public data from one UK retailer, 2009 to 2011. Many customers look like wholesale buyers with lumpy purchasing, so 90-day "churn" may over-label.
- 22.8% of rows (13.3% of revenue) have no customer ID and are outside every customer model.
- Cancellations are excluded, not netted against the original orders.
- CLV totals are unreliable: the level follows the calendar (0.85 to 1.65 across calibration dates) and a fixed correction does not carry over. Use CLV to rank customers.
- The health score covers active customers only. At 2011-06-01, 45% of customers with a past order were already lapsed.
- Personas describe behaviour only. The dataset has no demographics.
- The semantic layer is a minimal compiler (simple and ratio metrics, one join, date filter only), not MetricFlow.
- The agent evaluation is small (20 questions), uses one model, and agent answers vary between runs.
- This dataset cannot identify price elasticity credibly: the estimates range from -3.4 to +0.2, and a simulation with zero true elasticity produces estimates in the same range.
- Pricing elasticity from observed prices would be biased. The pricing module is not built.
- No online evaluation. All metrics are offline backtests.
- `lifetimes` is old. If it fails to install, swap in `pymc-marketing`. It counts at most one purchase per time unit, so same-day invoices collapse.

## Next

1. Run the agent evaluation (3 conditions x 20 questions) and add the scores.
2. Run the pricing command again for the line-level price-quantity measurement, and add it above.
3. Run the notebook on the real data so the charts are embedded (`jupyter nbconvert --to notebook --execute notebooks/walkthrough.ipynb --inplace`), then commit it.
4. Push to GitHub; CI runs the unit tests and `dbt parse` on every push.

## Repository layout

| Path | What |
|---|---|
| `dbt/models/` | staging, intermediate, marts, with column descriptions and tests |
| `semantic/` | Governed metric definitions and the dbt time-spine files |
| `src/features.py`, `src/models/`, `src/eval/`, `src/ranking.py` | Features, models, backtests, experiments, ranking |
| `src/health.py`, `src/personas.py`, `src/pricing.py`, `src/semantic.py` | Health score, personas, pricing and demand, semantic layer compiler |
| `mcp_server/` | Metrics server and two read-only SQL baseline servers |
| `agent_eval/` | Questions, key generator, scorer, protocol |
| `scripts/` | Profile, load, and create-roles scripts |
| `notebooks/` | Walkthrough notebook |
| `tests/` | 45 tests (41 run by default; 4 more with `RETAINX_TEST_ROLES=1`, which creates database roles) |
| `docs/` | Problem statement, data quality log, decisions, personas |
| `.github/workflows/ci.yml` | Runs unit tests and `dbt parse` on every push |

## Data source

UCI Machine Learning Repository, Online Retail II (dataset 502), licensed CC BY 4.0.
