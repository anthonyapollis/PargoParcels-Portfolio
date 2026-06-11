select
    r.return_id                                          as return_key,
    r.parcel_id                                          as parcel_key,
    dr.retailer_key,
    to_number(to_char(r.return_initiated_at,'YYYYMMDD')) as return_date_key,
    r.return_initiated_at,
    r.return_reason,
    r.return_value_zar,
    r.drop_off_point_id,
    datediff('day', p.collected_at, r.return_initiated_at) as days_to_return
from {{ ref('stg_returns') }} r
left join {{ ref('stg_parcels') }} p using (parcel_id)
left join {{ ref('dim_retailer') }} dr
    on r.retailer_id = dr.retailer_id and dr.is_current
