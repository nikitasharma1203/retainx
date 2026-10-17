"""Shared helpers for loading the Online Retail II file."""
import pandas as pd

# Different copies of the dataset use different column names.
COLUMN_ALIASES = {
    "invoice": "invoice",
    "invoiceno": "invoice",
    "stockcode": "stock_code",
    "description": "description",
    "quantity": "quantity",
    "invoicedate": "invoice_date",
    "price": "price",
    "unitprice": "price",
    "customer id": "customer_id",
    "customerid": "customer_id",
    "country": "country",
}
REQUIRED = ["invoice", "stock_code", "description", "quantity",
            "invoice_date", "price", "customer_id", "country"]


def read_file(path: str) -> pd.DataFrame:
    """Read xlsx (all sheets stacked) or csv, and normalise column names."""
    if path.lower().endswith((".xlsx", ".xls")):
        sheets = pd.read_excel(path, sheet_name=None, dtype={"Invoice": str, "InvoiceNo": str, "StockCode": str})
        df = pd.concat(sheets.values(), ignore_index=True)
    else:
        df = pd.read_csv(path, dtype=str, encoding="latin-1")
    df.columns = [COLUMN_ALIASES.get(c.strip().lower(), c.strip().lower()) for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns after renaming: {missing}. Found: {list(df.columns)}")
    df = df[REQUIRED].copy()
    df["invoice"] = df["invoice"].astype(str)
    df["stock_code"] = df["stock_code"].astype(str)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce")
    return df
