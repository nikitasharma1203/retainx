# Data quality log

Run `python scripts/profile_data.py data/raw/<file>` and paste the output under "Profile".
For every issue, record what you found, what you decided and where it is implemented.
Fill the counts from YOUR data. None are pre-filled on purpose.

## Profile
## Profile of `data/raw/online_retail_II.xlsx`

- rows: 1,067,371; columns: 8
- invoice_date range: 2009-12-01 07:45:00 -> 2011-12-09 12:50:00
- rows with missing customer_id: 243,007 (22.8%)
- distinct customers: 5,942
- distinct invoices: 53,628
- cancellation invoices (start with 'C'): 19,494 rows
- quantity <= 0: 22,950 rows
- price <= 0: 6,207 rows
- missing description: 4,382 rows
- exact duplicate rows: 34,335
- stock codes not starting with 5 digits (likely non-product): 6,093 rows

Top non-product stock codes:
stock_code
POST            2122
DOT             1446
M               1421
C2               282
D                177
S                104
BANK CHARGES     102
ADJUST            67
AMAZONFEE         43
DCGS0058          31

Nulls per column:
invoice              0
stock_code           0
description       4382
quantity             0
invoice_date         0
price                0
customer_id     243007
country              0


## Issues and decisions

| # | Check | Count | Decision | Implemented in |
|---|---|---|---|---|
| 1 | Rows with missing customer ID | | Excluded from customer-level models; kept in staging, flagged | `int_valid_sales.sql` |
| 2 | Cancellation invoices (start with `C`) | | Excluded from sales; flagged in staging. Not netted against original orders (see decisions.md) | `int_valid_sales.sql` |
| 3 | Quantity <= 0 | | Excluded | `int_valid_sales.sql` |
| 4 | Price <= 0 | | Excluded | `int_valid_sales.sql` |
| 5 | Non-product stock codes (POST, D, M, BANK CHARGES ...) | | Excluded: keep codes starting with 5 digits | `int_valid_sales.sql` |
| 6 | Exact duplicate rows | | _decide: keep or drop_ | |
| 7 | Same stock code with several descriptions | | Latest description used | `stg_products.sql` |
| 8 | Date range vs the windows in `src/config.py` | | Adjust cutoffs if needed | `src/config.py` |
