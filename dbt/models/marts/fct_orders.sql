select
    customer_id,
    invoice_id,
    invoice_ts,
    invoice_ts::date as order_date,
    n_lines,
    n_units,
    order_revenue
from {{ ref('int_customer_orders') }}
