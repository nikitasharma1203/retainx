import pytest

from src import health
from tests.synth import make_orders


def test_health_scores_bands_and_validation():
    orders = make_orders(1500, seed=5)
    sc, coef, n_lapsed = health.score(orders, "2010-09-01", "2010-12-01")
    assert sc["health"].between(0, 100).all()
    sizes = sc["band"].value_counts()
    assert set(sizes.index) == {"Green", "Amber", "Red"}
    assert sizes.max() - sizes.min() <= 2          # terciles
    assert "recency_days" in coef.index
    v = health.validate(orders, sc, "2010-12-01")
    assert list(v.index) == ["Green", "Amber", "Red"] and (v["n"] > 0).all()


def test_health_rejects_overlapping_train_window():
    with pytest.raises(ValueError):
        health.score(make_orders(300), "2010-09-01", "2010-10-15")


def test_labels_unavailable_past_end_of_data():
    orders = make_orders(300)
    orders = orders[orders["invoice_ts"] < "2011-12-01"]
    assert health.labels_available(orders, "2011-08-01")
    assert not health.labels_available(orders, "2011-11-30")
