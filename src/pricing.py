"""Exploratory price elasticity and demand baselines from Online Retail II.

Elasticity: ln(units) on ln(price) per product-week, with product and week fixed effects and standard errors
clustered by product. The price is the product's median unit price that week (a list-price proxy).

READ THIS BEFORE USING THE NUMBERS. Prices here were not set at random:
  * prices move with promotions, clearance, season and stock, which also move demand, so the estimate is biased
    (usually toward zero: tests/test_pricing.py shows the effect on simulated data);
  * the same product is sold at different prices to retail and wholesale buyers, and the mix changes by week;
  * weeks with few sales lines give a noisier median price, which ties the price measure to volume. That is
    an artifact, so product-weeks with fewer than `min_lines` lines are dropped and the CLI prints a sensitivity table;
  * only products whose price actually changes contribute any information.
Treat the output as exploratory, never as a basis for a price change without a controlled test.

Usage: python -m src.pricing [--top-n 50]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from src import config


def load_sales(engine=None) -> pd.DataFrame:
    engine = engine or create_engine(config.DB_URL)
    df = pd.read_sql("select stock_code, invoice_ts, quantity, unit_price from analytics.int_valid_sales",
                     engine, parse_dates=["invoice_ts"])
    df["unit_price"] = df["unit_price"].astype(float)
    return df


def _week(ts: pd.Series) -> pd.Series:
    return ts.dt.to_period("W").dt.start_time


def weekly_panel(sales: pd.DataFrame) -> pd.DataFrame:
    s = sales.assign(week=_week(sales["invoice_ts"]), value=sales["quantity"] * sales["unit_price"])
    g = s.groupby(["stock_code", "week"])
    panel = g.agg(units=("quantity", "sum"), price_median=("unit_price", "median"), value=("value", "sum"),
                  n_lines=("quantity", "size"))
    panel["price_mean"] = panel["value"] / panel["units"]
    return panel.drop(columns="value").reset_index()


def twoway_demean(v, a, b, tol: float = 1e-9, max_iter: int = 200) -> np.ndarray:
    """Remove two sets of fixed effects from an unbalanced panel by alternating projections."""
    v = np.asarray(v, float).copy()
    ca, cb = pd.factorize(a)[0], pd.factorize(b)[0]
    for _ in range(max_iter):
        before = v.copy()
        for codes in (ca, cb):
            v -= (np.bincount(codes, weights=v) / np.bincount(codes))[codes]
        if np.abs(v - before).max() < tol:
            break
    return v


def estimate_elasticity(panel: pd.DataFrame, price_col: str = "price_median", min_weeks: int = 20, min_lines: int = 5) -> dict:
    d = panel[(panel["units"] > 0) & (panel[price_col] > 0)]
    if "n_lines" in d:
        d = d[d["n_lines"] >= min_lines]
    d = d[d.groupby("stock_code")["week"].transform("size") >= min_weeks]
    d = d[d.groupby("stock_code")[price_col].transform("nunique") >= 2]
    if d["stock_code"].nunique() < 10:
        return {"elasticity": np.nan, "se": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                "n_obs": len(d), "n_products": int(d["stock_code"].nunique())}
    xt = twoway_demean(np.log(d[price_col]), d["stock_code"], d["week"])
    yt = twoway_demean(np.log(d["units"]), d["stock_code"], d["week"])
    sxx = (xt ** 2).sum()
    beta = (xt * yt).sum() / sxx
    resid = yt - beta * xt
    scores = pd.Series(xt * resid).groupby(d["stock_code"].to_numpy()).sum()
    G = len(scores)
    se = float(np.sqrt(G / (G - 1) * (scores ** 2).sum()) / sxx)
    return {"elasticity": float(beta), "se": se, "ci_low": float(beta - 1.96 * se), "ci_high": float(beta + 1.96 * se),
            "n_obs": int(len(d)), "n_products": int(G)}


def volume_discount_slope(sales: pd.DataFrame, min_lines: int = 2) -> dict:
    """Within the same product and week, do bigger lines get lower unit prices?

    Slope of ln(unit price) on ln(quantity), demeaned within product-week, clustered by product.
    A clearly negative slope means volume discounts exist, so any price measure that weights by quantity
    is mechanically linked to units sold, which would bias the elasticity toward more negative values.
    """
    d = sales[(sales["quantity"] > 0) & (sales["unit_price"] > 0)].copy()
    d["week"] = _week(d["invoice_ts"])
    d["lp"], d["lq"] = np.log(d["unit_price"]), np.log(d["quantity"])
    grp = d.groupby(["stock_code", "week"])
    d = d[grp["lp"].transform("size") >= min_lines]
    grp = d.groupby(["stock_code", "week"])
    lp_t = d["lp"] - grp["lp"].transform("mean")
    lq_t = d["lq"] - grp["lq"].transform("mean")
    sxx = float((lq_t ** 2).sum())
    beta = float((lq_t * lp_t).sum() / sxx)
    scores = ((lq_t * (lp_t - beta * lq_t)).groupby(d["stock_code"]).sum())
    G = len(scores)
    return {"slope": beta, "se": float(np.sqrt(G / (G - 1) * (scores ** 2).sum()) / sxx),
            "n_lines": int(len(d)), "n_products": int(G)}


def revenue_effect(elasticity: float, price_change: float) -> float:
    """Constant-elasticity revenue change for a price change (+0.10 = +10%). -1 means unit elastic."""
    return (1 + price_change) ** (1 + elasticity) - 1


def scenarios(est: dict, changes=(-0.10, -0.05, 0.05, 0.10)) -> pd.DataFrame:
    return pd.DataFrame([{"price_change": c,
                          "revenue_change_point": revenue_effect(est["elasticity"], c),
                          "revenue_change_at_ci_low": revenue_effect(est["ci_low"], c),
                          "revenue_change_at_ci_high": revenue_effect(est["ci_high"], c)} for c in changes])


def by_price_tercile(panel: pd.DataFrame, **kw) -> pd.DataFrame:
    prod = panel.groupby("stock_code")["price_median"].median()
    tier = pd.qcut(prod, 3, labels=["low price", "mid price", "high price"])
    rows = []
    for name in tier.cat.categories:
        sub = panel[panel["stock_code"].isin(tier.index[tier == name])]
        rows.append({"group": name, **estimate_elasticity(sub, **kw)})
    return pd.DataFrame(rows)


# ---- demand baselines -------------------------------------------------------
def weekly_units_matrix(sales: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    s = sales.assign(week=_week(sales["invoice_ts"]))
    top = s.groupby("stock_code")["quantity"].sum().nlargest(top_n).index
    m = s[s["stock_code"].isin(top)].pivot_table(index="week", columns="stock_code", values="quantity",
                                                  aggfunc="sum", fill_value=0)
    return m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="7D"), fill_value=0)


def backtest_baselines(Y: pd.DataFrame, horizon: int = 4, test_weeks: int = 26, season: int = 52) -> pd.DataFrame:
    """Rolling-origin forecasts of weekly units `horizon` weeks ahead, scored on the last `test_weeks` weeks."""
    A, T = Y.to_numpy(float), len(Y)
    if T < season + test_weeks + horizon:
        raise ValueError("Not enough weeks for a seasonal backtest.")
    preds = {"naive (last week)": [], "4-week average": [], "same week last year": [], "average of the last two": []}
    actual = []
    for tgt in range(T - test_weeks, T):
        t = tgt - horizon
        ma4, sn = A[t - 3:t + 1].mean(axis=0), A[tgt - season]
        preds["naive (last week)"].append(A[t]); preds["4-week average"].append(ma4)
        preds["same week last year"].append(sn); preds["average of the last two"].append(0.5 * (ma4 + sn))
        actual.append(A[tgt])
    act = np.array(actual)
    return pd.DataFrame([{"model": k, "wape": np.abs(np.array(v) - act).sum() / act.sum(),
                          "bias": np.array(v).sum() / act.sum() - 1} for k, v in preds.items()])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=50)
    a = ap.parse_args()
    sales = load_sales()
    panel = weekly_panel(sales)
    Path("reports").mkdir(exist_ok=True)
    pd.set_option("display.width", 200)

    print(f"Panel: {panel['stock_code'].nunique()} products, {len(panel):,} product-weeks\n")
    rows = [{"group": "all products (median price)", **estimate_elasticity(panel)},
            {"group": "all products (mean price)", **estimate_elasticity(panel, price_col="price_mean")}]
    el = pd.concat([pd.DataFrame(rows), by_price_tercile(panel)], ignore_index=True)
    el.to_csv("reports/pricing_elasticity.csv", index=False)
    print("Price elasticity of demand (fixed effects, clustered SE). EXPLORATORY: see the caveats in src/pricing.py")
    print(el.round(3).to_string(index=False))

    vd = volume_discount_slope(sales)
    print(f"\nVolume-discount check (same product, same week): ln(price) on ln(quantity) slope = {vd['slope']:.3f} "
          f"(se {vd['se']:.3f}, {vd['n_lines']:,} lines, {vd['n_products']:,} products). "
          "Negative = bigger lines get lower prices, which mechanically links price to units.")

    sens = pd.DataFrame([{"min_lines_per_product_week": m, **estimate_elasticity(panel, min_lines=m)} for m in (1, 5, 10, 20)])
    sens.to_csv("reports/pricing_sensitivity.csv", index=False)
    print("\nSensitivity to the minimum number of sales lines per product-week (a stable estimate is more credible):")
    print(sens.round(3).to_string(index=False))

    main_est = el.iloc[0].to_dict()
    if np.isfinite(main_est["elasticity"]):
        sc = scenarios(main_est)
        sc.to_csv("reports/pricing_scenarios.csv", index=False)
        print("\nWhat the estimate would imply for revenue (constant elasticity, other things equal):")
        print(sc.round(3).to_string(index=False))

    Y = weekly_units_matrix(sales, a.top_n)
    bt = backtest_baselines(Y)
    bt.to_csv("reports/demand_baselines.csv", index=False)
    print(f"\nDemand baselines, top {a.top_n} products, 4 weeks ahead, last 26 weeks (WAPE: lower is better):")
    print(bt.round(3).to_string(index=False))
    bt_total = backtest_baselines(Y.sum(axis=1).to_frame("total"))
    bt_total.to_csv("reports/demand_baselines_total.csv", index=False)
    print("\nSame baselines on the TOTAL of those products (aggregation removes most of the lumpiness):")
    print(bt_total.round(3).to_string(index=False))
