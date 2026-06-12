import os
"""
Pargo DW — Snowflake loader
============================
Reads the parquet partitions under data/raw and loads them into
PARGO_DW.RAW via an internal stage + COPY INTO (most cost-efficient
pattern — single COPY per file, no per-row round-trips).

Usage:
    python snowflake_loader.py [--data-dir ../data/raw] [--recreate]

Pass --recreate to DROP + recreate all tables (safe for dev; skip in prod).
"""
import argparse, os, sys, time
from pathlib import Path

import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd

# ── Snowflake creds ───────────────────────────────────────────────────────────
import os

SF = dict(
    account   = os.environ.get('SNOWFLAKE_ACCOUNT',   'your-account.region.aws'),
    user      = os.environ.get('SNOWFLAKE_USER',      'your-username'),
    password  = os.environ.get('SNOWFLAKE_PASSWORD',  ''),
    role      = os.environ.get('SNOWFLAKE_ROLE',      'ACCOUNTADMIN'),
    warehouse = os.environ.get('SNOWFLAKE_WAREHOUSE', 'PARGO_LOAD_WH'),
    database  = os.environ.get('SNOWFLAKE_DATABASE',  'PARGO_DW'),
    schema    = os.environ.get('SNOWFLAKE_SCHEMA',    'RAW'),
)

# ── DDL ───────────────────────────────────────────────────────────────────────
SETUP_SQL = """
CREATE DATABASE IF NOT EXISTS PARGO_DW;
CREATE SCHEMA  IF NOT EXISTS PARGO_DW.RAW;
CREATE SCHEMA  IF NOT EXISTS PARGO_DW.STAGING;

USE DATABASE PARGO_DW;
USE SCHEMA   RAW;

GRANT USAGE ON DATABASE PARGO_DW          TO ROLE LYRA_TRANSFORMER;
GRANT USAGE ON SCHEMA   PARGO_DW.RAW      TO ROLE LYRA_TRANSFORMER;
GRANT USAGE ON SCHEMA   PARGO_DW.STAGING  TO ROLE LYRA_TRANSFORMER;
GRANT ALL   ON ALL TABLES IN SCHEMA PARGO_DW.RAW TO ROLE LYRA_TRANSFORMER;
GRANT ALL   ON FUTURE TABLES IN SCHEMA PARGO_DW.RAW TO ROLE LYRA_TRANSFORMER;
"""

