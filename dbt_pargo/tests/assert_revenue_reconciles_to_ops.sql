-- Finance mart parcel counts must reconcile to the core fact (tolerance 0).
with ops as (select count(*) c from {{ ref('fct_parcels') }}),
fin as (select sum(parcels) c from {{ ref('mart_retailer_performance') }})
select * from ops join fin on ops.c <> fin.c
