select
    c.customer_id                              as customer_key,   -- 10M rows: natural key, no SCD2 by design
    c.customer_name,
    c.province,
    c.city,
    c.registration_date,
    c.customer_segment,
    c.active_flag,
    coalesce(a.lifetime_parcels, 0)            as lifetime_parcels,
    a.first_parcel_at,
    a.last_parcel_at,
    coalesce(a.lifetime_parcel_value_zar, 0)   as lifetime_parcel_value_zar,
    case
        when a.lifetime_parcels >= 24 then 'Power User'
        when a.lifetime_parcels >= 6  then 'Engaged'
        when a.lifetime_parcels >= 1  then 'Light'
        else 'Never Shipped'
    end                                        as usage_band
from {{ ref('stg_customers') }} c
left join {{ ref('int_customer_activity') }} a using (customer_id)
