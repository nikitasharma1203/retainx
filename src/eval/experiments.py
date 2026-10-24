"""Compare churn models across rolling cutoffs, including baselines and a seasonality fix.

Models
  recency_rule     score = days since last order (no training). The baseline to beat.
  logistic         logistic regression, trained on the previous cutoff.
  xgb_single       XGBoost trained on the previous cutoff (what src/models/churn.py does).
  xgb_pooled       XGBoost trained on all earlier cutoffs, plus month-of-year features.
  xgb_pooled_cal   as above, but trained on all earlier cutoffs but the last, then probabilities
                   recalibrated (isotonic) on that last one.

Brier is compared with `brier_constant`: always predicting the base rate seen at the previous cutoff.
A model with Brier above that has probabilities worse than no model at all.

Usage: python -m src.eval.experiments [--horizon 90] [--cutoffs 2010-06-01,2010-09-01,...]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from src import config
from src.features import build_dataset, load_orders
from src.models.common import top_decile_lift


def _xgb():
    return XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
                         colsample_bytree=0.8, eval_metric="logloss", random_state=42)


def _logit():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(max_iter=2000))


def _add_month(X: pd.DataFrame, cutoff) -> pd.DataFrame:
    m = pd.Timestamp(cutoff).month
    X = X.copy()
    X["month_sin"] = np.sin(2 * np.pi * m / 12)
    X["month_cos"] = np.cos(2 * np.pi * m / 12)
    return X


def _snapshots(orders, cutoffs, horizon, lookback, month):
    out = []
    for c in cutoffs:
        X, y = build_dataset(orders, c, horizon, lookback, "churn")
        out.append((_add_month(X, c) if month else X, y))
    return out


def _stack(parts):
    return pd.concat([p[0] for p in parts]), pd.concat([p[1] for p in parts])


def _two_classes(*ys) -> bool:
    return all(pd.Series(y).nunique() == 2 for y in ys)


def run(orders: pd.DataFrame, cutoffs, horizon_days: int = 90, lookback: int | None = 180) -> pd.DataFrame:
    cuts = [pd.Timestamp(c) for c in cutoffs]
    h = pd.Timedelta(days=horizon_days)
    rows = []
    for i in range(1, len(cuts)):
        test = cuts[i]
        earlier = [c for c in cuts[:i] if c + h <= test]   # label windows must end before the test cutoff
        if not earlier:
            continue
        Xte, yte = build_dataset(orders, test, horizon_days, lookback, "churn")
        prev = earlier[-1]
        (Xp, yp), = _snapshots(orders, [prev], horizon_days, lookback, month=False)
        if not _two_classes(yte, yp):
            continue
        base = {
            "test_cutoff": str(test.date()), "n_test": int(len(yte)),
            "base_rate_test": float(yte.mean()),
            "brier_constant": float(((yte - yp.mean()) ** 2).mean()),
        }

        def add(model, p, calibrated_prob=True):
            rows.append({**base, "model": model,
                         "auc": float(roc_auc_score(yte, p)),
                         "brier": float(brier_score_loss(yte, p)) if calibrated_prob else np.nan,
                         "lift": top_decile_lift(yte.to_numpy(), np.asarray(p))})

        add("recency_rule", Xte["recency_days"].to_numpy(), calibrated_prob=False)
        add("logistic", _logit().fit(Xp, yp).predict_proba(Xte)[:, 1])
        add("xgb_single", _xgb().fit(Xp, yp).predict_proba(Xte)[:, 1])

        parts = _snapshots(orders, earlier, horizon_days, lookback, month=True)
        Xt = _add_month(Xte, test)
        Xs, ys = _stack(parts)
        if _two_classes(ys):
            add("xgb_pooled", _xgb().fit(Xs, ys).predict_proba(Xt)[:, 1])
        if len(parts) >= 2 and _two_classes(_stack(parts[:-1])[1], parts[-1][1]):
            Xa, ya = _stack(parts[:-1])
            model = _xgb().fit(Xa, ya)
            iso = IsotonicRegression(out_of_bounds="clip").fit(
                model.predict_proba(parts[-1][0])[:, 1], parts[-1][1])
            add("xgb_pooled_cal", iso.predict(model.predict_proba(Xt)[:, 1]))
    return pd.DataFrame(rows)


def summarise(res: pd.DataFrame) -> pd.DataFrame:
    return (res.groupby("model")[["auc", "brier", "lift"]].mean()
            .join(res.groupby("model")["brier_constant"].mean())
            .reindex(["recency_rule", "logistic", "xgb_single", "xgb_pooled", "xgb_pooled_cal"])
            .dropna(how="all"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=config.CHURN["horizon_days"])
    ap.add_argument("--cutoffs", default=",".join(config.BACKTEST_CUTOFFS))
    a = ap.parse_args()
    res = run(load_orders(), a.cutoffs.split(","), a.horizon, config.CHURN["active_lookback_days"])
    Path("reports").mkdir(exist_ok=True)
    res.to_csv("reports/experiments.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.round(3).to_string(index=False))
    print("\nMean over splits (only splits where that model could run):")
    print(summarise(res).round(3).to_string())
