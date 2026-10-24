"""Read-only SQL tools used as the baselines in the agent evaluation.

  --mode raw         list_tables (names and types only) + run_sql. Role agent_raw: raw and analytics schemas.
  --mode documented  describe_data (marts with column descriptions from dbt) + run_sql. Role agent_marts: marts only.

Safety: one SELECT or WITH statement, run inside a READ ONLY transaction with a 10 s timeout and a 100-row cap,
connected as a role that cannot write and (in documented mode) cannot see the raw data.
Run from the repo root with PYTHONPATH set:  python -m mcp_server.sql_server --mode raw
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import os
import re
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src import config

MAX_ROWS = 100
ROLES = {"raw": "agent_raw", "documented": "agent_marts"}
SCHEMA_FILE = Path(__file__).resolve().parents[1] / "dbt/models/marts/schema.yml"


def make_engine(mode: str):
    url = os.getenv("AGENT_DATABASE_URL") or make_url(config.DB_URL).set(username=ROLES[mode], password="agent")
    return create_engine(url)


def check_query(q: str) -> str:
    q = q.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", q):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in q:
        raise ValueError("One statement only.")
    return q


def _clean(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return v


def run_sql(engine, query: str) -> dict:
    q = check_query(query)
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        conn.exec_driver_sql("SET LOCAL statement_timeout = 10000")
        res = conn.execute(text(q.replace(":", "\\:")))      # colons are literal, not bind parameters
        rows = res.fetchmany(MAX_ROWS + 1)
        cols = list(res.keys())
    return {"columns": cols, "rows": [[_clean(v) for v in r] for r in rows[:MAX_ROWS]], "truncated": len(rows) > MAX_ROWS}


def list_tables(engine) -> dict:
    sql = """select table_schema || '.' || table_name as t, column_name || ' ' || data_type as c
             from information_schema.columns
             where table_schema in ('raw', 'analytics') and table_name not like 'metricflow%'
             order by 1, ordinal_position"""
    out: dict = {}
    with engine.connect() as conn:
        for t, c in conn.execute(text(sql)):
            out.setdefault(t, []).append(c)
    return out


def describe_data(engine) -> list[dict]:
    types = list_tables(engine)
    docs = {m["name"]: m for m in yaml.safe_load(SCHEMA_FILE.read_text())["models"]}
    out = []
    for t, cols in types.items():
        name = t.split(".")[1]
        m = docs.get(name, {})
        cdesc = {c["name"]: c.get("description", "") for c in m.get("columns", [])}
        out.append({"table": t, "description": m.get("description", ""),
                    "columns": {c.split(" ")[0]: {"type": c.split(" ", 1)[1], "meaning": cdesc.get(c.split(" ")[0], "")} for c in cols}})
    return out


def build(mode: str):
    from mcp.server.fastmcp import FastMCP
    engine = make_engine(mode)
    mcp = FastMCP(f"retainx-sql-{mode}")

    if mode == "raw":
        @mcp.tool(name="list_tables")
        def _list_tables() -> dict:
            """List the tables and columns you can query, with their types."""
            return list_tables(engine)
    else:
        @mcp.tool(name="describe_data")
        def _describe_data() -> list[dict]:
            """The tables you can query, what each means, and what every column means. Call this first."""
            return describe_data(engine)

    @mcp.tool(name="run_sql")
    def _run_sql(query: str) -> dict:
        """Run one read-only SELECT query (PostgreSQL). Returns up to 100 rows."""
        return run_sql(engine, query)

    return mcp


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=list(ROLES), required=True)
    build(ap.parse_args().mode).run()
