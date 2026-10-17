"""Churn: among customers active in the last 180 days, who places no order in the next 90?

Usage: python -m src.models.churn --train-cutoff 2010-06-01 --test-cutoff 2010-12-01
"""
import argparse
import json
from pathlib import Path

from src import config
from src.features import load_orders
from src.models.common import train_eval


def run(orders, train_cutoff, test_cutoff):
    return train_eval(orders, train_cutoff, test_cutoff, target="churn", **config.CHURN)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-cutoff", required=True)
    ap.add_argument("--test-cutoff", required=True)
    a = ap.parse_args()
    metrics, _ = run(load_orders(), a.train_cutoff, a.test_cutoff)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/churn_metrics.json").write_text(json.dumps(metrics, indent=2))
    print({k: v for k, v in metrics.items() if k != "calibration"})
