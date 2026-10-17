# Agent evaluation set

Goal: measure whether the semantic layer and narrow tools help Claude answer correctly.
Run each question twice: (A) agent with raw-table SQL access, (B) agent with `mcp_server` tools.
Score correct / incorrect against the reference query. Report both rates.

Write the reference answer by running the SQL yourself once the data is loaded.

| # | Question | Reference SQL (run this for the answer key) |
|---|---|---|
| 1 | How many customers placed an order in 2011? | `select count(distinct customer_id) from analytics.fct_orders where invoice_ts >= '2011-01-01' and invoice_ts < '2012-01-01'` |
| 2 | What was total revenue in 2010? | `select sum(order_revenue) from analytics.fct_orders where invoice_ts >= '2010-01-01' and invoice_ts < '2011-01-01'` |
| 3 | Which month in 2011 had the highest revenue? | `select date_trunc('month', invoice_ts) m, sum(order_revenue) r from analytics.fct_orders where invoice_ts >= '2011-01-01' group by 1 order by r desc limit 1` |
| 4 | What is the average order value? | `select avg(order_revenue) from analytics.fct_orders` |
| 5 | How many customers ordered exactly once? | `select count(*) from (select customer_id from analytics.fct_orders group by 1 having count(*) = 1) t` |
| 6 | Which country has the most customers? | `select country, count(*) from analytics.dim_customer group by 1 order by 2 desc limit 1` |
| 7 | How many orders did customer 12347 place before 2011-01-01? | `select count(*) from analytics.fct_orders where customer_id = 12347 and invoice_ts < '2011-01-01'` |
| 8 | How many distinct products have been sold? | `select count(*) from analytics.dim_product` |
| 9 | What share of revenue came from the top 10% of customers? | _write the query_ |
| 10 | Which customers have not ordered in the 180 days before 2011-12-01? | _write the query_ |

Add 10 more before reporting results. Include at least three where the wrong table or a missing filter
(cancellations, missing customer ID) would give a plausible but wrong answer.
