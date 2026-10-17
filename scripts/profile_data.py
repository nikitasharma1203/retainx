"""Day-1 data check. Prints a markdown block to paste into docs/data_quality_log.md.

Usage: python scripts/profile_data.py data/raw/online_retail_II.xlsx
"""
import sys
from _common import read_file


def main(path: str) -> None:
    df = read_file(path)
    n = len(df)
    cancel = df["invoice"].str.startswith("C")
    nonprod = ~df["stock_code"].str.match(r"^[0-9]{5}")
    print(f"## Profile of `{path}`\n")
    print(f"- rows: {n:,}; columns: {df.shape[1]}")
    print(f"- invoice_date range: {df['invoice_date'].min()} -> {df['invoice_date'].max()}")
    print(f"- rows with missing customer_id: {df['customer_id'].isna().sum():,} ({df['customer_id'].isna().mean():.1%})")
    print(f"- distinct customers: {df['customer_id'].nunique():,}")
    print(f"- distinct invoices: {df['invoice'].nunique():,}")
    print(f"- cancellation invoices (start with 'C'): {cancel.sum():,} rows")
    print(f"- quantity <= 0: {(df['quantity'] <= 0).sum():,} rows")
    print(f"- price <= 0: {(df['price'] <= 0).sum():,} rows")
    print(f"- missing description: {df['description'].isna().sum():,} rows")
    print(f"- exact duplicate rows: {df.duplicated().sum():,}")
    print(f"- stock codes not starting with 5 digits (likely non-product): {nonprod.sum():,} rows")
    print("\nTop non-product stock codes:")
    print(df.loc[nonprod, "stock_code"].value_counts().head(10).to_string())
    print("\nNulls per column:")
    print(df.isna().sum().to_string())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
