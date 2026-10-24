"""CLV with BG/NBD (purchase count) + Gamma-Gamma (order value), checked on a holdout period.

BG/NBD often fits a < 1 on data where many customers never seem to drop out. Its expected-purchases
formula is invalid there and returns inf or negative values. So every fit is validated, and when
BG/NBD is invalid the code falls back to Pareto/NBD, which has no such restriction. Every attempt
is printed. If nothing is valid it raises instead of returning inf.

Usage: python -m src.models.clv --calibration-end 2010-12-01 --observation-end 2011-12-01
       python -m src.models.clv --calibration-end 2010-12-01 --horizons 90,180,365   (does over-prediction grow with the horizon?)
Note: lifetimes counts at most one purchase per time unit, so same-day invoices collapse.
"""
import argparse
import contextlib
import io
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import load_orders

# (model, time unit, penalizer). Stronger penalizers push BG/NBD's `a` further below 1, so they are not tried.
ATTEMPTS = [("bgnbd", "D", 0.001), ("bgnbd", "W", 0.001), ("pareto", "D", 0.001), ("pareto", "W", 0.001)]


def _summary(orders, calibration_end, observation_end, freq):
    from lifetimes.utils import calibration_and_holdout_data
    return calibration_and_holdout_data(
        orders, "customer_id", "invoice_ts",
        calibration_period_end=pd.Timestamp(calibration_end),
        observation_period_end=pd.Timestamp(observation_end),
        freq=freq, monetary_value_col="order_revenue",
    )


def fit_count_model(orders, calibration_end, observation_end, attempts=ATTEMPTS):
    """Returns (model, summary, predicted purchases, chosen attempt, full attempt log)."""
    from lifetimes import BetaGeoFitter, ParetoNBDFitter
    from lifetimes.utils import ConvergenceError

    log = []
    for model_name, freq, pen in attempts:
        rec = {"model": model_name, "freq": freq, "penalizer": pen, "ok": False, "note": ""}
        try:
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                warnings.simplefilter("ignore", RuntimeWarning)
                s = _summary(orders, calibration_end, observation_end, freq)
                m = (BetaGeoFitter if model_name == "bgnbd" else ParetoNBDFitter)(penalizer_coef=pen)
                m.fit(s["frequency_cal"], s["recency_cal"], s["T_cal"])
                p = m.params_
                rec.update({k: float(v) for k, v in p.items()})
                pred = m.conditional_expected_number_of_purchases_up_to_time(
                    s["duration_holdout"], s["frequency_cal"], s["recency_cal"], s["T_cal"])
            valid = bool(np.isfinite(p).all() and (p > 0).all()
                         and np.isfinite(pred).all() and (pred >= 0).all())
            if model_name == "bgnbd" and valid and p["a"] <= 1:
                valid = False
                rec["note"] = "a <= 1: expected-purchases formula is invalid"
            rec["ok"] = valid
            if not valid and not rec["note"]:
                rec["note"] = "invalid parameters or non-finite predictions"
        except ConvergenceError:
            rec["note"] = "did not converge"
        except Exception as e:  # keep trying other settings
            rec["note"] = f"{type(e).__name__}: {e}"[:80]
        log.append(rec)
        if rec["ok"]:
            return m, s, pred, rec, log
    raise RuntimeError("No valid purchase-count fit. Attempts:\n" + pd.DataFrame(log).to_string(index=False))


def run(orders: pd.DataFrame, calibration_end, observation_end, attempts=ATTEMPTS) -> dict:
    from lifetimes import GammaGammaFitter

    _, s, pred, chosen, log = fit_count_model(orders, calibration_end, observation_end, attempts)
    s["pred_purchases"] = pred
    out = {
        "fit": chosen, "attempts": log,
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


def horizon_table(orders: pd.DataFrame, calibration_end, horizons=(90, 180, 365)) -> pd.DataFrame:
    """Same fit-and-check at several holdout lengths. A ratio of 1.0 means totals match."""
    rows = []
    last = orders["invoice_ts"].max()
    for h in horizons:
        end = pd.Timestamp(calibration_end) + pd.Timedelta(days=int(h))
        if end > last:
            rows.append({"horizon_days": h, "note": "runs past the end of the data"})
            continue
        try:
            r = run(orders, calibration_end, end)
        except RuntimeError:
            rows.append({"horizon_days": h, "note": "no valid fit"})
            continue
        rows.append({
            "horizon_days": h, "model": r["fit"]["model"], "customers": r["n_customers"],
            "purchases_actual": r["purchases_actual_total"], "purchases_pred": r["purchases_pred_total"],
            "purchases_ratio": r["purchases_pred_total"] / r["purchases_actual_total"],
            "purchases_corr": r["purchases_corr"],
            "spend_ratio": r["spend_pred_total"] / r["spend_actual_total"], "spend_corr": r["spend_corr"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibration-end", required=True)
    ap.add_argument("--observation-end")
    ap.add_argument("--horizons", help="comma-separated days, e.g. 90,180,365")
    a = ap.parse_args()
    if a.horizons:
        t = horizon_table(load_orders(), a.calibration_end, [int(x) for x in a.horizons.split(",")])
        Path("reports").mkdir(exist_ok=True)
        t.to_csv("reports/clv_horizons.csv", index=False)
        print(t.round(3).to_string(index=False))
        raise SystemExit(0)
    if not a.observation_end:
        raise SystemExit("Give --observation-end or --horizons")
    try:
        res = run(load_orders(), a.calibration_end, a.observation_end)
    except RuntimeError as e:
        raise SystemExit(str(e))
    Path("reports").mkdir(exist_ok=True)
    Path("reports/clv_metrics.json").write_text(json.dumps(res, indent=2))
    print("Fit attempts:")
    print(pd.DataFrame(res["attempts"]).round(4).to_string(index=False))
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items() if k not in ("attempts", "fit")})
