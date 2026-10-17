import numpy as np
import pandas as pd

from src.features import build_dataset, build_features, build_labels
from src.ranking import bayesian_rate, wilson_lower_bound


def make_orders(seed=0, n_customers=300):
    rng = np.random.default_rng(seed)
    rows = []
    for cid in range(n_customers):
        start = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 200)))
        t = start
        for _ in range(int(rng.integers(1, 12))):
            t = t + pd.Timedelta(days=int(rng.integers(5, 90)))
            rows.append({"customer_id": cid, "invoice_id": f"{cid}-{len(rows)}", "invoice_ts": t,
                         "n_units": int(rng.integers(1, 20)), "order_revenue": float(rng.gamma(2, 40))})
    return pd.DataFrame(rows)


def test_features_ignore_future_data():
    orders = make_orders()
    cutoff = pd.Timestamp("2010-09-01")
    full = build_features(orders, cutoff)
    truncated = build_features(orders[orders["invoice_ts"] < cutoff], cutoff)
    pd.testing.assert_frame_equal(full.sort_index(), truncated.sort_index())


def test_labels_only_use_horizon_window():
    orders = make_orders()
    cutoff = pd.Timestamp("2010-09-01")
    got = build_labels(orders, cutoff, 30)
    win = orders[(orders.invoice_ts >= cutoff) & (orders.invoice_ts < cutoff + pd.Timedelta(days=30))]
    assert got == set(win.customer_id)


def test_churn_label_is_inverse_of_purchase():
    orders = make_orders()
    cutoff = "2010-09-01"
    _, y_buy = build_dataset(orders, cutoff, 90, 180, "purchase")
    _, y_churn = build_dataset(orders, cutoff, 90, 180, "churn")
    assert (y_buy + y_churn == 1).all()


def test_wilson_penalises_small_samples():
    # 3 of 3 repeaters should rank below 80 of 100.
    small = wilson_lower_bound(3, 3)
    large = wilson_lower_bound(80, 100)
    assert small < large


def test_bayes_shrinks_toward_prior():
    shrunk = bayesian_rate(3, 3, prior_mean=0.3, prior_strength=20)
    assert 0.3 < shrunk < 1.0
