select parcel_key
from {{ ref('fct_parcels') }}
where arrived_at_point_at < created_at
