-- One row per stock code. first_sale_ts is used to simulate "new launches" in ranking.
with sales as (
    select * from {{ ref('stg_transactions') }}
    where not is_cancellation and quantity > 0
)

select
    stock_code,
    (array_agg(description order by invoice_ts desc)
        filter (where description is not null))[1]  as description,
    min(invoice_ts)                                 as first_sale_ts,
    max(invoice_ts)                                 as last_sale_ts,
    count(distinct invoice_id)                      as n_invoices
from sales
group by stock_code
