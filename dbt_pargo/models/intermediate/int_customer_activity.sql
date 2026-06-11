select
    customer_id,
    count(*)                                   as lifetime_parcels,
    min(created_at)                            as first_parcel_at,
    max(created_at)                            as last_parcel_at,
    sum(parcel_value_zar)                      as lifetime_parcel_value_zar,
    count(distinct pickup_point_id)            as distinct_points_used,
    count(distinct retailer_id)                as distinct_retailers_used
from {{ ref('stg_parcels') }}
group by 1
