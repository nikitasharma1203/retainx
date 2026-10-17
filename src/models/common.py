"""Shared train/evaluate routine with a strict time split."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from xgboost import XGBClassifier

from src.features import build_dataset


def top_decile_lift(y_true: np.ndarray, p: np.ndarray) -> float:
    n = max(1, int(len(p) * 0.1))
    idx = np.argsort(-p)[:n]
    base = y_true.mean()
    return float(y_true[idx].mean() / base) if base > 0 else float("nan")


def train_eval(orders, train_cutoff, test_cutoff, horizon_days, active_lookback_days, target):
    train_cutoff, test_cutoff = pd.Timestamp(train_cutoff), pd.Timestamp(test_cutoff)
    if train_cutoff + pd.Timedelta(days=horizon_days) > test_cutoff:
        raise ValueError("Training labels would overlap the test period. Move test_cutoff later.")

    Xtr, ytr = build_dataset(orders, train_cutoff, horizon_days, active_lookback_days, target)
    Xte, yte = build_dataset(orders, test_cutoff, horizon_days, active_lookback_days, target)
    if ytr.nunique() < 2 or yte.nunique() < 2:
        raise ValueError("A split has a single class. Check cutoffs against the data's date range.")

    model = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
                          colsample_bytree=0.8, eval_metric="logloss", random_state=42)
    model.fit(Xtr, ytr)
    p = model.predict_proba(Xte)[:, 1]
    y = yte.to_numpy()

    frac_pos, mean_pred = calibration_curve(y, p, n_bins=10, strategy="quantile")
    return {
        "target": target,
        "train_cutoff": str(train_cutoff.date()),
        "test_cutoff": str(test_cutoff.date()),
        "n_train": int(len(ytr)),
        "n_test": int(len(yte)),
        "base_rate_test": float(y.mean()),
        "auc": float(roc_auc_score(y, p)),
        "avg_precision": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "top_decile_lift": top_decile_lift(y, p),
        "calibration": [{"mean_pred": float(a), "observed": float(b)} for a, b in zip(mean_pred, frac_pos)],
    }, model
