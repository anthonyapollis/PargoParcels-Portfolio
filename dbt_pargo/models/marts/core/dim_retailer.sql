-- SCD2 from snapshot: rate cards and tiers change; revenue attribution
-- must use the rate in force when the parcel shipped.
select
    {{ dbt_utils.generate_surrogate_key(['retailer_id', 'dbt_valid_from']) }} as retailer_key,
    retailer_id,
    retailer_name,
    industry,
    tier,
    contract_start_date,
    rate_per_parcel_zar,
    integration_type,
    dbt_valid_from as valid_from,
    coalesce(dbt_valid_to, '9999-12-31'::timestamp) as valid_to,
    dbt_valid_to is null as is_current
from {{ ref('snap_retailers') }}
