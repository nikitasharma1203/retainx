import numpy as np
import pandas as pd

from src.eval.experiments import run, summarise


def synth(n=700, seed=2):
    rng = np.random.default_rng(seed)
    rows = []
    for cid in range(n):
        t = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 250)))
        lam, p = rng.gamma(2, 0.01), rng.beta(1, 6)
        while t < pd.Timestamp("2011-12-01"):
            t += pd.Timedelta(days=max(1, int(rng.exponential(1 / lam))))
            rows.append({"customer_id": cid, "invoice_id": f"{cid}-{len(rows)}", "invoice_ts": t,
                         "n_units": 3, "order_revenue": float(rng.gamma(2, 40))})
            if rng.random() < p:
                break
    return pd.DataFrame(rows)


def test_experiments_runs_and_has_expected_models():
    cuts = ["2010-06-01", "2010-09-01", "2010-12-01", "2011-03-01"]
    res = run(synth(), cuts)
    assert {"recency_rule", "logistic", "xgb_single", "xgb_pooled", "xgb_pooled_cal"} <= set(res["model"])
    assert res["auc"].between(0, 1).all()
    assert not summarise(res).empty


def test_overlapping_windows_are_skipped():
    # 60-day spacing with a 90-day horizon: no valid earlier cutoff, so nothing may run
    res = run(synth(), ["2010-06-01", "2010-07-31"], horizon_days=90)
    assert res.empty
