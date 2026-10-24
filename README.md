# retainx

[![CI](https://github.com/nikitasharma1203/retainx/actions/workflows/ci.yml/badge.svg)](https://github.com/nikitasharma1203/retainx/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![dbt-postgres](https://img.shields.io/badge/dbt-postgres-orange.svg)](https://www.getdbt.com/)
[![MCP Ready](https://img.shields.io/badge/MCP-FastMCP-green.svg)](https://modelcontextprotocol.io/)

**AI-native customer intelligence and semantic decision layer for Direct-to-Consumer (D2C) brands.**

`retainx` bridges raw transactional data with predictive intelligence and autonomous AI agents. It replaces blanket marketing blasts and volatile bestseller lists with **strictly time-split churn & propensity models**, **probabilistic CLV forecasting (BG/NBD + Gamma-Gamma)**, **cold-start-resilient product rankings (Wilson / Bayesian shrinkage)**, and a **guarded Model Context Protocol (MCP) server** that lets LLMs query business intelligence safely without writing raw SQL.

> **Portfolio Project Notice**: Built and benchmarked on public transactional data ([UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) — 1,067,371 rows across 2009–2011). Designed for zero target leakage, production reproducibility, and agentic workflows. Full problem statement in [`docs/problem_statement.md`](docs/problem_statement.md).

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph DataIngestion ["1. Data Ingestion & Quality Audit"]
        RAW["data/raw/online_retail_II.xlsx<br/>(1.06M rows)"] --> PROF["scripts/profile_data.py<br/>(Data Quality & Anomaly Log)"]
        RAW --> LOAD["scripts/load_raw.py<br/>(Chunked Ingestion)"]
        LOAD --> PG_RAW[("Postgres: raw.online_retail")]
    end

    subgraph ELT ["2. dbt Semantic Core & Marts"]
        PG_RAW --> STG["dbt Staging<br/>stg_transactions | stg_products<br/>(Type casts & quality flags)"]
        STG --> INT["dbt Intermediate<br/>int_valid_sales | int_customer_orders<br/>(Single-point exclusion rules)"]
        INT --> MARTS[("dbt Analytics Marts<br/>fct_orders | dim_customer | dim_product<br/>fct_product_customer | customer_rfm")]
    end

    subgraph Intelligence ["3. ML & Ranking Engine (Zero Data Leakage)"]
        MARTS --> FEAT["src/features.py<br/>Explicit Cutoff Feature Store"]
        FEAT --> CHURN["src/models/churn.py<br/>XGBoost Churn (180d lookback -> 90d horizon)"]
        FEAT --> PROP["src/models/propensity.py<br/>XGBoost 30-Day Purchase Propensity"]
        FEAT --> CLV["src/models/clv.py<br/>BG/NBD + Gamma-Gamma CLV"]
        MARTS --> RANK["src/ranking.py<br/>Wilson Lower Bound & Empirical Bayes Ranking"]
        CHURN & PROP --> BACKTEST["src/eval/backtest.py<br/>Quarterly Rolling Out-of-Time Backtesting"]
    end

    subgraph AgentLayer ["4. Agentic Interface (MCP Server)"]
        MARTS --> MCP["mcp_server/server.py<br/>(FastMCP Stdio Server)"]
        MCP --> TOOLS["Guarded Tools (50-row cap, parameterized):<br/>• describe_data()<br/>• get_customer_summary()<br/>• monthly_revenue()<br/>• top_products()"]
        TOOLS --> AGENT["Claude Desktop / Claude Code / AI Agents"]
    end
```

---

## Core Capabilities & Stakeholder Impact

| Stakeholder | Legacy Pain Point | retainx Solution | Implementation |
|---|---|---|---|
| **CRM & Retention** | Blanket email blasts; lapsed customers noticed too late | Calibrated 90-day churn prediction & 30-day purchase propensity models with top-decile lift tracking | [`src/models/churn.py`](src/models/churn.py)<br>[`src/models/propensity.py`](src/models/propensity.py) |
| **Growth & Finance** | Historical spend treated as lifetime value; no future projection | Probabilistic CLV separating transaction rate from average order profit across holdout windows | [`src/models/clv.py`](src/models/clv.py) |
| **Merchandising** | Top-product lists shuffle erratically; new launches spike on 3 fluke orders | Statistical shrinkage (Wilson 95% CI & Empirical Bayes) preventing small-sample cold-start distortions | [`src/ranking.py`](src/ranking.py) |
| **Analytics & AI Leads** | LLM agents querying raw databases hallucinate joins and query wrong tables | Zero raw SQL access; narrow, parameterized MCP tools backed by dbt `schema.yml` column descriptions | [`mcp_server/server.py`](mcp_server/server.py) |

---

## Key Design Principles & Data Governance

For an exhaustive audit trail, review [`docs/decisions.md`](docs/decisions.md) and [`docs/data_quality_log.md`](docs/data_quality_log.md).

1. **Strict Zero-Leakage Feature Engineering**:
   - `features` exclusively use orders strictly timestamped `< cutoff`.
   - `labels` exclusively examine target behavior in `[cutoff, cutoff + horizon)`.
   - Cross-validation uses **time splits only**; random splits are forbidden because they leak future behavior into the past.
2. **Single Point of Exclusion**:
   - Raw data is kept complete in `raw.online_retail` and `staging.stg_transactions`.
   - Business exclusions (cancellations `C%`, unassigned `customer_id is null`, non-merchandise stock codes like `POST`, `BANK CHARGES`, `D`, `M`) occur exclusively inside [`dbt/models/intermediate/int_valid_sales.sql`](dbt/models/intermediate/int_valid_sales.sql).
3. **Time-Invariant Dimensional Modeling**:
   - `dim_customer` contains time-invariant attributes (`first_order_ts`, `country`). Lifetime totals and recency are strictly computed at explicit cutoff dates via `customer_rfm` or `src/features.py` to prevent retrospective data contamination.
4. **Agent Guardrails**:
   - LLMs never get raw arbitrary SQL access. All database interactions flow through vetted, parameterized SQL queries capped at 50 rows.

---

## Project Structure

```text
retainx/
├── .github/workflows/
│   └── ci.yml               # Automated CI (pytest unit tests + dbt parse)
├── data/
│   └── raw/
│       ├── README.md        # Download instructions for Online Retail II
│       └── online_retail_II.xlsx (Git-ignored raw dataset)
├── dbt/                     # dbt Core transformation project
│   ├── dbt_project.yml      # Project configuration & variables (cutoff_date)
│   ├── profiles.yml         # Postgres connection (dev target port 5434)
│   ├── models/
│   │   ├── sources.yml      # Raw table source declarations
│   │   ├── staging/         # Typed views (stg_transactions, stg_products)
│   │   ├── intermediate/    # Business filters (int_valid_sales, int_customer_orders)
│   │   └── marts/           # Analytics tables (fct_orders, dim_customer, dim_product, customer_rfm)
│   └── tests/               # Custom business assertions (assert_revenue_reconciles.sql)
├── docs/
│   ├── agent_eval_questions.md # Benchmark test suite for agent SQL vs MCP accuracy
│   ├── data_quality_log.md  # 1.06M row profiling findings & transformation choices
│   ├── decisions.md         # Architecture decision register & trade-offs
│   └── problem_statement.md # Business case, baselines, and hypotheses
├── mcp_server/              # Model Context Protocol service
│   ├── README.md            # Client configuration for Claude Desktop
│   └── server.py            # FastMCP server exposing guarded dbt tools
├── reports/                 # Machine-generated benchmark evaluation logs
│   ├── churn_metrics.json   # Churn model performance & calibration curve
│   └── clv_metrics.json     # CLV model holdout metrics
├── scripts/                 # Administrative & ETL utilities
│   ├── _common.py           # Multi-sheet Excel / CSV reader with schema normalization
│   ├── load_raw.py          # Chunked raw loader into Postgres raw schema
│   └── profile_data.py      # Day-1 automated dataset profiling tool
├── sql/
│   └── 00_create_schema.sql # Docker entrypoint initializing raw and analytics schemas
├── src/                     # Core analytics & machine learning package
│   ├── config.py            # Cutoffs, table mappings, and model parameters
│   ├── features.py          # Leakage-safe feature & label builder
│   ├── ranking.py           # Wilson lower bound & Bayesian shrinkage rankers
│   ├── eval/
│   │   └── backtest.py      # Rolling time-window model stability evaluation
│   └── models/
│       ├── churn.py         # 90-day churn classifier (XGBoost)
│       ├── clv.py           # BG/NBD + Gamma-Gamma lifetime value models
│       ├── common.py        # Time-split train/evaluate routine with Brier & Lift
│       └── propensity.py    # 30-day purchase propensity classifier (XGBoost)
├── tests/
│   ├── conftest.py          # Pytest path configurations
│   └── test_features.py     # Leakage, horizon boundary, and shrinkage unit tests
├── docker-compose.yml       # PostgreSQL 16 container definition
├── Makefile                 # One-command execution recipes
└── requirements.txt         # Pinned production dependencies
```

---

## Quickstart Guide

### 1. Prerequisites & Environment Setup

- Python 3.11+
- Docker & Docker Compose
- Virtual environment:

```bash
# Clone the repository
git clone https://github.com/nikitasharma1203/retainx.git
cd retainx

# Configure environment variables
cp .env.example .env

# Create and activate virtual environment
python -m venv .venv
# On macOS/Linux:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt
```

> [!NOTE]
> **Database Port Note**: In `docker-compose.yml`, Postgres maps container port `5432` to host port `5434` (to avoid collision with existing local Postgres instances). Verify that your `.env` contains:
> ```dotenv
> PGPORT=5434
> DATABASE_URL=postgresql+psycopg2://retainx:retainx@localhost:5434/retainx
> ```

---

### 2. Database & Data Ingestion

1. **Spin up PostgreSQL 16**:
   ```bash
   make up
   ```
2. **Download Dataset**:
   Place the UCI Online Retail II Excel file in `data/raw/online_retail_II.xlsx` (see [`data/raw/README.md`](data/raw/README.md)).
3. **Profile the Raw File**:
   ```bash
   make profile FILE=data/raw/online_retail_II.xlsx
   ```
4. **Load Raw Data to Postgres**:
   ```bash
   make load FILE=data/raw/online_retail_II.xlsx
   ```

---

### 3. Run Transformations & Quality Tests (dbt)

Compile and build all staging views, intermediate filters, and dimensional marts:

```bash
# Execute dbt build (runs models and schema tests)
make dbt-build

# Run custom test suite (e.g. revenue reconciliation between lines and orders)
make dbt-test
```

To build RFM tables for a specific historical cutoff date:
```bash
cd dbt && dbt build --vars '{cutoff_date: "2011-03-01"}' --profiles-dir . && cd ..
```

---

### 4. Run Unit Tests (Leakage & Ranking Integrity)

Verify that feature construction never looks into the future, label windows are bounded, and Bayesian shrinkage operates as expected:

```bash
make test
```

---

### 5. Train & Evaluate Models

#### A. Churn Prediction (XGBoost)
Predicts which customers active in the preceding 180 days will make zero purchases in the subsequent 90 days:
```bash
make churn
```
*Outputs evaluation metrics to `reports/churn_metrics.json`.*

#### B. Rolling Backtesting
Evaluates model stability and out-of-time performance across sequential quarters:
```bash
make backtest
# Or test propensity across windows:
python -m src.eval.backtest --task propensity
```

#### C. Customer Lifetime Value (BG/NBD + Gamma-Gamma)
Fits transaction frequency and conditional monetary value on calibration data and tests against a 1-year holdout:
```bash
make clv
```
*Outputs fit summaries to `reports/clv_metrics.json`.*

#### D. Repeat-Purchase Product Ranking Simulation
Simulate how cold-start products behave under naive repeat rate vs. Wilson 95% confidence lower bound vs. Bayesian shrinkage:
```bash
python -c "
import pandas as pd
from src import config, ranking
from sqlalchemy import create_engine
eng = create_engine(config.DB_URL)
pc = pd.read_sql('select * from ' + config.PRODUCT_CUSTOMER_TABLE, eng, parse_dates=['first_purchase_ts'])
pr = pd.read_sql('select stock_code, description, first_sale_ts from ' + config.PRODUCT_TABLE, eng, parse_dates=['first_sale_ts'])
stats = ranking.product_stats(pc, pr, '2011-06-01')
print('Top 5 Products via Wilson Lower Bound:')
print(stats.sort_values('wilson', ascending=False)[['n_customers', 'naive', 'wilson', 'bayes']].head())
"
```

---

## Model Evaluation & Real-Data Benchmarks

Evaluated on the full 2-year UCI dataset:

### 1. 90-Day Churn Model Performance (`reports/churn_metrics.json`)
- **Train Window Cutoff**: `2010-06-01` ($N=2,672$)
- **Test Window Cutoff**: `2010-12-01` ($N=3,471$)
- **Base Churn Rate**: $61.97\%$
- **ROC AUC**: **$0.741$**
- **Average Precision (PR-AUC)**: **$0.791$**
- **Top-Decile Lift**: **$1.37\times$** (targeting the top 10% risk segment captures 1.37× more churners than random selection)
- **Calibration (Brier Score)**: $0.238$ with monotonic probability deciles.

### 2. Product Ranking Stability
- **Problem**: In naive sorting ($p = \frac{\text{repeaters}}{\text{buyers}}$), a new product with $2$ buyers and $2$ repeaters ($100\%$) outranks an established bestseller with $800$ repeaters out of $1,000$ buyers ($80\%$).
- **Solution**:
  - **Wilson Score Lower Bound**: Computes the 95% confidence lower bound of the binomial proportion. A $2/2$ item receives a score of $\approx 0.34$, keeping it out of top ranks until sufficient sample size accumulates.
  - **Empirical Bayes Shrinkage**: Pulls product rates toward catalogue-wide average ($\alpha=20$ pseudo-customers).

---

## Agentic Interface: MCP Server

`retainx` includes a native Model Context Protocol (MCP) server that provides AI agents with controlled access to the analytics layer.

### Exposed Tools

1. `describe_data()`: Introspects dbt `schema.yml` to return available tables, grain, and column business definitions.
2. `get_customer_summary(customer_id: int, as_of: str)`: Returns orders, revenue, and recency strictly prior to `as_of`.
3. `monthly_revenue(start: str, end: str)`: Aggregates historical monthly order volumes and revenue.
4. `top_products(as_of: str, n: int, method: str)`: Generates stable rankings using `'wilson'`, `'bayes'`, or `'naive'`.

### Connecting to Claude Desktop / Claude Code

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "retainx": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/retainx",
      "env": {
        "DATABASE_URL": "postgresql+psycopg2://retainx:retainx@localhost:5434/retainx"
      }
    }
  }
}
```

### Measuring Agent Accuracy
The repository includes a 10-question evaluation benchmark in [`docs/agent_eval_questions.md`](docs/agent_eval_questions.md) comparing agent accuracy when accessing raw database tables versus the curated `retainx` semantic layer.

---

## Tech Stack & Dependencies

- **Database**: PostgreSQL 16
- **Transformation**: dbt-core 1.8 (`dbt-postgres`)
- **Machine Learning**: scikit-learn, XGBoost, lifetimes (BG/NBD, Gamma-Gamma)
- **Data Engineering**: pandas, NumPy, SQLAlchemy, psycopg2-binary, openpyxl
- **Agent Protocols**: FastMCP (MCP SDK)
- **Testing & CI**: pytest, GitHub Actions

---

## Known Constraints & Assumptions

- **Return Handling**: Cancelled orders (`C%`) are excluded rather than matched and netted against original orders.
- **Daily Aggregation in Lifetimes**: The `lifetimes` package aggregates multiple same-day orders into a single daily event.
- **Observational Pricing**: Price elasticity estimates on non-experimental retail data reflect observational variance, not causal demand elasticity.
- **MCP Versioning**: `mcp` is pinned to `<2.0` due to upstream syntax changes with FastMCP.

---

## License

This project is licensed under the MIT License. Public dataset sourced from the UCI Machine Learning Repository.
