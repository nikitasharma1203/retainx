# MCP servers

Read-only tools over the dbt marts. The agent never gets write access, and in two of the three modes it never sees the raw data.

| Server | Command | Tools |
|---|---|---|
| Metrics (governed) | `python -m mcp_server.server` | `list_metrics`, `query_metric`, `get_customer_summary`, `monthly_revenue`, `top_products`, `describe_data` |
| Documented SQL | `python -m mcp_server.sql_server --mode documented` | `describe_data`, `run_sql` (five marts only) |
| Raw SQL | `python -m mcp_server.sql_server --mode raw` | `list_tables`, `run_sql` (raw and analytics, no documentation) |

The last two exist as baselines for the agent evaluation in [`agent_eval/`](../agent_eval/PROTOCOL.md).
Create the database roles first (`python scripts/create_agent_roles.py`) and rerun it after every `dbt build`.

Run from the repo root with `PYTHONPATH` set to it and `DATABASE_URL` pointing at your database.
The SQL servers swap in a read-only role (`agent_raw` or `agent_marts`) and keep only the host, port and database name.

Guardrails: one SELECT or WITH statement, a READ ONLY transaction, a 10 second timeout, a 100-row cap, parameterised metric queries, date validation.

`mcp` is pinned `<2` because v2 renamed `FastMCP`.
