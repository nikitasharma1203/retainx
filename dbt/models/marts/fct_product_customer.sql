-- Which customers bought which product, and how many separate times.
-- Feeds the ranking simulation (repeat-purchase rate per product).
select
    stock_code,
    customer_id,
    count(distinct invoice_id) as n_invoices,
    min(invoice_ts)            as first_purchase_ts
from {{ ref('int_valid_sales') }}
group by stock_code, customer_id
