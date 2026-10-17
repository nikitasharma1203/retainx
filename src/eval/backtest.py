"""Rolling backtest: train on cutoff i, test on cutoff i+1.

Usage: python -m src.eval.backtest --task churn   (or propensity)
"""
import argparse

import pandas as pd

from src import config
from src.features import load_orders
from src.models import churn, propensity


def main(task: str) -> pd.DataFrame:
    orders = load_orders()
    fn = {"churn": churn.run, "propensity": propensity.run}[task]
    rows = []
    cuts = config.BACKTEST_CUTOFFS
    for tr, te in zip(cuts[:-1], cuts[1:]):
        try:
            m, _ = fn(orders, tr, te)
            rows.append({k: m[k] for k in ["train_cutoff", "test_cutoff", "n_test", "base_rate_test", "auc", "brier", "top_decile_lift"]})
        except ValueError as e:
            rows.append({"train_cutoff": tr, "test_cutoff": te, "error": str(e)})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["churn", "propensity"], default="churn")
    main(ap.parse_args().task)
