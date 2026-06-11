select return_id, parcel_id, retailer_id, return_initiated_at,
       return_reason, return_value_zar, drop_off_point_id
from {{ source('pargo_raw', 'returns') }}
qualify row_number() over (partition by return_id order by _loaded_at desc) = 1
