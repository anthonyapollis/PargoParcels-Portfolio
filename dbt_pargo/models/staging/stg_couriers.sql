select courier_id, courier_name, region, vehicle_type, hired_date
from {{ source('pargo_raw', 'couriers') }}
qualify row_number() over (partition by courier_id order by _loaded_at desc) = 1
