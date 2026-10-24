"""Run the reference SQL to produce the answer key and a blank answers template.

Run after `dbt build` (question 18 reads customer_rfm, built at its default cutoff 2010-12-01).
Usage: python agent_eval/make_key.py
"""
import csv
import os
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text

HERE = Path(__file__).resolve().parent
CONDITIONS = ["raw", "documented", "metrics"]


def load_questions():
    return yaml.safe_load((HERE / "questions.yml").read_text())["questions"]


def compute_key(engine, questions):
    out = []
    with engine.connect() as c:
        for q in questions:
            row = c.execute(text(q["sql"])).fetchone()
            out.append({"id": q["id"], "category": q["category"], "type": q["type"], "question": q["question"],
                        "key": None if row is None or row[0] is None else str(row[0])})
    return out


def main():
    eng = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg2://retainx:retainx@localhost:5432/retainx"))
    key = compute_key(eng, load_questions())
    with open(HERE / "answer_key.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "category", "type", "question", "key"])
        w.writeheader(); w.writerows(key)
    with open(HERE / "answers_template.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "run", "id", "answer", "declined"])
        for cond in CONDITIONS:
            for k in key:
                w.writerow([cond, 1, k["id"], "", 0])
    missing = [k["id"] for k in key if k["key"] is None]
    print(f"Wrote answer_key.csv and answers_template.csv ({len(key)} questions).")
    if missing:
        print(f"WARNING: no reference answer for question(s) {missing}. Check the customer id or date range in questions.yml.")


if __name__ == "__main__":
    main()
