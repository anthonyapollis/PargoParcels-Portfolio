{{
  config(
    cluster_by=['EVENT_DATE']
  )
}}

with parcels as (
    select
        to_date(CREATED_AT)   as EVENT_DATE,
        PROVINCE,
        PARCEL_STATUS,
        SERVICE_TYPE,
        LOAD_YEAR,
        count(*)              as PARCELS_CREATED,
        sum(PARCEL_VALUE_ZAR) as TOTAL_VALUE_ZAR,
        sum(DELIVERY_COST_ZAR) as TOTAL_COST_ZAR,
        avg(TRANSIT_HOURS)    as AVG_TRANSIT_HOURS,
        avg(DWELL_DAYS)       as AVG_DWELL_DAYS
    from {{ ref('stg_parcels') }}
    group by 1,2,3,4,5
),
events as (
    select
        to_date(EVENT_TIMESTAMP) as EVENT_DATE,
        EVENT_TYPE,
        count(*)                 as EVENT_COUNT
    from {{ ref('stg_tracking_events') }}
    group by 1,2
),
returns as (
    select
        to_date(RETURN_INITIATED_AT) as EVENT_DATE,
        count(*)                      as RETURNS_COUNT,
        sum(RETURN_VALUE_ZAR)         as TOTAL_RETURN_VALUE
    from {{ ref('stg_returns') }}
    group by 1
)

select
    p.EVENT_DATE,
    p.PROVINCE,
    p.PARCEL_STATUS,
    p.SERVICE_TYPE,
    p.LOAD_YEAR,
    p.PARCELS_CREATED,
    p.TOTAL_VALUE_ZAR,
    p.TOTAL_COST_ZAR,
    p.AVG_TRANSIT_HOURS,
    p.AVG_DWELL_DAYS,
    coalesce(r.RETURNS_COUNT, 0)      as RETURNS_COUNT,
    coalesce(r.TOTAL_RETURN_VALUE, 0) as TOTAL_RETURN_VALUE
from parcels p
left join returns r on p.EVENT_DATE = r.EVENT_DATE
