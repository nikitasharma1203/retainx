import pandas as pd

from src.ranking import product_stats


def test_repeat_only_counts_if_second_purchase_is_before_cutoff():
    pc = pd.DataFrame({
        "stock_code": ["A", "A", "B"],
        "customer_id": [1, 2, 3],
        "first_purchase_ts": pd.to_datetime(["2010-01-01", "2010-02-01", "2010-01-15"]),
        "second_purchase_ts": pd.to_datetime(["2010-06-01", None, None]),
    })
    products = pd.DataFrame({"stock_code": ["A", "B"],
                             "first_sale_ts": pd.to_datetime(["2010-01-01", "2010-01-15"])})
    early = product_stats(pc, products, "2010-03-01")
    late = product_stats(pc, products, "2010-07-01")
    assert early.loc["A", "n_customers"] == 2 and early.loc["A", "n_repeaters"] == 0   # June repeat is in the future
    assert late.loc["A", "n_repeaters"] == 1


def test_customers_first_buying_after_cutoff_are_ignored():
    pc = pd.DataFrame({"stock_code": ["A"], "customer_id": [1],
                       "first_purchase_ts": pd.to_datetime(["2010-05-01"]),
                       "second_purchase_ts": pd.to_datetime([None])})
    products = pd.DataFrame({"stock_code": ["A"], "first_sale_ts": pd.to_datetime(["2010-05-01"])})
    assert product_stats(pc, products, "2010-04-01").empty