TABLES = {
    "DIM_COURIERS": """
        CREATE TABLE IF NOT EXISTS DIM_COURIERS (
            COURIER_ID        NUMBER        NOT NULL PRIMARY KEY,
            COURIER_NAME      VARCHAR(200),
            REGION            VARCHAR(100),
            VEHICLE_TYPE      VARCHAR(100),
            HIRED_DATE        TIMESTAMP_NTZ
        )""",

    "DIM_CUSTOMERS": """
        CREATE TABLE IF NOT EXISTS DIM_CUSTOMERS (
            CUSTOMER_ID         NUMBER        NOT NULL PRIMARY KEY,
            CUSTOMER_NAME       VARCHAR(300),
            MOBILE_NUMBER       VARCHAR(50),
            PROVINCE            VARCHAR(100),
            CITY                VARCHAR(150),
            REGISTRATION_DATE   TIMESTAMP_NTZ,
            CUSTOMER_SEGMENT    VARCHAR(100),
            ACTIVE_FLAG         BOOLEAN
        )""",

    "DIM_PICKUP_POINTS": """
        CREATE TABLE IF NOT EXISTS DIM_PICKUP_POINTS (
            PICKUP_POINT_ID   NUMBER        NOT NULL PRIMARY KEY,
            STORE_NAME        VARCHAR(300),
            PARTNER_NAME      VARCHAR(200),
            PROVINCE          VARCHAR(100),
            CITY              VARCHAR(150),
            LATITUDE          FLOAT,
            LONGITUDE         FLOAT,
            OPENING_DATE      TIMESTAMP_NTZ,
            CAPACITY_PER_DAY  NUMBER,
            STATUS            VARCHAR(50)
        )""",

    "DIM_RETAILERS": """
        CREATE TABLE IF NOT EXISTS DIM_RETAILERS (
            RETAILER_ID           NUMBER        NOT NULL PRIMARY KEY,
            RETAILER_NAME         VARCHAR(300),
            INDUSTRY              VARCHAR(150),
            TIER                  VARCHAR(50),
            CONTRACT_START_DATE   TIMESTAMP_NTZ,
            RATE_PER_PARCEL_ZAR   FLOAT,
            INTEGRATION_TYPE      VARCHAR(100)
        )""",

    "FACT_ORDERS": """
        CREATE TABLE IF NOT EXISTS FACT_ORDERS (
            ORDER_ID          NUMBER        NOT NULL,
            CUSTOMER_ID       NUMBER,
            RETAILER_ID       NUMBER,
            ORDER_CREATED_AT  TIMESTAMP_NTZ,
            ORDER_VALUE_ZAR   FLOAT,
            CHANNEL           VARCHAR(100),
            LOAD_YEAR         NUMBER,
            LOAD_MONTH        VARCHAR(7)
        ) CLUSTER BY (LOAD_YEAR, TO_DATE(ORDER_CREATED_AT))""",

    "FACT_PARCELS": """
        CREATE TABLE IF NOT EXISTS FACT_PARCELS (
            PARCEL_ID              NUMBER NOT NULL,
            ORDER_ID               NUMBER,
            CUSTOMER_ID            NUMBER,
            RETAILER_ID            NUMBER,
            PICKUP_POINT_ID        NUMBER,
            COURIER_ID             NUMBER,
            WAYBILL_NUMBER         VARCHAR(50),
            CREATED_AT             TIMESTAMP_NTZ,
            DISPATCHED_AT          TIMESTAMP_NTZ,
            ARRIVED_AT_POINT_AT    TIMESTAMP_NTZ,
            NOTIFIED_AT            TIMESTAMP_NTZ,
            COLLECTED_AT           TIMESTAMP_NTZ,
            RTS_AT                 TIMESTAMP_NTZ,
            PARCEL_STATUS          VARCHAR(50),
            PARCEL_VALUE_ZAR       FLOAT,
            PARCEL_WEIGHT_KG       FLOAT,
            DELIVERY_COST_ZAR      FLOAT,
            SERVICE_TYPE           VARCHAR(50),
            PROVINCE               VARCHAR(100),
            LOAD_YEAR              NUMBER,
            LOAD_MONTH             VARCHAR(7)
        ) CLUSTER BY (LOAD_YEAR, TO_DATE(CREATED_AT))""",

    "FACT_TRACKING_EVENTS": """
        CREATE TABLE IF NOT EXISTS FACT_TRACKING_EVENTS (
            TRACKING_EVENT_ID  NUMBER NOT NULL,
            PARCEL_ID          NUMBER,
            EVENT_TYPE         VARCHAR(100),
            EVENT_TIMESTAMP    TIMESTAMP_NTZ,
            LATITUDE           FLOAT,
            LONGITUDE          FLOAT,
            STATUS             VARCHAR(100),
            SOURCE_SYSTEM      VARCHAR(100),
            LOAD_YEAR          NUMBER,
            LOAD_MONTH         VARCHAR(7)
        ) CLUSTER BY (LOAD_YEAR, TO_DATE(EVENT_TIMESTAMP))""",

    "FACT_RETURNS": """
        CREATE TABLE IF NOT EXISTS FACT_RETURNS (
            RETURN_ID             NUMBER NOT NULL,
            PARCEL_ID             NUMBER,
            RETAILER_ID           NUMBER,
            RETURN_INITIATED_AT   TIMESTAMP_NTZ,
            RETURN_REASON         VARCHAR(200),
            RETURN_VALUE_ZAR      FLOAT,
            DROP_OFF_POINT_ID     NUMBER,
            LOAD_YEAR             NUMBER,
            LOAD_MONTH            VARCHAR(7)
        ) CLUSTER BY (LOAD_YEAR, TO_DATE(RETURN_INITIATED_AT))""",
}

