import numpy as np
import pandas as pd


def make_orders(n=700, seed=2, dropout=True, end="2011-12-01"):
    """Customers buy at a personal rate; with dropout=True each purchase may be their last."""
    rng = np.random.default_rng(seed)
    rows = []
    for cid in range(n):
        t = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 250)))
        lam = rng.gamma(2, 0.01)
        p = rng.beta(1, 6) if dropout else 0.0
        while t < pd.Timestamp(end):
            t += pd.Timedelta(days=max(1, int(rng.exponential(1 / lam))))
            rows.append({"customer_id": cid, "invoice_id": f"{cid}-{len(rows)}", "invoice_ts": t,
                         "n_units": 3, "order_revenue": float(rng.gamma(2, 40))})
            if rng.random() < p:
                break
    return pd.DataFrame(rows)
