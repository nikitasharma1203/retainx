-- RFM as of a cutoff. Only orders strictly before the cutoff are used.
-- Change the cutoff with:  dbt run --vars '{cutoff_date: "2011-03-01"}'
{% set cutoff = var('cutoff_date') %}

with base as (
    select
        customer_id,
        ('{{ cutoff }}'::date - max(invoice_ts)::date)  as recency_days,
        count(distinct invoice_id)                      as frequency,
        sum(order_revenue)                              as monetary,
        ('{{ cutoff }}'::date - min(invoice_ts)::date)  as tenure_days
    from {{ ref('fct_orders') }}
    where invoice_ts < '{{ cutoff }}'::timestamp
    group by customer_id
)

select
    *,
    '{{ cutoff }}'::date as cutoff_date,
    6 - ntile(5) over (order by recency_days)  as r_score,  -- 5 = most recent
    ntile(5) over (order by frequency, monetary) as f_score,
    ntile(5) over (order by monetary)            as m_score
from base
