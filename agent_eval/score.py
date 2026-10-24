"""Score agent answers against the key.

Fill answers_template.csv (copy it, e.g. answers_run1.csv): one row per condition, run and question.
  answer   the figure or name the agent gave (exactly as given)
  declined 1 if the agent said it could not answer from its tools, else 0

Numbers are correct within 0.5% (or 0.01). Months compare as year-month. Text must contain the key.
Reports counts, not just percentages: with 20 questions per condition, treat small gaps as noise.

Usage: python agent_eval/score.py [answers.csv ...]
"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def parse_number(s):
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group()) if m else None


def extract_answer(text) -> str:
    """Take the value after the last 'ANSWER:' line if present, so a whole pasted reply can be scored."""
    t = "" if text is None else str(text)
    hits = list(re.finditer(r"(?im)^\s*\**answer\**\s*:\s*(.+)$", t))
    return hits[-1].group(1).strip().strip("*") if hits else t.strip()


def judge(answer, declined, key, qtype) -> str:
    answer = extract_answer(answer) if answer is not None else None
    if answer is not None and re.match(r"(?i)^\W*decline\b", answer):
        declined = 1
    if int(declined) == 1:
        return "declined"
    if answer is None or str(answer).strip() == "" or key is None:
        return "wrong"
    if qtype == "number":
        a, k = parse_number(answer), parse_number(key)
        return "correct" if a is not None and k is not None and abs(a - k) <= max(0.005 * abs(k), 0.01) else "wrong"
    if qtype == "month":
        a = pd.to_datetime(str(answer), errors="coerce")
        k = pd.to_datetime(str(key), errors="coerce")
        return "correct" if pd.notna(a) and pd.notna(k) and a.to_period("M") == k.to_period("M") else "wrong"
    return "correct" if str(key).casefold() in str(answer).casefold() else "wrong"


def score(key: pd.DataFrame, answers: pd.DataFrame) -> pd.DataFrame:
    df = answers.merge(key, on="id", how="left")
    df["outcome"] = [judge(r.answer if pd.notna(r.answer) else None, r.declined, r.key, r.type) for r in df.itertuples()]
    return df


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    t = df.groupby(["condition", "category", "outcome"]).size().unstack(fill_value=0)
    for c in ("correct", "wrong", "declined"):
        if c not in t:
            t[c] = 0
    t = t[["correct", "wrong", "declined"]]
    t["n"] = t.sum(axis=1)
    return t


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:]] or [p for p in HERE.glob("answers*.csv") if "template" not in p.name]
    if not paths:
        sys.exit("No answers files found. Copy answers_template.csv, fill it in, and pass it as an argument.")
    ans = pd.concat([pd.read_csv(p, dtype={"answer": str}) for p in paths], ignore_index=True)
    ans["declined"] = ans["declined"].fillna(0).astype(int)
    df = score(pd.read_csv(HERE / "answer_key.csv", dtype={"key": str}), ans)
    pd.set_option("display.width", 160)
    print(summarise(df).to_string())
    tot = summarise(df).groupby("condition").sum()
    tot["correct_%"] = (100 * tot["correct"] / tot["n"]).round(0)
    tot["wrong_%"] = (100 * tot["wrong"] / tot["n"]).round(0)
    print("\nBy condition:")
    print(tot.to_string())
    df.to_csv(HERE / "scored.csv", index=False)
