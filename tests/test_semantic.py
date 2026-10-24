import pytest
from sqlalchemy import create_engine, text

from src import config
from src.semantic import SemanticLayer

sl = SemanticLayer()


def _db_ok():
    try:
        with create_engine(config.DB_URL).connect() as c:
            c.execute(text("select count(*) from analytics.fct_orders"))
        return True
    except Exception:
        return False


def test_lists_metrics_and_dimensions():
    names = {m["metric"] for m in sl.list_metrics()}
    assert names == {"revenue", "orders", "active_customers", "avg_order_value", "customers"}
    assert "country" in sl.dimensions_for("revenue")        # reached through the customer entity
    assert "month" in sl.dimensions_for("customers")


def test_compiles_join_filter_and_ratio():
    sql, params = sl.compile("revenue", "country", "2011-01-01", "2011-12-01")
    assert "join analytics.dim_customer d on m.customer_id = d.customer_id" in sql
    assert "m.order_date >= :s" in sql and "m.order_date < :e" in sql and set(params) == {"s", "e"}
    sql, _ = sl.compile("avg_order_value", "month")
    assert "nullif" in sql and "date_trunc('month'" in sql


def test_rejects_unknown_metric_dimension_and_bad_dates():
    with pytest.raises(ValueError):
        sl.compile("profit")
    with pytest.raises(ValueError):
        sl.compile("revenue", "customer_id; drop table x")
    with pytest.raises(ValueError):
        sl.compile("revenue", None, "not-a-date")


@pytest.mark.skipif(not _db_ok(), reason="needs the retainx database")
def test_metrics_match_direct_sql():
    eng = create_engine(config.DB_URL)
    with eng.connect() as c:
        rev = float(c.execute(text("select sum(order_revenue) from analytics.fct_orders where invoice_ts >= '2010-06-01' and invoice_ts < '2011-06-01'")).scalar())
        n_cust = c.execute(text("select count(distinct customer_id) from analytics.fct_orders")).scalar()
        aov = float(c.execute(text("select avg(order_revenue) from analytics.fct_orders")).scalar())
    assert sl.query(eng, "revenue", None, "2010-06-01", "2011-06-01")[0]["value"] == pytest.approx(rev, abs=0.01)
    assert sl.query(eng, "active_customers")[0]["value"] == n_cust
    assert sl.query(eng, "avg_order_value")[0]["value"] == pytest.approx(aov, abs=0.01)
    by_country = sl.query(eng, "revenue", "country")
    assert sum(r["value"] for r in by_country) == pytest.approx(float(sl.query(eng, "revenue")[0]["value"]), abs=0.05)
