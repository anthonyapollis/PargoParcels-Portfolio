{{ config(
    materialized='incremental',
    unique_key='parcel_key',
    incremental_strategy='merge',
    cluster_by=['created_date_key', 'province']
) }}
-- Grain: one row per parcel. 30M rows at full scale -> incremental merge.
-- SCD2 dims joined AS-OF parcel creation so historic rate cards hold.
with parcels as (
    select * from {{ ref('int_parcel_milestones') }}
    {% if is_incremental() %}
      where created_at >= (select dateadd(day, -3, max(created_at)) from {{ this }})
    {% endif %}
)
select
    p.parcel_id                                            as parcel_key,
    p.order_id                                             as order_key,
    p.customer_id                                          as customer_key,
    dr.retailer_key,
    dp.pickup_point_key,
    p.courier_id                                           as courier_key,
    to_number(to_char(p.created_at, 'YYYYMMDD'))           as created_date_key,
    to_number(to_char(p.collected_at, 'YYYYMMDD'))         as collected_date_key,
    p.waybill_number,
    p.created_at,
    p.dispatched_at,
    p.arrived_at_point_at,
    p.notified_at,
    p.collected_at,
    p.rts_at,
    p.parcel_status,
    p.service_type,
    p.province,
    p.parcel_value_zar,
    p.parcel_weight_kg,
    p.delivery_cost_zar,
    dr.rate_per_parcel_zar                                 as billed_rate_zar,
    p.delivery_hours,
    p.dwell_hours,
    p.end_to_end_hours,
    p.is_delivered,
    p.is_rts,
    p.is_lost,
    p.is_damaged,
    p.sla_met,
    p.collected_in_window,
    p.has_quality_issue
from parcels p
left join {{ ref('dim_retailer') }} dr
    on p.retailer_id = dr.retailer_id
   and p.created_at >= dr.valid_from and p.created_at < dr.valid_to
left join {{ ref('dim_pickup_point') }} dp
    on p.pickup_point_id = dp.pickup_point_id
   and p.created_at >= dp.valid_from and p.created_at < dp.valid_to
