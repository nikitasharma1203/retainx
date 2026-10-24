import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_eval"))
import make_key  # noqa: E402
import score  # noqa: E402

from src import config  # noqa: E402


def _db_ok():
    try:
        with create_engine(config.DB_URL).connect() as c:
            c.execute(text("select count(*) from analytics.fct_orders"))
        return True
    except Exception:
        return False


def test_question_set_shape():
    qs = make_key.load_questions()
    assert [q["id"] for q in qs] == list(range(1, 21))
    cats = [q["category"] for q in qs]
    assert (cats.count("metric"), cats.count("lookup"), cats.count("out_of_scope")) == (12, 3, 5)
    assert {q["type"] for q in qs} <= {"number", "month", "text"}


def test_judging_rules():
    j = score.judge
    assert j("£8,887,123.40", 0, "8887123.45", "number") == "correct"
    assert j("8.9 million", 0, "8887123.45", "number") == "wrong"
    assert j("November 2011", 0, "2011-11", "month") == "correct"
    assert j("2011-10", 0, "2011-11", "month") == "wrong"
    assert j("It is United Kingdom.", 0, "United Kingdom", "text") == "correct"
    assert j("", 1, "5", "number") == "declined"
    assert j(None, 0, "5", "number") == "wrong"


def test_summary_counts():
    import pandas as pd
    key = pd.DataFrame({"id": [1, 2], "category": ["metric", "metric"], "type": ["number", "number"], "question": ["a", "b"], "key": ["10", "20"]})
    ans = pd.DataFrame({"condition": ["raw", "raw"], "run": [1, 1], "id": [1, 2], "answer": ["10", "99"], "declined": [0, 0]})
    t = score.summarise(score.score(key, ans))
    assert t.loc[("raw", "metric"), "correct"] == 1 and t.loc[("raw", "metric"), "wrong"] == 1


@pytest.mark.skipif(not _db_ok(), reason="needs the retainx database")
def test_every_reference_query_runs():
    key = make_key.compute_key(create_engine(config.DB_URL), make_key.load_questions())
    assert len(key) == 20
    assert key[0]["key"] is not None      # revenue in 2010 must exist


def test_scorer_reads_the_answer_line_and_declines():
    j = score.judge
    reply = "I summed the lines and got 8,887,123.45 revenue.\nANSWER: 8,887,123.45"
    assert j(reply, 0, "8887123.45", "number") == "correct"
    assert j("Cannot be answered from these tools.\nANSWER: DECLINE", 0, "5", "number") == "declined"
    assert j("**ANSWER:** United Kingdom", 0, "United Kingdom", "text") == "correct"
    assert score.extract_answer("no marker here") == "no marker here"


def test_runner_builds_a_restricted_command_and_config(tmp_path):
    import json
    import run_claude_code as rc
    name = rc.write_config(tmp_path / "m.json", "raw", python="py", env={"PYTHONPATH": "x", "DATABASE_URL": "y"})
    cfg = json.loads((tmp_path / "m.json").read_text())
    assert list(cfg["mcpServers"]) == [name] == ["retainx-raw"]
    cmd = rc.build_command("claude", name, tmp_path / "m.json", "How many orders?", "some-model")
    assert "--strict-mcp-config" in cmd and cmd[cmd.index("--allowedTools") + 1] == "mcp__retainx-raw"
    assert "How many orders?" in cmd[2] and "ANSWER:" in cmd[2] and cmd[-2:] == ["--model", "some-model"]
    assert rc.parse_result(json.dumps({"result": " hi "})) == "hi"
