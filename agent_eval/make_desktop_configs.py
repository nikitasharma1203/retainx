"""Write Claude Desktop MCP configs for each evaluation condition, using THIS machine's paths.

Usage: python agent_eval/make_desktop_configs.py     (with DATABASE_URL set, inside your venv)

Writes agent_eval/desktop_configs/claude_desktop_config_<condition>.json (add that folder to .gitignore).
For each condition: back up your current Claude Desktop config, copy ONE file over it, fully quit and reopen Claude Desktop.
  Windows config: %APPDATA%\\Claude\\claude_desktop_config.json
  macOS config:   ~/Library/Application Support/Claude/claude_desktop_config.json
Only one condition's server should be connected at a time.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from run_claude_code import SERVERS  # noqa: E402


def write_configs(out_dir: Path, python: str = sys.executable, env: dict | None = None) -> list[Path]:
    env = env or {"PYTHONPATH": str(ROOT), "DATABASE_URL": os.environ.get("DATABASE_URL", "")}
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for condition, (name, args) in SERVERS.items():
        path = out_dir / f"claude_desktop_config_{condition}.json"
        path.write_text(json.dumps({"mcpServers": {name: {"command": python, "args": args, "env": env}}}, indent=2))
        paths.append(path)
    return paths


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("WARNING: DATABASE_URL is not set, so the configs will have an empty database URL. Set it first (see the README).")
    for p in write_configs(HERE / "desktop_configs"):
        print("wrote", p)
    print("\nWindows example for one condition:")
    print('  copy "%APPDATA%\\Claude\\claude_desktop_config.json" "%APPDATA%\\Claude\\claude_desktop_config.backup.json"')
    print('  copy agent_eval\\desktop_configs\\claude_desktop_config_raw.json "%APPDATA%\\Claude\\claude_desktop_config.json"')
    print("Then fully quit and reopen Claude Desktop. Repeat with _documented and _metrics for the other conditions.")
