select retailer_id, retailer_name, industry, tier, contract_start_date,
       rate_per_parcel_zar, integration_type
from {{ source('pargo_raw', 'retailers') }}
qualify row_number() over (partition by retailer_id order by _loaded_at desc) = 1
