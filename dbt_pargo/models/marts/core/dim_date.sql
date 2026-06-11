-- The dimension the original spec forgot. SA-aware: trading seasons matter
-- more than holidays for parcel volume (Black Friday, festive, Janworth).
with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('history_start') ~ "' as date)",
        end_date="dateadd(year, 1, current_date)") }}
)
select
    to_number(to_char(date_day, 'YYYYMMDD'))   as date_key,
    date_day,
    year(date_day)                             as year,
    quarter(date_day)                          as quarter,
    month(date_day)                            as month,
    monthname(date_day)                        as month_name,
    dayofweekiso(date_day)                     as iso_day_of_week,
    dayname(date_day)                          as day_name,
    iso_day_of_week in (6, 7)                  as is_weekend,
    case
        when month(date_day) = 11 then 'Black Friday Season'
        when month(date_day) = 12 then 'Festive Peak'
        when month(date_day) = 1  then 'January Slump'
        else 'Standard Trading'
    end                                        as trading_season
from spine
