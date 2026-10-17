-- Descriptors that do not change with time. Deliberately has no last_order or lifetime
-- totals: those would leak the future into features. Use customer_rfm at a cutoff instead.
select
    customer_id,
    min(invoice_ts) as first_order_ts,
    (array_agg(country order by invoice_ts desc))[1] as country
from {{ ref('int_valid_sales') }}
group by customer_id
