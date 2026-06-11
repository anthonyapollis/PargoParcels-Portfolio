select customer_id, customer_name, mobile_number, province, city,
       registration_date, customer_segment, active_flag
from {{ source('pargo_raw', 'customers') }}
qualify row_number() over (partition by customer_id order by _loaded_at desc) = 1
