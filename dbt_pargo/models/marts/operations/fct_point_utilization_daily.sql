-- Network-health table: one row per point per day. Powers the
-- saturated/dormant point analysis that drives network expansion.
with daily as (
    select
        pickup_point_id,
        to_date(arrived_at_point_at) as activity_date,
        count(*)                     as parcels_received
    from {{ ref('stg_parcels') }}
    where arrived_at_point_at is not null
    group by 1, 2
),
collections as (
    select
        pickup_point_id,
        to_date(collected_at) as activity_date,
        count(*)              as parcels_collected
    from {{ ref('stg_parcels') }}
    where collected_at is not null
    group by 1, 2
)
select
    coalesce(d.pickup_point_id, c.pickup_point_id)        as pickup_point_id,
    pp.pickup_point_key,
    coalesce(d.activity_date, c.activity_date)            as activity_date,
    to_number(to_char(coalesce(d.activity_date, c.activity_date), 'YYYYMMDD')) as date_key,
    coalesce(d.parcels_received, 0)                       as parcels_received,
    coalesce(c.parcels_collected, 0)                      as parcels_collected,
    pp.capacity_per_day,
    round(coalesce(d.parcels_received, 0) / nullif(pp.capacity_per_day, 0), 4) as capacity_utilization
from daily d
full outer join collections c
    on d.pickup_point_id = c.pickup_point_id and d.activity_date = c.activity_date
left join {{ ref('dim_pickup_point') }} pp
    on coalesce(d.pickup_point_id, c.pickup_point_id) = pp.pickup_point_id
   and pp.is_current
