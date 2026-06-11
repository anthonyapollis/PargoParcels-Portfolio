select courier_id as courier_key, courier_name, region, vehicle_type, hired_date
from {{ ref('stg_couriers') }}
