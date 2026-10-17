select
    p.stock_code,
    p.description,
    p.first_sale_ts,
    p.n_invoices
from {{ ref('stg_products') }} p
where p.stock_code ~ '^[0-9]{5}'
