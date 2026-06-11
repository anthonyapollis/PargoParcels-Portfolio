select pickup_point_id, store_name, partner_name, province, city,
       latitude, longitude, opening_date, capacity_per_day, status
from {{ source('pargo_raw', 'pickup_points') }}
qualify row_number() over (partition by pickup_point_id order by _loaded_at desc) = 1
