-- Fails if order-level revenue does not match line-level revenue.
with orders as (select sum(order_revenue) as r from {{ ref('fct_orders') }}),
     lines  as (select sum(line_revenue)  as r from {{ ref('int_valid_sales') }})
select orders.r as order_total, lines.r as line_total
from orders, lines
where abs(orders.r - lines.r) > 0.01
