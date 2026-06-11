-- Monthly operational scorecard by province: feeds the Ops dashboard directly.
select
    date_trunc('month', created_at)::date     as month,
    province,
    count(*)                                  as parcels,
    avg(delivery_hours)                       as avg_delivery_hours,
    median(delivery_hours)                    as median_delivery_hours,
    avg(dwell_hours)                          as avg_dwell_hours,
    sum(iff(sla_met, 1, 0)) / count(*)        as sla_achievement,
    sum(iff(is_delivered, 1, 0)) / count(*)   as delivery_rate,
    sum(iff(is_rts, 1, 0)) / count(*)         as rts_rate,
    sum(iff(is_lost, 1, 0))                   as lost_parcels,
    sum(iff(is_damaged, 1, 0))                as damaged_parcels
from {{ ref('fct_parcels') }}
group by 1, 2
