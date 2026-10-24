"""Does a simple recalibration fix CLV's level bias when applied out of time?

The CLV fit over-predicts purchases by a roughly constant factor at every horizon, so the problem is
the level, not compounding error. This fits the purchase-count model at several calibration dates,
measures actual / predicted purchases for customers who were active vs lapsed at that date, then
applies the PREVIOUS window's factor to the NEXT window and reports the error before and after.
Windows must be at least `horizon` days apart, so no outcome is used to correct a prediction made before it.

Usage: python -m src.eval.clv_recalibration [--horizon 180] [--cal-ends 2010-06-01,2010-12-01,2011-06-01]
       python -m src.eval.clv_recalibration --bias-by-date [--horizon 90]
          predicted / actual purchases at many calibration dates: does the bias follow the calendar?
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import load_orders
from src.models.clv import fit_count_model


def window(orders: pd.DataFrame, cal_end, horizon: int, lapse_days: int = 180):
    end = pd.Timestamp(cal_end) + pd.Timedelta(days=horizon)
    _, s, pred, chosen, _ = fit_count_model(orders, cal_end, end)
    unit = 7 if chosen["freq"] == "W" else 1
    days_since_last = (s["T_cal"] - s["recency_cal"]) * unit
    df = pd.DataFrame({"pred": np.asarray(pred), "actual": s["frequency_holdout"].to_numpy(),
                       "lapsed": (days_since_last > lapse_days).to_numpy()}, index=s.index)
    return df, chosen["model"]


def factors(df: pd.DataFrame) -> dict:
    """actual / predicted, overall and for active vs lapsed customers."""
    out = {"all": df["actual"].sum() / df["pred"].sum()}
    for name, mask in (("active", ~df["lapsed"]), ("lapsed", df["lapsed"])):
        p = df.loc[mask, "pred"].sum()
        out[name] = df.loc[mask, "actual"].sum() / p if p > 0 else np.nan
    return out


def evaluate(orders: pd.DataFrame, cal_ends, horizon: int = 180):
    cal = [pd.Timestamp(c) for c in cal_ends]
    for a, b in zip(cal[:-1], cal[1:]):
        if a + pd.Timedelta(days=horizon) > b:
            raise ValueError(f"Windows {a.date()} and {b.date()} are closer than the {horizon}-day horizon; "
                             "an outcome would leak into the next correction.")
    wins = [window(orders, c, horizon) for c in cal]
    per_window, tests = [], []
    for c, (df, model) in zip(cal, wins):
        f = factors(df)
        per_window.append({"cal_end": str(c.date()), "model": model, "active": int((~df["lapsed"]).sum()),
                           "lapsed": int(df["lapsed"].sum()),
                           "lapsed_share_of_pred": df.loc[df["lapsed"], "pred"].sum() / df["pred"].sum(),
                           "lapsed_share_of_actual": df.loc[df["lapsed"], "actual"].sum() / max(df["actual"].sum(), 1),
                           "factor_all": f["all"], "factor_active": f["active"], "factor_lapsed": f["lapsed"]})
    for i in range(1, len(cal)):
        prev, test = wins[i - 1][0], wins[i][0]
        f = factors(prev)
        f_active = f["active"] if np.isfinite(f["active"]) else f["all"]      # no history for a segment: use the overall factor
        f_lapsed = f["lapsed"] if np.isfinite(f["lapsed"]) else f["all"]
        seg = test["pred"] * np.where(test["lapsed"], f_lapsed, f_active)
        tests.append({"test_cal_end": str(cal[i].date()),
                      "pred_over_actual_before": test["pred"].sum() / test["actual"].sum(),
                      "after_one_factor": test["pred"].sum() * f["all"] / test["actual"].sum(),
                      "after_active_lapsed_factors": seg.sum() / test["actual"].sum(),
                      "corr_before": float(np.corrcoef(test["pred"], test["actual"])[0, 1]),
                      "corr_after": float(np.corrcoef(seg, test["actual"])[0, 1])})
    return pd.DataFrame(per_window), pd.DataFrame(tests)


DEFAULT_BIAS_DATES = ["2010-06-01", "2010-08-01", "2010-10-01", "2010-12-01", "2011-02-01", "2011-04-01", "2011-06-01", "2011-08-01"]


def bias_by_date(orders: pd.DataFrame, cal_ends, horizon: int = 90) -> pd.DataFrame:
    """Predicted / actual purchases for each calibration date. No correction is applied, so windows may overlap."""
    rows, last = [], orders["invoice_ts"].max()
    for c in cal_ends:
        c = pd.Timestamp(c)
        if c + pd.Timedelta(days=horizon) > last:
            rows.append({"cal_end": str(c.date()), "note": "runs past the end of the data"})
            continue
        try:
            df, model = window(orders, c, horizon)
        except RuntimeError:
            rows.append({"cal_end": str(c.date()), "note": "no valid fit"})
            continue
        rows.append({"cal_end": str(c.date()), "model": model, "customers": len(df),
                     "actual": df["actual"].sum(), "pred": df["pred"].sum(),
                     "pred_over_actual": df["pred"].sum() / df["actual"].sum(),
                     "corr": float(np.corrcoef(df["pred"], df["actual"])[0, 1])})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=None)
    ap.add_argument("--cal-ends", default="2010-06-01,2010-12-01,2011-06-01")
    ap.add_argument("--bias-by-date", action="store_true")
    a = ap.parse_args()
    if a.bias_by_date:
        t = bias_by_date(load_orders(), DEFAULT_BIAS_DATES, a.horizon or 90)
        Path("reports").mkdir(exist_ok=True)
        t.to_csv("reports/clv_bias_by_date.csv", index=False)
        pd.set_option("display.width", 200)
        print(t.round(3).to_string(index=False))
        raise SystemExit(0)
    a.horizon = a.horizon or 180
    pw, tt = evaluate(load_orders(), a.cal_ends.split(","), a.horizon)
    Path("reports").mkdir(exist_ok=True)
    pw.to_csv("reports/clv_recal_windows.csv", index=False)
    tt.to_csv("reports/clv_recal_tests.csv", index=False)
    pd.set_option("display.width", 220)
    print("Per window (factor = actual / predicted; 1.0 is perfect):")
    print(pw.round(3).to_string(index=False))
    print("\nOut-of-time test (predicted / actual; 1.0 is perfect):")
    print(tt.round(3).to_string(index=False))
