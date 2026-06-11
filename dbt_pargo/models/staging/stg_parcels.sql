-- Dedupe integration retries (keep latest load), standardise types,
-- quarantine impossible weights/values rather than silently fixing them.
with source as (
    select *,
        row_number() over (
            partition by parcel_id
            order by _loaded_at desc
        ) as _rn
    from {{ source('pargo_raw', 'parcels') }}
),
deduped as (
    select * from source where _rn = 1
)
select
    parcel_id,
    order_id,
    customer_id,
    retailer_id,
    pickup_point_id,
    courier_id,
    upper(waybill_number)                          as waybill_number,
    created_at,
    dispatched_at,
    arrived_at_point_at,
    notified_at,
    collected_at,
    rts_at,
    parcel_status,
    nullif(parcel_value_zar, 0)                    as parcel_value_zar,
    case when parcel_weight_kg > 0
         then parcel_weight_kg end                 as parcel_weight_kg,   -- nulls + negatives -> null
    delivery_cost_zar,
    service_type,
    province,
    (parcel_weight_kg is null or parcel_weight_kg <= 0
        or parcel_value_zar is null or parcel_value_zar <= 0)
                                                   as has_quality_issue
from deduped
