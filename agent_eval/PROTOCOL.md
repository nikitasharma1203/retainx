# Agent evaluation protocol

**Question:** does a governed semantic layer make an AI agent more accurate on a messy database than raw SQL access,
and what does it cost in flexibility?

| Condition | What the agent gets | Role |
|---|---|---|
| `raw` | `list_tables` (names and types) + `run_sql` over `raw.*` and `analytics.*` (redundant tables, staging views, no definitions) | `agent_raw` |
| `documented` | `describe_data` (marts with column meanings) + `run_sql` over the five marts only | `agent_marts` |
| `metrics` | `list_metrics`, `query_metric` (governed definitions), plus `get_customer_summary`, `monthly_revenue`, `top_products`, `describe_data` | `agent_marts` |

20 questions: 12 answered by governed metrics, 3 single-customer lookups, 5 that the metric tools cannot answer.
For those 5 the right behaviour in `metrics` is to decline, so they are scored separately.

## Setup (once, and after every `dbt build`)

```
python scripts/create_agent_roles.py
python agent_eval/make_key.py
```
`make_key.py` runs the reference SQL and writes `answer_key.csv` and a blank `answers_template.csv`.
Read the warning it prints: if customer 12347 is missing, change the id in `questions.yml` (questions 13 to 15) and rerun.
Question 18 reads `customer_rfm`, so build it at its default cutoff (2010-12-01).

## Claude Desktop configuration (Windows paths; adjust to yours)

Add ONE of these servers at a time, and turn off every other tool and connector for the run, so tools cannot leak between conditions.

```json
{
  "mcpServers": {
    "retainx-raw": {
      "command": "C:\\Users\\sniks\\retainx\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.sql_server", "--mode", "raw"],
      "env": {"PYTHONPATH": "C:\\Users\\sniks\\retainx",
              "DATABASE_URL": "postgresql+psycopg2://retainx:retainx@127.0.0.1:5434/retainx"}
    }
  }
}
```
For `documented` use `"--mode", "documented"`. For `metrics` use `"args": ["-m", "mcp_server.server"]`.
The servers swap in the read-only role from `DATABASE_URL`'s host, port and database; the superuser password is not used.

## Running

1. New chat for every question. Same first message every time:

   > Use only the connected tools to answer. Give one exact figure (no rounding) or one name. If the tools cannot answer this, reply DECLINE and say why. End your reply with a line "ANSWER: <value>" (or "ANSWER: DECLINE").
   > Question: *(paste the question)*

2. **Do not explain definitions** (what counts as a valid order or as revenue) in any condition. Finding them is part of the test.
3. Copy `answers_template.csv` to `answers_run1.csv`. For each question paste the agent's reply (or just its ANSWER line) into `answer`. The scorer reads the `ANSWER:` line and treats DECLINE as declined, so you can leave `declined` as 0.
4. Repeat the whole thing with `run = 2` and `3` if you can. The agent's answers vary between runs.
5. `python agent_eval/score.py` prints correct / wrong / declined per condition and category.

## Reading the result

* **Wrong is worse than declined.** A confident wrong number is the real failure; compare the `wrong` columns first.
* In `raw`, expect plausible-but-wrong revenue figures (cancellations, postage, missing customers and duplicates included).
  That gap is the case for governed definitions.
* In `metrics`, expect `declined` on the 5 out-of-scope questions. That is the price: governed answers, less flexibility.
* 20 questions per condition is a small sample. Report counts, not just percentages, and do not claim significance.
* One model and one configuration were tested. Say which.

## Optional: run it headlessly with Claude Code (experimental)

```
python agent_eval/run_claude_code.py --condition raw --limit 1 --dry-run   # prints the command
python agent_eval/run_claude_code.py --condition raw --limit 1             # one real question
python agent_eval/run_claude_code.py --condition raw                       # all 20, resumable
```
Then `documented` and `metrics`. This script is untested against the live Claude Code CLI; if a flag fails on your version,
use the manual steps above. It runs from an empty folder and allows only one condition's tools. It uses your Claude Code usage.
