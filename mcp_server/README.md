# MCP server (phase 2)

Read-only tools over the dbt marts. The agent gets no raw SQL.

| Tool | Purpose |
|---|---|
| `describe_data` | Table and column descriptions from dbt `schema.yml` (the lightweight semantic layer) |
| `get_customer_summary(customer_id, as_of)` | Orders, revenue, recency before a date |
| `monthly_revenue(start, end)` | Revenue and orders per month |
| `top_products(as_of, n, method)` | Stable ranking (wilson, bayes or naive) |

Run from the repo root:

    python -m mcp_server.server

Add to Claude Desktop / Claude Code as a stdio server pointing at that command, with the repo root as the working directory.

`mcp` is pinned to `<2` because v2 renamed `FastMCP`. If you move to v2, change the import.

Guardrails in the code: whitelisted queries only, parameterised SQL, date validation, 50-row cap.
