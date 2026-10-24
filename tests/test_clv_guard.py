import numpy as np
import pytest

from src.models import clv
from tests.synth import make_orders


def _all_finite(res):
    return all(np.isfinite(v) for k, v in res.items() if isinstance(v, float))


def test_clv_returns_finite_numbers_on_data_with_dropout():
    res = clv.run(make_orders(1500, seed=3), "2010-12-01", "2011-12-01")
    assert _all_finite(res)
    assert res["fit"]["ok"] and res["fit"]["model"] in {"bgnbd", "pareto"}


def test_bgnbd_with_a_below_one_is_rejected_and_pareto_is_used():
    # This dataset fits BG/NBD with a < 1 (formula invalid), so the fallback must take over.
    res = clv.run(make_orders(1500, seed=3), "2010-12-01", "2011-12-01")
    first = res["attempts"][0]
    assert first["model"] == "bgnbd" and not first["ok"] and first["a"] <= 1
    assert res["fit"]["model"] == "pareto"


def test_clv_never_returns_infinite_values_silently():
    # No dropout at all: BG/NBD may not fit. It must raise or return finite values, never inf.
    orders = make_orders(800, seed=4, dropout=False)
    try:
        res = clv.run(orders, "2010-12-01", "2011-12-01", attempts=[("bgnbd", "D", 0.001)])
    except RuntimeError as e:
        assert "Attempts" in str(e)
    else:
        assert _all_finite(res)


def test_horizon_table_reports_ratios_and_flags_past_end_of_data():
    orders = make_orders(1500, seed=3)
    orders = orders[orders["invoice_ts"] < "2011-12-01"]
    t = clv.horizon_table(orders, "2010-12-01", [90, 180, 900])
    assert list(t["horizon_days"]) == [90, 180, 900]
    ok = t.dropna(subset=["purchases_ratio"])
    assert len(ok) == 2 and np.isfinite(ok["purchases_ratio"]).all()
    assert t.loc[t["horizon_days"] == 900, "note"].iloc[0] == "runs past the end of the data"


def test_recalibration_runs_and_rejects_overlapping_windows():
    import pytest
    from src.eval import clv_recalibration as cr
    orders = make_orders(1500, seed=3)
    orders = orders[orders["invoice_ts"] < "2011-12-01"]
    pw, tt = cr.evaluate(orders, ["2010-06-01", "2010-12-01", "2011-06-01"], horizon=180)
    assert len(pw) == 3 and len(tt) == 2
    assert np.isfinite(tt[["pred_over_actual_before", "after_active_lapsed_factors"]].to_numpy()).all()
    with pytest.raises(ValueError):
        cr.evaluate(orders, ["2010-06-01", "2010-09-01"], horizon=180)


def test_bias_by_date_runs_and_flags_dates_past_the_data():
    from src.eval import clv_recalibration as cr
    orders = make_orders(1500, seed=3)
    orders = orders[orders["invoice_ts"] < "2011-12-01"]
    t = cr.bias_by_date(orders, ["2010-06-01", "2010-12-01", "2011-11-15"], horizon=90)
    ok = t.dropna(subset=["pred_over_actual"])
    assert len(ok) == 2 and np.isfinite(ok["pred_over_actual"]).all()
    assert t.iloc[2]["note"] == "runs past the end of the data"
