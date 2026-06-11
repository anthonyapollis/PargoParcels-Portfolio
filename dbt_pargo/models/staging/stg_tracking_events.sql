-- Filter orphan events (scanner feed outruns parcel sync) and
-- future-dated rows (known clock-skew bug in PartnerPOS uploads).
select
    e.tracking_event_id,
    e.parcel_id,
    e.event_type,
    e.event_timestamp,
    e.latitude,
    e.longitude,
    e.status,
    e.source_system
from {{ source('pargo_raw', 'tracking_events') }} e
inner join {{ ref('stg_parcels') }} p using (parcel_id)   -- drops orphans
where e.event_timestamp <= current_timestamp()
  and e.event_timestamp >= '{{ var("history_start") }}'
