"""Leakage-safe feature and label building.

Rule: features use only orders strictly BEFORE the cutoff. Labels use only orders
in [cutoff, cutoff + horizon). Every function takes the cutoff explicitly.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine

from src import config


def load_orders(engine=None, table: str | None = None) -> pd.DataFrame:
    engine = engine or create_engine(config.DB_URL)
    q = f"select customer_id, invoice_id, invoice_ts, n_units, order_revenue from {table or config.ORDERS_TABLE}"
    return pd.read_sql(q, engine, parse_dates=["invoice_ts"])


def build_features(orders: pd.DataFrame, cutoff) -> pd.DataFrame:
    cutoff = pd.Timestamp(cutoff)
    hist = orders[orders["invoice_ts"] < cutoff]
    g = hist.groupby("customer_id")
    f = g.agg(
        first_order=("invoice_ts", "min"),
        last_order=("invoice_ts", "max"),
        frequency=("invoice_id", "nunique"),
        monetary=("order_revenue", "sum"),
        avg_order_value=("order_revenue", "mean"),
        avg_units=("n_units", "mean"),
    )
    f["recency_days"] = (cutoff - f["last_order"]).dt.days
    f["tenure_days"] = (cutoff - f["first_order"]).dt.days
    span = (f["last_order"] - f["first_order"]).dt.days
    f["avg_gap_days"] = span / (f["frequency"] - 1)
    f.loc[f["frequency"] < 2, "avg_gap_days"] = float("nan")

    d = pd.Timedelta(days=90)
    recent = hist[hist["invoice_ts"] >= cutoff - d].groupby("customer_id")
    prev = hist[(hist["invoice_ts"] >= cutoff - 2 * d) & (hist["invoice_ts"] < cutoff - d)].groupby("customer_id")
    f["orders_last_90d"] = recent["invoice_id"].nunique()
    f["revenue_last_90d"] = recent["order_revenue"].sum()
    f["orders_prev_90d"] = prev["invoice_id"].nunique()
    for c in ["orders_last_90d", "revenue_last_90d", "orders_prev_90d"]:
        f[c] = f[c].fillna(0)
    f["orders_trend"] = f["orders_last_90d"] - f["orders_prev_90d"]
    return f.drop(columns=["first_order", "last_order"])


def build_labels(orders: pd.DataFrame, cutoff, horizon_days: int) -> set:
    """Customers with at least one order in [cutoff, cutoff + horizon)."""
    cutoff = pd.Timestamp(cutoff)
    end = cutoff + pd.Timedelta(days=horizon_days)
    fut = orders[(orders["invoice_ts"] >= cutoff) & (orders["invoice_ts"] < end)]
    return set(fut["customer_id"].unique())


def build_dataset(orders, cutoff, horizon_days, active_lookback_days=None, target="purchase"):
    """Returns (X, y). target='purchase' -> 1 if bought in the horizon; 'churn' -> 1 if NOT."""
    X = build_features(orders, cutoff)
    if active_lookback_days is not None:
        X = X[X["recency_days"] <= active_lookback_days]
    bought = build_labels(orders, cutoff, horizon_days)
    y = pd.Series(X.index.isin(bought).astype(int), index=X.index, name="bought")
    if target == "churn":
        y = (1 - y).rename("churned")
    return X, y
