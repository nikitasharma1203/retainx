"""EXPERIMENTAL: run the evaluation headlessly with Claude Code (`claude -p`).

Not tested against the live CLI (no Claude Code in my test environment); only the command building,
config writing and parsing are tested. Try one question first:  --condition raw --limit 1 --dry-run, then without --dry-run.
If a flag fails on your version, use the manual protocol in PROTOCOL.md; it does not depend on this script.

It runs from an empty temporary folder so the agent cannot read this repo's docs, and it allows only the tools of one MCP server.
It spends your Claude Code usage: 20 questions x 3 conditions is 60 runs per repeat.

Usage: python agent_eval/run_claude_code.py --condition raw|documented|metrics [--run 1] [--limit N] [--model NAME] [--dry-run]
Needs DATABASE_URL set (as for the other scripts) and the roles created with scripts/create_agent_roles.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import make_key  # noqa: E402

SERVERS = {
    "raw": ("retainx-raw", ["-m", "mcp_server.sql_server", "--mode", "raw"]),
    "documented": ("retainx-documented", ["-m", "mcp_server.sql_server", "--mode", "documented"]),
    "metrics": ("retainx-metrics", ["-m", "mcp_server.server"]),
}
PROMPT = ("Use only the connected tools to answer. Give one exact figure (no rounding) or one name. "
          "If the tools cannot answer this, reply DECLINE and say why. "
          "End your reply with a line 'ANSWER: <value>' (or 'ANSWER: DECLINE').\nQuestion: {q}")


def write_config(path: Path, condition: str, python: str = sys.executable, env: dict | None = None) -> str:
    name, args = SERVERS[condition]
    env = env or {"PYTHONPATH": str(ROOT), "DATABASE_URL": os.environ.get("DATABASE_URL", "")}
    path.write_text(json.dumps({"mcpServers": {name: {"command": python, "args": args, "env": env}}}, indent=2))
    return name


def build_command(claude: str, name: str, config_path: Path, question: str, model: str | None = None) -> list[str]:
    cmd = [claude, "-p", PROMPT.format(q=question), "--output-format", "json",
           "--mcp-config", str(config_path), "--strict-mcp-config",
           "--allowedTools", f"mcp__{name}", "--max-turns", "15"]
    return cmd + (["--model", model] if model else [])


def parse_result(stdout: str) -> str:
    return str(json.loads(stdout).get("result", "")).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", required=True, choices=list(SERVERS))
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    claude = shutil.which("claude")
    if not claude and not a.dry_run:
        sys.exit("Claude Code (`claude`) was not found on PATH. Use the manual protocol instead.")
    questions = make_key.load_questions()[: a.limit]
    out = HERE / f"answers_{a.condition}_run{a.run}.csv"
    done = set()
    if out.exists():
        done = {int(r["id"]) for r in csv.DictReader(open(out, newline=""))}
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "mcp.json"
        name = write_config(cfg, a.condition)
        new = not out.exists()
        with open(out, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["condition", "run", "id", "answer", "declined"])
            for q in questions:
                if q["id"] in done:
                    continue
                cmd = build_command(claude or "claude", name, cfg, q["question"], a.model)
                if a.dry_run:
                    print(" ".join(f'"{c}"' if " " in c else c for c in cmd)); break
                try:
                    r = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=300)
                    answer = parse_result(r.stdout) if r.returncode == 0 else f"ERROR: {r.stderr.strip()[:200]}"
                except Exception as e:  # keep going; the row is marked and can be rerun
                    answer = f"ERROR: {type(e).__name__}: {e}"
                w.writerow([a.condition, a.run, q["id"], answer, 0]); f.flush()
                print(f"question {q['id']}: {answer.splitlines()[-1][:80] if answer else '(empty)'}")


if __name__ == "__main__":
    main()
