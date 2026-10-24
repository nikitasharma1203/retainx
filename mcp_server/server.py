"""retainx MCP server: narrow, read-only tools over the dbt marts.

The agent never gets raw SQL access. Each tool hides which tables/columns are canonical,
so Claude cannot pick the wrong one. describe_data() returns the column descriptions from
dbt's schema.yml, which is the lightweight semantic layer.

Run (from repo root):   python -m mcp_server.server
Needs:                  pip install "mcp>=1.2,<2"   (v2 renamed FastMCP, so this is pinned)
"""
from __future__ import annotations

import datetime as dt
import decimal
import os
from pathlib import Path

import pandas as pd
import yaml
from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text

from src import config, ranking
from src.semantic import SemanticLayer

MAX_ROWS = 50
ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILES = [ROOT / "dbt/models/marts/schema.yml"]

engine = create_engine(os.getenv("DATABASE_URL", config.DB_URL))
mcp = FastMCP("retainx")
semantic = SemanticLayer()


def _clean(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return v.isoformat()
    return v


def _query(sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).fetchmany(MAX_ROWS)
    return [{k: _clean(v) for k, v in r._mapping.items()} for r in rows]


def _date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"Dates must be YYYY-MM-DD, got {s!r}") from e


@mcp.tool()
def list_metrics() -> list[dict]:
    """Governed business metrics (revenue, orders, active_customers, avg_order_value, customers), what they mean,
    and how each can be grouped. Always use these definitions rather than raw tables."""
    return semantic.list_metrics()


@mcp.tool()
def query_metric(metric: str, group_by: str | None = None, start: str | None = None, end: str | None = None) -> list[dict]:
    """Compute a governed metric. group_by: day, week, month, quarter, year or a dimension such as country.
    start (inclusive) and end (exclusive) are YYYY-MM-DD dates. Call list_metrics first."""
    return semantic.query(engine, metric, group_by, start, end)


@mcp.tool()
def describe_data() -> list[dict]:
    """List the available tables and what every column means. Call this first."""
    out = []
    for f in SCHEMA_FILES:
        for m in yaml.safe_load(f.read_text())["models"]:
            out.append({
                "table": f"analytics.{m['name']}",
                "description": m.get("description", ""),
                "columns": {c["name"]: c.get("description", "") for c in m.get("columns", [])},
            })
    return out


@mcp.tool()
def get_customer_summary(customer_id: int, as_of: str) -> dict:
    """Orders, revenue, last order date and recency for one customer, using only orders before `as_of` (YYYY-MM-DD)."""
    d = _date(as_of)
    rows = _query(
        """
        select count(*) as n_orders, sum(order_revenue) as revenue, max(invoice_ts) as last_order
        from analytics.fct_orders
        where customer_id = :cid and invoice_ts < :d
        """,
        {"cid": customer_id, "d": d},
    )
    r = rows[0]
    if not r["n_orders"]:
        return {"customer_id": customer_id, "as_of": as_of, "found": False}
    last = dt.datetime.fromisoformat(r["last_order"]).date()
    country = _query("select country from analytics.dim_customer where customer_id = :cid", {"cid": customer_id})
    return {"customer_id": customer_id, "as_of": as_of, "found": True,
            "n_orders": r["n_orders"], "revenue": round(r["revenue"], 2),
            "last_order": r["last_order"], "recency_days": (d - last).days,
            "country": country[0]["country"] if country else None}


@mcp.tool()
def monthly_revenue(start: str, end: str) -> list[dict]:
    """Revenue and order count per month for [start, end) (YYYY-MM-DD)."""
    return _query(
        """
        select date_trunc('month', invoice_ts)::date as month,
               count(*) as n_orders, sum(order_revenue) as revenue
        from analytics.fct_orders
        where invoice_ts >= :s and invoice_ts < :e
        group by 1 order by 1
        """,
        {"s": _date(start), "e": _date(end)},
    )


@mcp.tool()
def top_products(as_of: str, n: int = 10, method: str = "wilson") -> list[dict]:
    """Top products by repeat-purchase rate as of a date. method: wilson (default), bayes or naive.
    Wilson and bayes keep brand-new products from jumping to the top on a handful of buyers."""
    if method not in {"wilson", "bayes", "naive"}:
        raise ValueError("method must be wilson, bayes or naive")
    n = max(1, min(int(n), MAX_ROWS))
    pc = pd.read_sql(f"select * from {config.PRODUCT_CUSTOMER_TABLE}", engine, parse_dates=["first_purchase_ts", "second_purchase_ts"])
    pr = pd.read_sql(f"select stock_code, description, first_sale_ts from {config.PRODUCT_TABLE}", engine,
                     parse_dates=["first_sale_ts"])
    st = ranking.product_stats(pc, pr, _date(as_of)).join(pr.set_index("stock_code")["description"])
    top = st.sort_values(method, ascending=False).head(n).reset_index()
    return [{"stock_code": r.stock_code, "description": r.description, "n_customers": int(r.n_customers),
             "repeat_rate": round(float(r.naive), 3), "score": round(float(getattr(r, method)), 3),
             "is_new": bool(r.is_new)} for r in top.itertuples()]


if __name__ == "__main__":
    mcp.run()
