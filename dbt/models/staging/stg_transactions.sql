-- One row per raw invoice line. Typed and renamed only. Nothing is dropped here:
-- cancellations, missing customers and exact duplicate lines are flagged so every
-- filter is visible downstream (see int_valid_sales).
with src as (
    select
        invoice::text                                  as invoice_id,
        stock_code::text                               as stock_code,
        nullif(trim(description), '')                  as description,
        quantity::int                                  as quantity,
        invoice_date::timestamp                        as invoice_ts,
        price::numeric(12, 4)                          as unit_price,
        customer_id::bigint                            as customer_id,
        country::text                                  as country,
        (invoice like 'C%')                            as is_cancellation,
        (customer_id is null)                          as is_missing_customer
    from {{ source('raw', 'online_retail') }}
)

select
    *,
    -- true for the 2nd, 3rd... copy of a line identical in every field (NULLs compare equal here)
    (row_number() over (
        partition by invoice_id, stock_code, description, quantity,
                     invoice_ts, unit_price, customer_id, country
        order by invoice_ts
    ) > 1)                                             as is_duplicate_line
from src
