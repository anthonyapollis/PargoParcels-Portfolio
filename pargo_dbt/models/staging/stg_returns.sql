with source as (
    select * from {{ source('raw', 'FACT_RETURNS') }}
)
select
    RETURN_ID,
    PARCEL_ID,
    RETAILER_ID,
    RETURN_INITIATED_AT,
    trim(RETURN_REASON)     as RETURN_REASON,
    RETURN_VALUE_ZAR,
    DROP_OFF_POINT_ID,
    LOAD_YEAR,
    LOAD_MONTH
from source
where RETURN_ID is not null
  and PARCEL_ID is not null
