{{
  config(materialized='table')
}}

with orders as (
    select * from {{ ref('stg_orders') }}
),
parcels as (
    select * from {{ ref('stg_parcels') }}
),
returns as (
    select * from {{ ref('stg_returns') }}
),
customers as (
    select * from {{ ref('stg_customers') }}
),
order_stats as (
    select
        CUSTOMER_ID,
        count(*)             as ORDER_COUNT,
        sum(ORDER_VALUE_ZAR) as TOTAL_ORDER_VALUE,
        avg(ORDER_VALUE_ZAR) as AVG_ORDER_VALUE,
        min(ORDER_CREATED_AT) as FIRST_ORDER_AT,
        max(ORDER_CREATED_AT) as LAST_ORDER_AT,
        datediff('day', min(ORDER_CREATED_AT), max(ORDER_CREATED_AT)) as TENURE_DAYS
    from orders
    group by 1
),
parcel_stats as (
    select
        CUSTOMER_ID,
        count(*) as PARCEL_COUNT,
        sum(case when PARCEL_STATUS='RTS' then 1 else 0 end) as RTS_COUNT,
        avg(DWELL_DAYS) as AVG_DWELL_DAYS
    from parcels
    group by 1
),
return_stats as (
    select p.CUSTOMER_ID,
           count(r.RETURN_ID) as RETURN_COUNT
    from parcels p
    join returns r on p.PARCEL_ID = r.PARCEL_ID
    group by 1
)

select
    c.CUSTOMER_ID,
    c.PROVINCE,
    c.CUSTOMER_SEGMENT,
    c.ACTIVE_FLAG,
    coalesce(os.ORDER_COUNT, 0)       as ORDER_COUNT,
    coalesce(os.TOTAL_ORDER_VALUE, 0) as TOTAL_ORDER_VALUE,
    coalesce(os.AVG_ORDER_VALUE, 0)   as AVG_ORDER_VALUE,
    coalesce(os.TENURE_DAYS, 0)       as TENURE_DAYS,
    coalesce(ps.PARCEL_COUNT, 0)      as PARCEL_COUNT,
    coalesce(ps.RTS_COUNT, 0)         as RTS_COUNT,
    coalesce(ps.AVG_DWELL_DAYS, 0)    as AVG_DWELL_DAYS,
    coalesce(rs.RETURN_COUNT, 0)      as RETURN_COUNT,
    round(coalesce(os.TOTAL_ORDER_VALUE,0) / nullif(coalesce(os.TENURE_DAYS,0)/365.0, 0), 2)
                                      as ANNUALISED_VALUE
from customers c
left join order_stats  os on c.CUSTOMER_ID = os.CUSTOMER_ID
left join parcel_stats ps on c.CUSTOMER_ID = ps.CUSTOMER_ID
left join return_stats rs on c.CUSTOMER_ID = rs.CUSTOMER_ID
