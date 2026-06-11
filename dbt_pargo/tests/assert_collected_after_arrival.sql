-- Business rule: a parcel cannot be collected before it arrived at the point.
select parcel_key, arrived_at_point_at, collected_at
from {{ ref('fct_parcels') }}
where collected_at is not null
  and arrived_at_point_at is not null
  and collected_at < arrived_at_point_at
