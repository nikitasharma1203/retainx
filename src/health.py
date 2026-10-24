"""Customer health score = 100 x (1 - predicted churn probability), banded into terciles.

Model: logistic regression (it matched XGBoost in the churn experiments and is readable),
trained on one earlier cutoff whose labels are fully observed before the score cutoff.
Bands are terciles of the scored population, so no arbitrary thresholds. The proof is validation:
observed churn must rise from Green to Red when labels exist.

Usage: python -m src.health --train-cutoff 2011-03-01 --score-cutoff 2011-06-01
       python -m src.health --train-cutoff 2011-06-01 --score-cutoff 2011-12-01   (live scoring, no labels yet)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config
from src.features import build_dataset, build_features, build_labels, load_orders


def _logit():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000))


def score(orders, train_cutoff, score_cutoff, horizon_days=90, lookback=180):
    """Returns (scores for active customers, standardized coefficient table, n lapsed customers)."""
    tc, sc = pd.Timestamp(train_cutoff), pd.Timestamp(score_cutoff)
    if tc + pd.Timedelta(days=horizon_days) > sc:
        raise ValueError("Training labels would overlap the scoring date. Use an earlier train cutoff.")
    Xtr, ytr = build_dataset(orders, tc, horizon_days, lookback, "churn")
    model = _logit().fit(Xtr, ytr)

    X = build_features(orders, sc)
    n_lapsed = int((X["recency_days"] > lookback).sum())
    X = X[X["recency_days"] <= lookback]
    p = model.predict_proba(X)[:, 1]
    out = pd.DataFrame({"p_churn": p}, index=X.index)
    out["health"] = np.round(100 * (1 - out["p_churn"])).astype(int)
    pct = out["p_churn"].rank(pct=True, method="first")
    out["band"] = pd.cut(pct, [0, 1 / 3, 2 / 3, 1.0], labels=["Green", "Amber", "Red"], include_lowest=True)

    coef = pd.Series(model.named_steps["logisticregression"].coef_[0], index=Xtr.columns, name="std_coef")
    coef = coef.reindex(coef.abs().sort_values(ascending=False).index).to_frame()
    return out, coef, n_lapsed


def labels_available(orders, cutoff, horizon_days=90) -> bool:
    return pd.Timestamp(cutoff) + pd.Timedelta(days=horizon_days) <= orders["invoice_ts"].max()


def validate(orders, scores, score_cutoff, horizon_days=90) -> pd.DataFrame:
    bought = build_labels(orders, score_cutoff, horizon_days)
    s = scores.copy()
    s["churned"] = (~s.index.isin(bought)).astype(int)
    return (s.groupby("band", observed=True)
            .agg(n=("churned", "size"), mean_predicted=("p_churn", "mean"), observed_churn=("churned", "mean"))
            .reindex(["Green", "Amber", "Red"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-cutoff", required=True)
    ap.add_argument("--score-cutoff", required=True)
    a = ap.parse_args()
    orders = load_orders()
    h, lb = config.CHURN["horizon_days"], config.CHURN["active_lookback_days"]
    sc, coef, n_lapsed = score(orders, a.train_cutoff, a.score_cutoff, h, lb)
    Path("reports").mkdir(exist_ok=True)
    sc.to_csv("reports/health_scores.csv")
    print(f"Scored {len(sc)} active customers; {n_lapsed} lapsed (> {lb} days) not scored.")
    print("\nStandardized coefficients (positive = raises churn risk):")
    print(coef.round(3).to_string())
    if labels_available(orders, a.score_cutoff, h):
        print("\nValidation (bands vs what actually happened):")
        print(validate(orders, sc, a.score_cutoff, h).round(3).to_string())
    else:
        print("\nNo validation: the label window runs past the end of the data.")
