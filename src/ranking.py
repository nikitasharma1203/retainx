"""Stable top-products ranking and cold-start simulation.

Signal: repeat-purchase rate = share of a product's buyers who bought it on 2+ separate
invoices. Online Retail II has no ratings, so this binary outcome stands in for "satisfied".
Wilson lower bound and Bayesian shrinkage stop a new product with a handful of buyers
from jumping to the top on noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def wilson_lower_bound(successes, n, z: float = 1.96):
    successes, n = np.asarray(successes, float), np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = successes / n
        denom = 1 + z**2 / n
        centre = p + z**2 / (2 * n)
        margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
        out = (centre - margin) / denom
    return np.where(n > 0, out, 0.0)


def bayesian_rate(successes, n, prior_mean: float, prior_strength: float = 20.0):
    """Shrink toward the catalogue average. prior_strength = pseudo-customers."""
    successes, n = np.asarray(successes, float), np.asarray(n, float)
    return (successes + prior_mean * prior_strength) / (n + prior_strength)


def product_stats(pc: pd.DataFrame, products: pd.DataFrame, cutoff) -> pd.DataFrame:
    """Per-product stats as of `cutoff`, using only information available before it.

    pc: stock_code, customer_id, first_purchase_ts, second_purchase_ts (NaT if bought once).
    products: stock_code, first_sale_ts.
    A buyer counts as a repeater only if their SECOND purchase happened before the cutoff.
    """
    cutoff = pd.Timestamp(cutoff)
    seen = pc[pc["first_purchase_ts"] < cutoff].copy()
    seen["is_repeater"] = seen["second_purchase_ts"] < cutoff   # NaT compares False
    st = seen.groupby("stock_code").agg(n_customers=("customer_id", "nunique"),
                                        n_repeaters=("is_repeater", "sum"))
    st["n_repeaters"] = st["n_repeaters"].astype(int)
    st = st.join(products.set_index("stock_code")["first_sale_ts"])
    st["is_new"] = st["first_sale_ts"] >= cutoff - pd.Timedelta(days=30)
    prior = st["n_repeaters"].sum() / max(st["n_customers"].sum(), 1)
    st["naive"] = st["n_repeaters"] / st["n_customers"]
    st["wilson"] = wilson_lower_bound(st["n_repeaters"], st["n_customers"])
    st["bayes"] = bayesian_rate(st["n_repeaters"], st["n_customers"], prior)
    return st


def new_in_topk(st: pd.DataFrame, k: int = 20) -> pd.Series:
    """How many new products land in the top-k under each method (lower = steadier)."""
    return pd.Series({m: int(st.sort_values(m, ascending=False).head(k)["is_new"].sum())
                      for m in ["naive", "wilson", "bayes"]})


def rank_displacement(a: pd.Series, b: pd.Series, k: int = 20) -> float:
    """Mean absolute rank change of items in the top-k of `a` between rankings a and b."""
    ra, rb = a.rank(ascending=False), b.rank(ascending=False)
    top = ra[ra <= k].index.intersection(rb.index)
    return float((ra[top] - rb[top]).abs().mean())
