{{
  config(
    cluster_by=['LOAD_YEAR', 'PROVINCE']
  )
}}

with parcels as (
    select * from {{ ref('stg_parcels') }}
),
retailers as (
    select * from {{ ref('stg_retailers') }}
),
couriers as (
    select * from {{ ref('stg_couriers') }}
),
pickup_points as (
    select * from {{ ref('stg_pickup_points') }}
)

select
    p.PARCEL_ID,
    p.ORDER_ID,
    p.WAYBILL_NUMBER,
    p.CREATED_AT,
    p.PARCEL_STATUS,
    p.SERVICE_TYPE,
    p.PROVINCE,
    p.PARCEL_VALUE_ZAR,
    p.PARCEL_WEIGHT_KG,
    p.DELIVERY_COST_ZAR,
    p.TRANSIT_HOURS,
    p.DWELL_DAYS,
    p.LOAD_YEAR,
    p.LOAD_MONTH,
    r.RETAILER_NAME,
    r.INDUSTRY          as RETAILER_INDUSTRY,
    r.TIER              as RETAILER_TIER,
    c.COURIER_NAME,
    c.VEHICLE_TYPE,
    pp.STORE_NAME       as PICKUP_STORE,
    pp.PARTNER_NAME     as PICKUP_PARTNER,
    case
        when p.PARCEL_STATUS = 'COLLECTED'
             and p.DWELL_DAYS <= 5 then 'ON_TIME'
        when p.PARCEL_STATUS = 'COLLECTED'
             and p.DWELL_DAYS > 5  then 'LATE'
        when p.PARCEL_STATUS = 'RTS'       then 'RETURNED'
        else 'IN_PROGRESS'
    end                 as SLA_STATUS
from parcels p
left join retailers  r  on p.RETAILER_ID    = r.RETAILER_ID
left join couriers   c  on p.COURIER_ID     = c.COURIER_ID
left join pickup_points pp on p.PICKUP_POINT_ID = pp.PICKUP_POINT_ID
