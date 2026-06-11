{{
  config(materialized='table', cluster_by=['LOAD_YEAR'])
}}

with parcels as (
    select * from {{ ref('stg_parcels') }}
),
tracking as (
    select
        PARCEL_ID,
        count(*) as EVENT_COUNT,
        min(EVENT_TIMESTAMP) as FIRST_EVENT,
        max(EVENT_TIMESTAMP) as LAST_EVENT,
        sum(case when EVENT_TYPE = 'EXCEPTION' then 1 else 0 end) as EXCEPTION_COUNT
    from {{ ref('stg_tracking_events') }}
    group by 1
),
returns as (
    select PARCEL_ID, 1 as IS_RETURNED
    from {{ ref('stg_returns') }}
)

select
    p.PARCEL_ID,
    p.LOAD_YEAR,
    p.LOAD_MONTH,
    p.PROVINCE,
    p.SERVICE_TYPE,
    p.PARCEL_WEIGHT_KG,
    p.PARCEL_VALUE_ZAR,
    p.DELIVERY_COST_ZAR,
    p.TRANSIT_HOURS,
    p.DWELL_DAYS,
    coalesce(t.EVENT_COUNT, 0)     as TRACKING_EVENT_COUNT,
    coalesce(t.EXCEPTION_COUNT, 0) as EXCEPTION_COUNT,
    datediff('hour', p.CREATED_AT, t.FIRST_EVENT)  as HOURS_TO_FIRST_SCAN,
    datediff('hour', t.LAST_EVENT, p.ARRIVED_AT_POINT_AT) as HOURS_LAST_SCAN_TO_ARRIVAL,
    case when p.PARCEL_STATUS = 'RTS' then 1 else 0 end as LABEL_IS_RTS,
    coalesce(r.IS_RETURNED, 0)     as LABEL_IS_RETURNED
from parcels p
left join tracking t on p.PARCEL_ID = t.PARCEL_ID
left join returns  r on p.PARCEL_ID = r.PARCEL_ID
where p.PARCEL_STATUS in ('COLLECTED','RTS')
