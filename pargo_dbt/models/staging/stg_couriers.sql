with source as (
    select * from {{ source('raw', 'DIM_COURIERS') }}
)
select
    COURIER_ID,
    trim(COURIER_NAME)  as COURIER_NAME,
    REGION,
    VEHICLE_TYPE,
    HIRED_DATE::date    as HIRED_DATE
from source
where COURIER_ID is not null
