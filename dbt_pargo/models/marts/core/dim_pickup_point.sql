select
    {{ dbt_utils.generate_surrogate_key(['pickup_point_id', 'dbt_valid_from']) }} as pickup_point_key,
    pickup_point_id,
    store_name,
    partner_name,
    province,
    city,
    latitude,
    longitude,
    opening_date,
    capacity_per_day,
    status,
    dbt_valid_from as valid_from,
    coalesce(dbt_valid_to, '9999-12-31'::timestamp) as valid_to,
    dbt_valid_to is null as is_current
from {{ ref('snap_pickup_points') }}
