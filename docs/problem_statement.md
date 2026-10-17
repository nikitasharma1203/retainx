# retainx: AI-native customer intelligence layer for D2C

*Know which customers will buy, leave or grow, and which products deserve the spotlight, without anyone writing SQL.*

## Context
A mid-size D2C brand has orders, events and a product catalogue. Its data says what happened, not who to act on or what to do next. Data sits in redundant tables, and every new launch shuffles the "top products" list.

> This is a portfolio project on public data (UCI Online Retail II). There is no live client and no A/B test.

## The people

| Person | Pain today |
|---|---|
| CRM manager | Campaigns go to everyone because nobody knows who will buy or churn |
| Merchandiser | Bestseller ranking is unstable. New launches get buried or spike on 3 orders |
| Growth lead | Pricing and stock decisions are gut-based. A data question takes days |

## Baseline (measure first, do not assume)

| Factor | Start |
|---|---|
| Who to target | Blanket sends |
| Churn visibility | None until a customer has lapsed |
| Customer value | Revenue to date only, no forecast |
| Top-products rank | Raw average or count, unstable on new items |
| Price and demand | Manual, no elasticity estimate |
| Data access | Raw redundant tables, analyst-dependent |

## North Star
A CRM manager can pick a segment, see its predicted value and churn risk, and launch an action in minutes.

## Approach

| Module | For | Method |
|---|---|---|
| Behaviour and funnel analytics | Growth | Cohorts and RFM (extends CartPulse) |
| Propensity | CRM | XGBoost purchase-likelihood, checked for calibration |
| Churn and CLV | CRM | Churn classifier; BG/NBD with Gamma-Gamma for value |
| Customer health score | CRM | Composite of recency, frequency, trend; validated against real churn |
| Personas | CRM | K-Means on behaviour; Claude writes plain-language persona cards |
| Demand and pricing | Growth | Forecast plus price elasticity (observational, so biased; say so) |
| Stable top-products ranking | Merchandiser | Wilson lower bound or Bayesian shrinkage |
| Semantic layer and MCP agent | All | Curated dbt marts, column descriptions, narrow read-only MCP tools |

## Success metrics (hypotheses to test on a holdout, not promised results)

| Metric | How measured |
|---|---|
| Propensity lift, top decile | Holdout lift curve |
| Churn model | Time-split AUC and calibration, never a random split |
| CLV | Forecast vs actual spend in a held-out period |
| Rank stability | Mean top-20 rank displacement when new products are added |
| Agent accuracy | Correct answers on 20 fixed business questions, with and without the semantic layer |

## Priority
1. **Now:** data model, semantic layer, behaviour analytics, churn and CLV.
2. **Next:** propensity, health score, personas, ranking.
3. **Later:** pricing and demand.

**Say no to:** a real-time streaming pipeline, UI polish, and a deep-learning model where a simpler one matches it.

**Done means** the metrics above moved against a stated baseline. Feature-complete alone does not count.
