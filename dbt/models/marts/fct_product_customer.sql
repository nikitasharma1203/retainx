-- Which customers bought which product, and when they first and second bought it.
-- second_purchase_ts lets ranking judge "repeat buyer" as of any cutoff without peeking ahead.
with per_invoice as (
    select
        stock_code,
        customer_id,
        invoice_id,
        min(invoice_ts) as invoice_ts
    from {{ ref('int_valid_sales') }}
    group by stock_code, customer_id, invoice_id
),

ranked as (
    select
        *,
        row_number() over (partition by stock_code, customer_id order by invoice_ts, invoice_id) as rn
    from per_invoice
)

select
    stock_code,
    customer_id,
    count(*)                                  as n_invoices,
    min(invoice_ts)                           as first_purchase_ts,
    min(invoice_ts) filter (where rn = 2)     as second_purchase_ts
from ranked
group by stock_code, customer_id
