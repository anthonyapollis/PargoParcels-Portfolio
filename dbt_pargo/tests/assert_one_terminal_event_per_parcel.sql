-- Business rule: no parcel may have two terminal lifecycle events.
select parcel_key, count(*) as terminal_events
from {{ ref('fct_tracking_events') }}
where is_terminal
group by 1
having count(*) > 1
