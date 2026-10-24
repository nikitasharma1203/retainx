import pandas as pd

from src.eval.ranking_check import evaluate, future_repeat_table


def _pc():
    return pd.DataFrame({
        "stock_code": ["A", "A", "A", "B"],
        "customer_id": [1, 2, 3, 4],
        "first_purchase_ts": pd.to_datetime(["2010-01-01"] * 4),
        "second_purchase_ts": pd.to_datetime(["2010-03-01", "2010-05-01", None, "2010-02-01"]),
    })


def test_future_repeat_counts_only_not_yet_repeated_buyers():
    t = future_repeat_table(_pc(), "2010-04-01", 90)
    # at 2010-04-01 customers 1 and 4 already repeated; 2 repeats within 90d; 3 never does
    assert t.loc["A", "eligible"] == 2 and t.loc["A", "converted"] == 1
    assert "B" not in t.index


def test_evaluate_has_expected_columns():
    pr = pd.DataFrame({"stock_code": ["A", "B"], "first_sale_ts": pd.to_datetime(["2010-01-01"] * 2)})
    res = evaluate(_pc(), pr, ["2010-04-01"], k=2)
    assert {"future_repeat", "eligible_topk", "min_buyers_topk"} <= set(res.columns)
    assert set(res["method"]) == {"naive", "wilson", "bayes"}
