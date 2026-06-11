select order_id, customer_id, retailer_id, order_created_at,
       order_value_zar, channel
from {{ source('pargo_raw', 'orders') }}
qualify row_number() over (partition by order_id order by _loaded_at desc) = 1