# Column name map: parquet column → Snowflake column (uppercase)
def normalise_df(df, year, month):
    df = df.copy()
    df.columns = [c.upper() for c in df.columns]
    # strip tz from any timestamp columns
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = df[col].dt.tz_localize(None)
            except TypeError:
                df[col] = df[col].dt.tz_convert(None)
    # Only add partition columns for fact tables (year > 0)
    if year > 0:
        df.rename(columns={'YEAR': 'LOAD_YEAR', 'MONTH': 'LOAD_MONTH'}, inplace=True)
        if 'LOAD_YEAR' not in df.columns:
            df['LOAD_YEAR'] = year
        if 'LOAD_MONTH' not in df.columns:
            df['LOAD_MONTH'] = f'{year}-{month:02d}'
    else:
        # Dimension tables: drop any stray YEAR/MONTH columns
        df.drop(columns=[c for c in ('YEAR', 'MONTH') if c in df.columns], inplace=True)
    return df


def run_sql(cur, sql, label=''):
    for stmt in sql.strip().split(';'):
        stmt = stmt.strip()
        if stmt:
            if label:
                print(f'  [{label}] {stmt[:100]}')
            cur.execute(stmt)


def load_table_from_parquet(sfcon, table, parquet_path, year, month):
    df = pd.read_parquet(parquet_path)
    df = normalise_df(df, year, month)
    t0 = time.time()
    # quote_identifiers=True prevents YEAR (reserved word) from being unquoted
    success, nchunks, nrows, output = write_pandas(
        sfcon, df, table,
        database='PARGO_DW', schema='RAW',
        auto_create_table=False,
        quote_identifiers=True,
        chunk_size=200_000,
    )
    elapsed = time.time() - t0
    return nrows, elapsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='../data/raw')
    ap.add_argument('--recreate', action='store_true',
                    help='DROP and recreate all tables (dev only)')
    a = ap.parse_args()
    data_dir = Path(a.data_dir).resolve()

    print('='*70)
    print('PARGO DW — SNOWFLAKE LOADER')
    print(f'  data dir : {data_dir}')
    print(f'  account  : {SF["account"]}')
    print('='*70)

    # ── Connect ───────────────────────────────────────────────────────────────
    print('\n[1] Connecting…')
    sfcon = snowflake.connector.connect(**SF)
    cur = sfcon.cursor()
    print(f'  OK: {cur.execute("SELECT CURRENT_USER(), CURRENT_ACCOUNT()").fetchone()}')

    # ── Setup DB / schema / grants ────────────────────────────────────────────
    print('\n[2] Creating PARGO_DW database + RAW schema…')
    run_sql(cur, SETUP_SQL)

    # ── Tables ────────────────────────────────────────────────────────────────
    print('\n[3] Creating tables…')
    cur.execute('USE DATABASE PARGO_DW')
    cur.execute('USE SCHEMA RAW')

    if a.recreate:
        for tbl in TABLES:
            cur.execute(f'DROP TABLE IF EXISTS {tbl}')
            print(f'  Dropped {tbl}')

    for tbl, ddl in TABLES.items():
        cur.execute(ddl.strip())
        print(f'  Created/verified {tbl}')

    # ── Dimensions ────────────────────────────────────────────────────────────
    print('\n[4] Loading dimension tables…')
    dim_map = {
        'DIM_COURIERS':      'couriers.parquet',
        'DIM_CUSTOMERS':     'customers.parquet',
        'DIM_PICKUP_POINTS': 'pickup_points.parquet',
        'DIM_RETAILERS':     'retailers.parquet',
    }
    for tbl, fname in dim_map.items():
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        if cur.fetchone()[0] > 0:
            print(f'  {tbl}: already loaded — skipping.')
            continue
        path = data_dir / fname
        if not path.exists():
            print(f'  {tbl}: {path} not found — skipping.')
            continue
        nrows, elapsed = load_table_from_parquet(sfcon, tbl, path, 0, 0)
        print(f'  {tbl}: {nrows:,} rows in {elapsed:.1f}s')

    # ── Facts (partitioned) ───────────────────────────────────────────────────
    fact_map = {
        'FACT_ORDERS':          'orders',
        'FACT_PARCELS':         'parcels',
        'FACT_TRACKING_EVENTS': 'tracking_events',
        'FACT_RETURNS':         'returns',
    }
    print('\n[5] Loading fact tables (month-by-month)…')
    grand_totals = {t: 0 for t in fact_map}

    # collect all (year, month) combos that exist for at least one entity
    all_periods = set()
    for entity in fact_map.values():
        for f in (data_dir / entity).glob('year=*/month=*/*.parquet'):
            parts = f.parts
            y = int([p for p in parts if p.startswith('year=')][-1].split('=')[1])
            m = int([p for p in parts if p.startswith('month=')][-1].split('=')[1])
            all_periods.add((y, m))

    all_periods = sorted(all_periods)
    print(f'  Found {len(all_periods)} year/month partitions')

    for yi, (year, month) in enumerate(all_periods, 1):
        for tbl, entity in fact_map.items():
            pattern = data_dir / entity / f'year={year}' / f'month={month:02d}'
            files = list(pattern.glob('*.parquet'))
            if not files:
                continue

            # skip if already loaded for this month (idempotent)
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE LOAD_YEAR={year} AND LOAD_MONTH='{year}-{month:02d}'")
            if cur.fetchone()[0] > 0:
                continue

            for f in files:
                nrows, elapsed = load_table_from_parquet(sfcon, tbl, f, year, month)
                grand_totals[tbl] += nrows

        print(f'  [{yi:>3}/{len(all_periods)}] {year}-{month:02d} done | '
              + ' | '.join(f'{t.split("_")[1][:4]}={grand_totals[t]:>10,}' for t in fact_map),
              flush=True)

    # ── Final counts ─────────────────────────────────────────────────────────
    print('\n[6] Final row counts:')
    all_tables = list(dim_map.keys()) + list(fact_map.keys())
    for tbl in all_tables:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        cnt = cur.fetchone()[0]
        print(f'  {tbl:30s} {cnt:>15,}')

    # ── Verification queries ──────────────────────────────────────────────────
    print('\n[7] Verification queries:')
    checks = [
        ("Parcels by year",
         "SELECT LOAD_YEAR, COUNT(*) n, ROUND(AVG(PARCEL_VALUE_ZAR),2) avg_val "
         "FROM FACT_PARCELS GROUP BY LOAD_YEAR ORDER BY LOAD_YEAR"),
        ("Parcel status breakdown",
         "SELECT PARCEL_STATUS, COUNT(*) n FROM FACT_PARCELS GROUP BY 1 ORDER BY 2 DESC"),
        ("Events by source system",
         "SELECT SOURCE_SYSTEM, COUNT(*) n FROM FACT_TRACKING_EVENTS GROUP BY 1 ORDER BY 2 DESC"),
        ("Returns by reason",
         "SELECT RETURN_REASON, COUNT(*) n FROM FACT_RETURNS GROUP BY 1 ORDER BY 2 DESC"),
        ("Top 5 retailers by parcels",
         "SELECT r.RETAILER_NAME, COUNT(*) n FROM FACT_PARCELS p "
         "JOIN DIM_RETAILERS r ON p.RETAILER_ID=r.RETAILER_ID "
         "GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
        ("Orphan events (data quality)",
         "SELECT COUNT(*) orphan_events FROM FACT_TRACKING_EVENTS e "
         "WHERE NOT EXISTS (SELECT 1 FROM FACT_PARCELS p WHERE p.PARCEL_ID=e.PARCEL_ID)"),
    ]
    for label, sql in checks:
        print(f'\n  -- {label}')
        cur.execute(sql)
        for row in cur.fetchall():
            print(f'    {row}')

    cur.close()
    sfcon.close()
    print('\nAll done.')


if __name__ == '__main__':
    main()
