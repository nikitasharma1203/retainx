-- The single place where rows are excluded from analysis. Each rule is in docs/decisions.md.
select
    invoice_id,
    stock_code,
    customer_id,
    country,
    invoice_ts,
    quantity,
    unit_price,
    quantity * unit_price as line_revenue
from {{ ref('stg_transactions') }}
where not is_cancellation
  and not is_missing_customer
  and quantity > 0
  and unit_price > 0
  and stock_code ~ '^[0-9]{5}'   -- drops POST, D, M, BANK CHARGES etc.; keeps 85123A style codes
  {% if var('dedupe_exact', true) %}and not is_duplicate_line{% endif %}   -- sensitivity: --vars "{dedupe_exact: false}"
