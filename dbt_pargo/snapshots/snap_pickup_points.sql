{% snapshot snap_pickup_points %}
{{ config(
    target_schema='snapshots', unique_key='pickup_point_id',
    strategy='check',
    check_cols=['store_name','partner_name','capacity_per_day','status']
) }}
select * from {{ source('pargo_raw', 'pickup_points') }}
qualify row_number() over (partition by pickup_point_id order by _loaded_at desc) = 1
{% endsnapshot %}
