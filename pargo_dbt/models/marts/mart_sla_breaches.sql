with parcels as (
    select * from {{ ref('stg_parcels') }}
),
customers as (
    select * from {{ ref('stg_customers') }}
),
retailers as (
    select * from {{ ref('stg_retailers') }}
)

select
    p.PARCEL_ID,
    p.WAYBILL_NUMBER,
    p.CREATED_AT,
    p.ARRIVED_AT_POINT_AT,
    p.COLLECTED_AT,
    p.RTS_AT,
    p.PARCEL_STATUS,
    p.PROVINCE,
    p.DWELL_DAYS,
    p.TRANSIT_HOURS,
    p.LOAD_YEAR,
    p.LOAD_MONTH,
    c.CUSTOMER_NAME,
    c.CUSTOMER_SEGMENT,
    r.RETAILER_NAME,
    r.TIER              as RETAILER_TIER,
    case
        when p.PARCEL_STATUS = 'RTS'                then 'RTS_BREACH'
        when p.DWELL_DAYS > 7                       then 'LONG_DWELL'
        when p.TRANSIT_HOURS > 72                   then 'SLOW_TRANSIT'
        else 'WITHIN_SLA'
    end                 as BREACH_TYPE
from parcels p
join customers  c on p.CUSTOMER_ID  = c.CUSTOMER_ID
join retailers  r on p.RETAILER_ID  = r.RETAILER_ID
where p.PARCEL_STATUS in ('RTS','COLLECTED')
  and (p.DWELL_DAYS > 5 or p.TRANSIT_HOURS > 72 or p.PARCEL_STATUS = 'RTS')
