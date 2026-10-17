"""CLV with BG/NBD (purchase count) + Gamma-Gamma (order value), checked on a holdout period.

Usage: python -m src.models.clv --calibration-end 2010-12-01 --observation-end 2011-12-01

Note: lifetimes counts at most one purchase per day, so same-day invoices collapse.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import load_orders


def _fit_bgnbd(s, BetaGeoFitter, penalizers=(0.001, 0.01, 0.1)):
    """BG/NBD can fail to converge on sparse data. Retry with a stronger penalizer."""
    from lifetimes.utils import ConvergenceError
    last = None
    for pen in penalizers:
        try:
            m = BetaGeoFitter(penalizer_coef=pen)
            m.fit(s["frequency_cal"], s["recency_cal"], s["T_cal"])
            return m
        except ConvergenceError as e:
            last = e
    raise last


def run(orders: pd.DataFrame, calibration_end, observation_end) -> dict:
    from lifetimes import BetaGeoFitter, GammaGammaFitter
    from lifetimes.utils import calibration_and_holdout_data

    s = calibration_and_holdout_data(
        orders, "customer_id", "invoice_ts",
        calibration_period_end=pd.Timestamp(calibration_end),
        observation_period_end=pd.Timestamp(observation_end),
        freq="D", monetary_value_col="order_revenue",
    )
    bgf = _fit_bgnbd(s, BetaGeoFitter)
    s["pred_purchases"] = bgf.conditional_expected_number_of_purchases_up_to_time(
        s["duration_holdout"], s["frequency_cal"], s["recency_cal"], s["T_cal"])

    out = {
        "n_customers": int(len(s)),
        "purchases_actual_total": float(s["frequency_holdout"].sum()),
        "purchases_pred_total": float(s["pred_purchases"].sum()),
        "purchases_mae": float((s["pred_purchases"] - s["frequency_holdout"]).abs().mean()),
        "purchases_corr": float(np.corrcoef(s["pred_purchases"], s["frequency_holdout"])[0, 1]),
    }

    rep = s[(s["frequency_cal"] > 0) & (s["monetary_value_cal"] > 0)].copy()
    out["freq_monetary_corr"] = float(rep["frequency_cal"].corr(rep["monetary_value_cal"]))  # Gamma-Gamma assumes ~0
    ggf = GammaGammaFitter(penalizer_coef=0.001)
    ggf.fit(rep["frequency_cal"], rep["monetary_value_cal"])
    rep["pred_avg_value"] = ggf.conditional_expected_average_profit(rep["frequency_cal"], rep["monetary_value_cal"])
    rep["pred_spend"] = rep["pred_purchases"] * rep["pred_avg_value"]
    rep["actual_spend"] = rep["frequency_holdout"] * rep["monetary_value_holdout"]
    out["spend_actual_total"] = float(rep["actual_spend"].sum())
    out["spend_pred_total"] = float(rep["pred_spend"].sum())
    out["spend_corr"] = float(np.corrcoef(rep["pred_spend"], rep["actual_spend"])[0, 1])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration-end", required=True)
    ap.add_argument("--observation-end", required=True)
    a = ap.parse_args()
    res = run(load_orders(), a.calibration_end, a.observation_end)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/clv_metrics.json").write_text(json.dumps(res, indent=2))
    print(res)
