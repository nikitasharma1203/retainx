"""Create read-only database roles for the agent evaluation.

  agent_raw    can read raw.* and analytics.* (every table and view, no documentation)
  agent_marts  can read only the five mart tables (used by the documented and metrics conditions)

dbt drops and recreates tables, which removes grants. Rerun this after every `dbt build`.
The passwords are for a local development database only.

Usage: python scripts/create_agent_roles.py
"""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

MARTS = ["fct_orders", "dim_customer", "dim_product", "fct_product_customer", "customer_rfm"]


def main() -> None:
    url = make_url(os.getenv("DATABASE_URL", "postgresql+psycopg2://retainx:retainx@localhost:5432/retainx"))
    eng = create_engine(url, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        for role in ("agent_raw", "agent_marts"):
            if not c.execute(text("select 1 from pg_roles where rolname = :r"), {"r": role}).scalar():
                c.execute(text(f"create role {role} login password 'agent'"))
            c.execute(text(f'grant connect on database "{url.database}" to {role}'))
            c.execute(text(f"revoke all on all tables in schema raw, analytics from {role}"))
            c.execute(text(f"revoke all on schema raw, analytics from {role}"))
        c.execute(text("grant usage on schema raw, analytics to agent_raw"))
        c.execute(text("grant select on all tables in schema raw, analytics to agent_raw"))
        c.execute(text("grant usage on schema analytics to agent_marts"))
        for t in MARTS:
            c.execute(text(f"grant select on analytics.{t} to agent_marts"))
    print("Roles ready: agent_raw (raw + analytics), agent_marts (five marts only). Rerun after each dbt build.")


if __name__ == "__main__":
    main()
