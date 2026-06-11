with parcels as (
    select * from {{ ref('stg_parcels') }}
),
returns as (
    select * from {{ ref('stg_returns') }}
),
retailers as (
    select * from {{ ref('stg_retailers') }}
),
parcel_agg as (
    select
        RETAILER_ID,
        LOAD_YEAR,
        count(*)                                        as TOTAL_PARCELS,
        sum(PARCEL_VALUE_ZAR)                           as TOTAL_GMV,
        sum(DELIVERY_COST_ZAR)                          as TOTAL_DELIVERY_COST,
        avg(TRANSIT_HOURS)                              as AVG_TRANSIT_HOURS,
        avg(DWELL_DAYS)                                 as AVG_DWELL_DAYS,
        sum(case when PARCEL_STATUS='COLLECTED' and DWELL_DAYS<=5 then 1 else 0 end)
                                                        as ON_TIME_COLLECTIONS,
        sum(case when PARCEL_STATUS='RTS' then 1 else 0 end) as RTS_COUNT
    from parcels
    group by 1,2
),
return_agg as (
    select
        RETAILER_ID,
        LOAD_YEAR,
        count(*)             as TOTAL_RETURNS,
        sum(RETURN_VALUE_ZAR) as TOTAL_RETURN_VALUE
    from returns
    group by 1,2
)

select
    r.RETAILER_ID,
    r.RETAILER_NAME,
    r.INDUSTRY,
    r.TIER,
    r.RATE_PER_PARCEL_ZAR,
    pa.LOAD_YEAR,
    pa.TOTAL_PARCELS,
    pa.TOTAL_GMV,
    pa.TOTAL_DELIVERY_COST,
    pa.AVG_TRANSIT_HOURS,
    pa.AVG_DWELL_DAYS,
    pa.ON_TIME_COLLECTIONS,
    pa.RTS_COUNT,
    coalesce(ra.TOTAL_RETURNS, 0)      as TOTAL_RETURNS,
    coalesce(ra.TOTAL_RETURN_VALUE, 0) as TOTAL_RETURN_VALUE,
    round(100.0 * pa.ON_TIME_COLLECTIONS / nullif(pa.TOTAL_PARCELS,0), 2) as ON_TIME_PCT,
    round(100.0 * pa.RTS_COUNT          / nullif(pa.TOTAL_PARCELS,0), 2) as RTS_RATE_PCT,
    round(pa.TOTAL_GMV * r.RATE_PER_PARCEL_ZAR, 2)                       as ESTIMATED_REVENUE
from retailers r
join parcel_agg pa on r.RETAILER_ID = pa.RETAILER_ID
left join return_agg ra on r.RETAILER_ID = ra.RETAILER_ID
                       and pa.LOAD_YEAR  = ra.LOAD_YEAR
