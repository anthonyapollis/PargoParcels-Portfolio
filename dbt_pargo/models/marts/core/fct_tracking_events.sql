{{ config(
    materialized='incremental',
    unique_key='tracking_event_key',
    incremental_strategy='merge',
    cluster_by=['event_date_key']
) }}
-- Grain: one row per scan event. 150M rows at full scale.
select
    e.tracking_event_id                                  as tracking_event_key,
    e.parcel_id                                          as parcel_key,
    to_number(to_char(e.event_timestamp, 'YYYYMMDD'))    as event_date_key,
    e.event_type,
    m.journey_stage,
    m.stage_order,
    m.is_terminal,
    e.event_timestamp,
    e.latitude,
    e.longitude,
    e.status,
    e.source_system
from {{ ref('stg_tracking_events') }} e
left join {{ ref('event_type_mapping') }} m using (event_type)
{% if is_incremental() %}
  where e.event_timestamp >= (select dateadd(day, -3, max(event_timestamp)) from {{ this }})
{% endif %}
