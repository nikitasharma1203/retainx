-- One row per customer per invoice.
select
    customer_id,
    invoice_id,
    min(invoice_ts)             as invoice_ts,
    count(*)                    as n_lines,
    sum(quantity)               as n_units,
    sum(line_revenue)           as order_revenue
from {{ ref('int_valid_sales') }}
group by customer_id, invoice_id
