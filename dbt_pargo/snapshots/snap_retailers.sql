{% snapshot snap_retailers %}
{{ config(
    target_schema='snapshots', unique_key='retailer_id',
    strategy='check',
    check_cols=['retailer_name','industry','tier','rate_per_parcel_zar','integration_type']
) }}
select * from {{ source('pargo_raw', 'retailers') }}
qualify row_number() over (partition by retailer_id order by _loaded_at desc) = 1
{% endsnapshot %}
