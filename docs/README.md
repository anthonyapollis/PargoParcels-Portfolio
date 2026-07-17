# PargoParcels — Enterprise Analytics Engineering Portfolio

A full modern-data-stack simulation of a South African click-and-collect logistics network:
**PostgreSQL OLTP → partitioned Parquet → Snowflake (RAW/STAGING/MARTS) → dbt → BI**.

**11,059,646 rows generated** at demo scale; the same scripts produce **220M+ rows** with `--scale 1.0`.

## Why this project

Pargo's business runs on a parcel lifecycle: a retailer dispatches, a courier moves, a parcel
arrives at one of 4,000+ pickup points, a customer is notified, then collects — or doesn't, and
the parcel returns to sender. Every number on their homepage (1.25-day average delivery, 4,000+
points) is a mart-layer aggregate over exactly this lifecycle. This project builds that layer.

## Quick start

```bash
# 1. Generate data (demo ~11M rows, ~6 min)
cd data_generator && python generate_pargo_data.py --scale 0.04

# 2. PostgreSQL OLTP
createdb pargo_oltp
psql -d pargo_oltp -f postgres/01_create_schema.sql
python postgres/load_postgres.py --dsn postgresql://user:pass@localhost:5432/pargo_oltp

# 3. Snowflake (roles, warehouses, RAW, COPY INTO)
snowsql -f snowflake/01_platform_setup.sql
# PUT each table's parquet to @STG_PARGO_LANDING/<table>/ then run the COPY INTO block

# 4. dbt
cd dbt_pargo
cp profiles.example.yml ~/.dbt/profiles.yml   # edit account/user
dbt deps && dbt seed && dbt snapshot && dbt build && dbt source freshness
```

## What's in the box

| Path | Contents |
|---|---|
| `data_generator/` | Seeded, chunked, vectorised generator. `--scale 1.0` = 30M parcels / ~209M events |
| `data/raw/` | Generated Parquet, partitioned `year=/month=`, plus dimension CSVs |
| `postgres/` | 3NF OLTP DDL + COPY bulk loader |
| `snowflake/` | Roles, 3 warehouses, RAW DDL with `CLUSTER BY`, COPY INTO |
| `dbt_pargo/` | 24 models, 2 SCD2 snapshots, seed, 30+ schema tests, 4 business-rule tests, freshness SLAs |
| `excel/` | 10-sheet data workbook, formula-driven KPI summary (2,256 formulas, 0 errors) |
| `ebook/` | 11-page branded project document with ERDs, methodology and findings |

## Design decisions (the short version)

1. **`int_parcel_milestones` is the single source of truth** for every duration and SLA metric.
   Finance and ops can never disagree about how `delivery_hours` is computed — it's one file.
2. **SCD2 only where money depends on it** (retailer rate cards, point capacity). The 10M-row
   customer dimension is deliberately Type 1.
3. **Facts join SCD2 dims as-of parcel creation** — current-flag joins silently corrupt
   historic revenue when a rate card changes.
4. **Incremental merge with a 3-day lookback** on the two big facts (30M / 150M rows at scale)
   absorbs late-arriving scans without full rebuilds.
5. **Partition by year/month, cluster by province.** Partitioning Parquet by province as well
   would create 13,000+ tiny files; Snowflake clustering achieves the pruning without the mess.
6. **RAW is deliberately dirty** (~0.5%: dupes, null/negative weights, orphan events, clock skew).
   Staging quarantines, tests prove it, and the lineage shows the cleaning — because real
   pipelines aren't clean, and a portfolio that pretends they are isn't credible.
7. **Tracking events derive from the same milestones as the fact table**, so the event log and
   `fct_parcels` reconcile by construction.

## Headline figures (demo scale, 36 months)

- 1,200,931 parcels · 8,368,335 tracking events · 999,961 orders · 85,769 returns · 400,000 customers
- Avg delivery **1.12 days** (Gauteng 22h) · delivery success **92.0%** · 48h SLA **95.8%**
- Avg dwell at point **36h** · RTS **5.5%** · Black Friday ≈ **1.9×** baseline
- Fashion returns **14.1%** vs pharmacy **2.0%** · top-10 clients ≈ **49%** of revenue

*Independent analytics case study. All data is synthetic; no affiliation with Pargo (Pty) Ltd.*
