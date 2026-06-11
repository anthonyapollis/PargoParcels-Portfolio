with source as (
    select * from {{ source('raw', 'DIM_CUSTOMERS') }}
)
select
    CUSTOMER_ID,
    trim(CUSTOMER_NAME)     as CUSTOMER_NAME,
    MOBILE_NUMBER,
    PROVINCE,
    CITY,
    REGISTRATION_DATE::date as REGISTRATION_DATE,
    CUSTOMER_SEGMENT,
    ACTIVE_FLAG
from source
where CUSTOMER_ID is not null
