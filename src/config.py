import os

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://retainx:retainx@localhost:5432/retainx")
ORDERS_TABLE = os.getenv("ORDERS_TABLE", "analytics.fct_orders")
PRODUCT_CUSTOMER_TABLE = os.getenv("PRODUCT_CUSTOMER_TABLE", "analytics.fct_product_customer")
PRODUCT_TABLE = os.getenv("PRODUCT_TABLE", "analytics.dim_product")

# Quarterly cutoffs for backtesting. Spacing must be >= the label horizon so that a
# training label window never overlaps the next test period. Verify against your data's date range.
BACKTEST_CUTOFFS = ["2010-06-01", "2010-09-01", "2010-12-01", "2011-03-01", "2011-06-01", "2011-09-01"]

CHURN = {"horizon_days": 90, "active_lookback_days": 180}   # active in last 180d, label = no order in next 90d
PROPENSITY = {"horizon_days": 30, "active_lookback_days": None}  # all known customers, label = order in next 30d
