with source as (
    select * from {{ source('raw', 'FACT_TRACKING_EVENTS') }}
)
select
    TRACKING_EVENT_ID,
    PARCEL_ID,
    upper(trim(EVENT_TYPE))     as EVENT_TYPE,
    EVENT_TIMESTAMP,
    LATITUDE,
    LONGITUDE,
    upper(trim(STATUS))         as STATUS,
    SOURCE_SYSTEM,
    LOAD_YEAR,
    LOAD_MONTH
from source
where TRACKING_EVENT_ID is not null
  and PARCEL_ID is not null
