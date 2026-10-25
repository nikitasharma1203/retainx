import numpy as np
import pandas as pd
import pytest

from src import pricing as pr


def simulate(true_eps=-1.4, P=80, W=90, price_follows_demand=0.0, seed=0):
    rng = np.random.default_rng(seed)
    a, g = rng.normal(3, 1, P), rng.normal(0, 0.4, W)
    b, h = rng.normal(1, 0.5, P), rng.normal(0, 0.2, W)
    rows = []
    for p in range(P):
        for w in range(W):
            u = rng.normal(0, 0.3)                               # demand shock
            lp = b[p] + h[w] + rng.normal(0, 0.15) + price_follows_demand * u
            ly = a[p] + g[w] + true_eps * lp + u
            rows.append({"stock_code": f"P{p}", "week": pd.Timestamp("2010-01-04") + pd.Timedelta(weeks=w),
                         "units": float(np.exp(ly)), "price_median": float(np.exp(lp)), "price_mean": float(np.exp(lp))})
    return pd.DataFrame(rows)


def test_recovers_a_known_elasticity_when_prices_are_exogenous():
    est = pr.estimate_elasticity(simulate(-1.4))
    assert est["elasticity"] == pytest.approx(-1.4, abs=0.15)
    assert est["ci_low"] < -1.4 < est["ci_high"] and est["se"] > 0


def test_estimate_is_biased_toward_zero_when_prices_follow_demand():
    est = pr.estimate_elasticity(simulate(-1.4, price_follows_demand=0.8))
    assert est["elasticity"] > -1.4 + 0.2      # the documented weakness of observational prices


def test_twoway_demean_removes_group_means():
    rng = np.random.default_rng(1)
    a, b = rng.integers(0, 5, 300), rng.integers(0, 7, 300)
    out = pr.twoway_demean(rng.normal(size=300) + a, a, b)
    assert abs(pd.Series(out).groupby(a).mean()).max() < 1e-6 and abs(pd.Series(out).groupby(b).mean()).max() < 1e-6


def test_revenue_effect_formula():
    assert pr.revenue_effect(-1.0, 0.10) == pytest.approx(0.0)
    assert pr.revenue_effect(-2.0, 0.10) == pytest.approx(1 / 1.1 - 1)
    assert pr.revenue_effect(-0.5, 0.10) > 0


def test_seasonal_baseline_beats_naive_on_seasonal_demand():
    weeks = 160
    base = 100 + 80 * np.sin(2 * np.pi * np.arange(weeks) / 52)
    rng = np.random.default_rng(2)
    Y = pd.DataFrame({f"p{i}": np.maximum(0, base * (1 + 0.2 * i / 10) + rng.normal(0, 5, weeks)) for i in range(10)},
                     index=pd.date_range("2010-01-04", periods=weeks, freq="7D"))
    bt = pr.backtest_baselines(Y).set_index("model")["wape"]
    assert bt["same week last year"] < bt["naive (last week)"]
    with pytest.raises(ValueError):
        pr.backtest_baselines(Y.iloc[:60])


def test_volume_discount_slope_is_recovered():
    rng = np.random.default_rng(3)
    rows = []
    for p in range(40):
        for w in range(30):
            for _ in range(6):
                q = float(rng.integers(1, 200))
                rows.append({"stock_code": f"P{p}", "invoice_ts": pd.Timestamp("2010-01-04") + pd.Timedelta(weeks=w, hours=int(rng.integers(0, 100))),
                             "quantity": q, "unit_price": float(np.exp(1 - 0.1 * np.log(q) + rng.normal(0, 0.05)))})
    out = pr.volume_discount_slope(pd.DataFrame(rows))
    assert out["slope"] == pytest.approx(-0.1, abs=0.02) and out["se"] > 0
    assert out["reverse_slope"] < 0 and out["sd_ln_quantity_within"] > out["sd_ln_price_within"]


def test_aggregating_products_makes_demand_easier_to_forecast():
    weeks = 160
    rng = np.random.default_rng(4)
    Y = pd.DataFrame({f"p{i}": rng.poisson(20, weeks).astype(float) for i in range(30)},
                     index=pd.date_range("2010-01-04", periods=weeks, freq="7D"))
    per_product = pr.backtest_baselines(Y).set_index("model")["wape"]["4-week average"]
    total = pr.backtest_baselines(Y.sum(axis=1).to_frame("total")).set_index("model")["wape"]["4-week average"]
    assert total < per_product


def _fake_elasticity_world(link=-0.03, price_noise=0.10, P=150, W=60, seed=0):
    """Demand does NOT depend on price (true elasticity 0); bigger lines just get slightly lower unit prices."""
    rng = np.random.default_rng(seed)
    pop, base = rng.uniform(0.3, 12, P), rng.normal(1.0, 0.5, P)
    rows = []
    for p in range(P):
        for w in range(W):
            n = 1 + rng.poisson(pop[p] * np.exp(rng.normal(0, 0.5)))
            q = np.maximum(1, np.round(np.exp(rng.normal(2.0, 1.2, n))))
            price = np.exp(base[p]) * q ** link * np.exp(rng.normal(0, price_noise, n))
            rows.append({"stock_code": f"P{p}", "week": pd.Timestamp("2010-01-04") + pd.Timedelta(weeks=w),
                         "units": q.sum(), "price_median": float(np.median(price)),
                         "price_mean": float((price * q).sum() / q.sum()), "n_lines": n})
    return pd.DataFrame(rows)


def test_a_tiny_quantity_price_link_fakes_a_large_elasticity():
    """The documented failure mode: with true elasticity 0, a -0.03 quantity-to-price link gives clearly negative estimates."""
    d = _fake_elasticity_world()
    assert pr.estimate_elasticity(d, min_lines=5)["elasticity"] < -1.0
    assert pr.estimate_elasticity(d, price_col="price_mean", min_lines=5)["elasticity"] < -1.5
