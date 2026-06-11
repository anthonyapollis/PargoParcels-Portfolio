{{
  config(materialized='table')
}}

with parcels as (
    select * from {{ ref('stg_parcels') }}
),
couriers as (
    select * from {{ ref('stg_couriers') }}
)

select
    c.COURIER_ID,
    c.COURIER_NAME,
    c.REGION,
    c.VEHICLE_TYPE,
    p.LOAD_YEAR,
    count(*)                                       as TOTAL_DELIVERIES,
    avg(p.TRANSIT_HOURS)                           as AVG_TRANSIT_HOURS,
    stddev(p.TRANSIT_HOURS)                        as STDDEV_TRANSIT_HOURS,
    sum(case when p.PARCEL_STATUS='RTS' then 1 else 0 end) as RTS_COUNT,
    sum(case when p.PARCEL_STATUS='COLLECTED' and p.DWELL_DAYS<=5 then 1 else 0 end) as ON_TIME_COUNT,
    round(100.0 * sum(case when p.PARCEL_STATUS='RTS' then 1 else 0 end)
          / nullif(count(*),0), 2)                 as RTS_RATE_PCT,
    round(100.0 * sum(case when p.PARCEL_STATUS='COLLECTED' and p.DWELL_DAYS<=5 then 1 else 0 end)
          / nullif(count(*),0), 2)                 as ON_TIME_PCT
from couriers c
join parcels p on c.COURIER_ID = p.COURIER_ID
group by 1,2,3,4,5
