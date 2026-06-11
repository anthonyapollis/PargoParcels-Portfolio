with source as (
    select * from {{ source('raw', 'FACT_ORDERS') }}
)
select
    ORDER_ID,
    CUSTOMER_ID,
    RETAILER_ID,
    ORDER_CREATED_AT,
    ORDER_VALUE_ZAR,
    upper(trim(CHANNEL)) as CHANNEL,
    LOAD_YEAR,
    LOAD_MONTH
from source
where ORDER_ID is not null
  and ORDER_VALUE_ZAR > 0
