with source as (
    select * from {{ source('raw', 'DIM_RETAILERS') }}
)
select
    RETAILER_ID,
    trim(RETAILER_NAME)     as RETAILER_NAME,
    INDUSTRY,
    TIER,
    CONTRACT_START_DATE::date as CONTRACT_START_DATE,
    RATE_PER_PARCEL_ZAR,
    INTEGRATION_TYPE
from source
where RETAILER_ID is not null
