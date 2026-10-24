{{ config(materialized='table') }}
-- Required by dbt's semantic layer: one row per day covering the dataset and some margin.
select generate_series('2009-01-01'::date, '2013-12-31'::date, interval '1 day')::date as date_day
