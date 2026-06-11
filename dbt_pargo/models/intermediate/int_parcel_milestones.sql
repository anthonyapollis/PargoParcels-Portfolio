-- Single source of truth for every duration / SLA metric in the platform.
-- All downstream marts compute from these columns; no mart re-derives them.
select
    p.*,
    datediff('hour', p.created_at, p.arrived_at_point_at)      as delivery_hours,
    datediff('hour', p.arrived_at_point_at, p.collected_at)    as dwell_hours,
    datediff('hour', p.created_at, p.collected_at)             as end_to_end_hours,
    p.parcel_status in ('Collected', 'Damaged')                as is_delivered,
    p.parcel_status = 'ExpiredRTS'                             as is_rts,
    p.parcel_status = 'Lost'                                   as is_lost,
    p.parcel_status = 'Damaged'                                as is_damaged,
    coalesce(
        datediff('hour', p.created_at, p.arrived_at_point_at)
            <= {{ var('sla_delivery_hours') }}, false)         as sla_met,
    coalesce(
        datediff('day', p.notified_at, p.collected_at)
            <= {{ var('collection_window_days') }}, false)     as collected_in_window
from {{ ref('stg_parcels') }} p
