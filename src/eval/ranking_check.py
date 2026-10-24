"""Does Wilson / Bayesian scoring keep new products out of the top-k and the list steadier?

For each month-start cutoff it ranks products by naive repeat rate, Wilson lower bound and a
Bayesian-shrunk rate, using only information available before that cutoff. It reports, per method:
  new_in_topk       products first sold in the last 30 days that reach the top-k (lower = steadier)
  min_buyers_topk   buyers of the least-evidenced product in the top-k (higher = better supported)
  overlap_prev      share of top-k kept from the previous month (higher = steadier)
  eligible_topk     buyers in the top-k who had not yet repeated at the cutoff (the evidence for the next column)
  future_repeat     of those, the share who made their repeat purchase in the next `horizon` days (higher = a better ranking)

Usage: python -m src.eval.ranking_check [--k 20] [--start 2010-07-01] [--end 2011-09-01] [--horizon 90]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from src import config, ranking

METHODS = ["naive", "wilson", "bayes"]


def future_repeat_table(pc: pd.DataFrame, cutoff, horizon_days: int) -> pd.DataFrame:
    """Per product: buyers not yet repeating at the cutoff, and how many repeat within the horizon."""
    t = pd.Timestamp(cutoff)
    end = t + pd.Timedelta(days=horizon_days)
    el = pc[(pc["first_purchase_ts"] < t) & (pc["second_purchase_ts"].isna() | (pc["second_purchase_ts"] >= t))].copy()
    el["converted"] = (el["second_purchase_ts"] >= t) & (el["second_purchase_ts"] < end)
    return el.groupby("stock_code").agg(eligible=("customer_id", "size"), converted=("converted", "sum"))


def evaluate(pc: pd.DataFrame, products: pd.DataFrame, cutoffs, k: int = 20, horizon_days: int = 90) -> pd.DataFrame:
    rows, prev = [], {}
    for c in cutoffs:
        st = ranking.product_stats(pc, products, c)
        fut = future_repeat_table(pc, c, horizon_days)
        for m in METHODS:
            top = st.sort_values([m, "n_customers"], ascending=False).head(k)
            ids = set(top.index)
            f = fut.reindex(top.index).fillna(0)
            rows.append({
                "cutoff": str(pd.Timestamp(c).date()), "method": m,
                "new_in_topk": int(top["is_new"].sum()),
                "min_buyers_topk": int(top["n_customers"].min()),
                "overlap_prev": len(ids & prev[m]) / k if m in prev else float("nan"),
                "eligible_topk": int(f["eligible"].sum()),
                "future_repeat": float(f["converted"].sum() / f["eligible"].sum()) if f["eligible"].sum() else float("nan"),
            })
            prev[m] = ids
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--start", default="2010-07-01")
    ap.add_argument("--end", default="2011-09-01")  # so cutoff + horizon stays inside the data
    ap.add_argument("--horizon", type=int, default=90)
    a = ap.parse_args()
    eng = create_engine(config.DB_URL)
    pc = pd.read_sql(f"select * from {config.PRODUCT_CUSTOMER_TABLE}", eng,
                     parse_dates=["first_purchase_ts", "second_purchase_ts"])
    pr = pd.read_sql(f"select stock_code, first_sale_ts from {config.PRODUCT_TABLE}", eng,
                     parse_dates=["first_sale_ts"])
    res = evaluate(pc, pr, pd.date_range(a.start, a.end, freq="MS"), a.k, a.horizon)
    Path("reports").mkdir(exist_ok=True)
    res.to_csv("reports/ranking_check.csv", index=False)
    print(res.groupby("method")[["new_in_topk", "min_buyers_topk", "overlap_prev", "eligible_topk", "future_repeat"]].mean().round(3).to_string())
    allp = [future_repeat_table(pc, c, a.horizon) for c in pd.date_range(a.start, a.end, freq="MS")]
    tot = pd.concat(allp).sum()
    print(f"\nAll products, for reference: future_repeat = {tot['converted'] / tot['eligible']:.3f}")
