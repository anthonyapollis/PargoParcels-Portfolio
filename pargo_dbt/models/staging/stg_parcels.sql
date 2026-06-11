with source as (
    select * from {{ source('raw', 'FACT_PARCELS') }}
),
cleaned as (
    select
        PARCEL_ID,
        ORDER_ID,
        CUSTOMER_ID,
        RETAILER_ID,
        PICKUP_POINT_ID,
        COURIER_ID,
        WAYBILL_NUMBER,
        CREATED_AT,
        DISPATCHED_AT,
        ARRIVED_AT_POINT_AT,
        NOTIFIED_AT,
        COLLECTED_AT,
        RTS_AT,
        upper(trim(PARCEL_STATUS))   as PARCEL_STATUS,
        PARCEL_VALUE_ZAR,
        PARCEL_WEIGHT_KG,
        DELIVERY_COST_ZAR,
        upper(trim(SERVICE_TYPE))    as SERVICE_TYPE,
        PROVINCE,
        LOAD_YEAR,
        LOAD_MONTH,
        datediff('hour', DISPATCHED_AT, ARRIVED_AT_POINT_AT) as TRANSIT_HOURS,
        datediff('day',  ARRIVED_AT_POINT_AT, COLLECTED_AT)  as DWELL_DAYS
    from source
    where PARCEL_ID is not null
)
select * from cleaned
