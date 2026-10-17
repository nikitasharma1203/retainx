-- One row per raw invoice line. Typed and renamed only. Nothing is dropped here:
-- cancellations and missing customers are flagged so every filter is visible downstream.
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
