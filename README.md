# retainx

AI-native customer intelligence layer for D2C: propensity, churn, CLV, health score, personas,
stable product ranking, and a semantic layer an AI agent can query safely.

Portfolio project on public data (UCI Online Retail II). No live client, no A/B test.
Full problem statement: [`docs/problem_statement.md`](docs/problem_statement.md).

## Quick start

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make up                                                  # Postgres in Docker
make profile FILE=data/raw/online_retail_II.xlsx         # day-1 data check, paste into docs/data_quality_log.md
make load    FILE=data/raw/online_retail_II.xlsx         # raw -> Postgres
make dbt-build                                           # staging, marts, tests
make test                                                # leakage + ranking unit tests
make churn                                               # train/test with a time split
make backtest                                            # rolling backtest
make clv
```

Download the data first (see `data/raw/README.md`) and check column names and the date range
against `src/config.py`.

## Layout

| Path | What |
|---|---|
| `dbt/models/staging` | Typed raw data. Nothing dropped, issues flagged |
| `dbt/models/intermediate` | `int_valid_sales`: the one place rows are excluded |
| `dbt/models/marts` | `fct_orders`, `dim_customer`, `dim_product`, `fct_product_customer`, `customer_rfm` |
| `src/features.py` | Leakage-safe features and labels, cutoff always explicit |
| `src/models` | churn, propensity, CLV (BG/NBD + Gamma-Gamma) |
| `src/eval/backtest.py` | Rolling time-split evaluation |
| `src/ranking.py` | Wilson / Bayesian ranking and cold-start check |
| `mcp_server` | Narrow read-only MCP tools (phase 2) |
| `docs/` | Problem statement, data quality log, decisions, agent eval set |

## Build order

| Week | Deliverable |
|---|---|
| 1 | Raw load, quality log, staging, dbt tests green |
| 2 | Marts, RFM, behaviour analytics notebook, CI |
| 3 | Churn (time split) and CLV |
| 4 | Propensity, health score, personas |
| 5 | Ranking simulation, dbt MetricFlow metrics |
| 6 | MCP agent and its accuracy test |

Not built yet: health score, personas, pricing/demand, MetricFlow metrics, notebooks.

## What was and was not tested

Tested here on **synthetic data shaped like Online Retail II** (not the real file):
loader and profile scripts, `dbt build` (28/28 passing on Postgres 16), churn / propensity /
backtest / CLV code paths, the MCP server over stdio, and the unit tests.

Not tested: the real dataset. Expect to adjust column names, cutoffs, and the stock-code filter
after you look at the real profile output. Metrics from synthetic runs mean nothing.

## Known caveats

- `lifetimes` is old and pinned with `numpy<2`. If install fails, swap in `pymc-marketing` for CLV.
- BG/NBD can fail to converge on sparse data. `clv.py` retries with stronger penalizers.
- `lifetimes` counts one purchase per day, so same-day invoices collapse.
- `mcp` is pinned `<2` (v2 renamed `FastMCP`).
- Cancellations are excluded, not netted against original orders.
- Pricing elasticity from observational prices is biased. State that when presenting.
