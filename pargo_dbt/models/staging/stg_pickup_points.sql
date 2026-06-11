with source as (
    select * from {{ source('raw', 'DIM_PICKUP_POINTS') }}
)
select
    PICKUP_POINT_ID,
    trim(STORE_NAME)    as STORE_NAME,
    PARTNER_NAME,
    PROVINCE,
    CITY,
    LATITUDE,
    LONGITUDE,
    OPENING_DATE::date  as OPENING_DATE,
    CAPACITY_PER_DAY,
    STATUS
from source
where PICKUP_POINT_ID is not null
  and STATUS = 'active'
