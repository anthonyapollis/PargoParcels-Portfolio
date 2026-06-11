-- Monthly commercial scorecard per retailer: revenue, returns, SLA.
with parcels as (
    select
        date_trunc('month', p.created_at)::date as month,
        r.retailer_id, r.retailer_name, r.industry, r.tier,
        count(*)                                 as parcels,
        sum(p.billed_rate_zar)                   as revenue_zar,
        sum(p.delivery_cost_zar)                 as delivery_cost_zar,
        avg(p.parcel_value_zar)                  as avg_basket_zar,
        sum(iff(p.sla_met, 1, 0)) / count(*)     as sla_achievement
    from {{ ref('fct_parcels') }} p
    join {{ ref('dim_retailer') }} r on p.retailer_key = r.retailer_key
    group by 1, 2, 3, 4, 5
),
rets as (
    select date_trunc('month', return_initiated_at)::date as month,
           r.retailer_id,
           count(*)              as returns,
           sum(return_value_zar) as return_value_zar
    from {{ ref('fct_returns') }} f
    join {{ ref('dim_retailer') }} r on f.retailer_key = r.retailer_key
    group by 1, 2
)
select
    p.*,
    coalesce(rt.returns, 0)                          as returns,
    coalesce(rt.return_value_zar, 0)                 as return_value_zar,
    round(coalesce(rt.returns, 0) / nullif(p.parcels, 0), 4) as return_rate,
    p.revenue_zar - p.delivery_cost_zar              as gross_margin_zar,
    rank() over (partition by p.month order by p.revenue_zar desc) as revenue_rank
from parcels p
left join rets rt using (month, retailer_id)
