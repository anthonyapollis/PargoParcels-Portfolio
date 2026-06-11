import os
"""
Pargo DW — BATCH LOADER
========================
Most cost-efficient Snowflake loading pattern:
  1. PUT all files for a table to an internal stage in one pass
  2. One COPY INTO per table — Snowflake parallelises across all staged files
  3. PURGE=TRUE — stage cleaned up automatically after copy

This minimises warehouse active time vs file-by-file loops.
"""
import argparse, time
from pathlib import Path
import snowflake.connector

import os

SF = dict(
    account   = os.environ.get('SNOWFLAKE_ACCOUNT',   'your-account.region.aws'),
    user      = os.environ.get('SNOWFLAKE_USER',      'your-username'),
    password  = os.environ.get('SNOWFLAKE_PASSWORD',  ''),
    role      = os.environ.get('SNOWFLAKE_ROLE',      'ACCOUNTADMIN'),
    warehouse = os.environ.get('SNOWFLAKE_WAREHOUSE', 'LYRA_LOAD_WH'),
    database  = os.environ.get('SNOWFLAKE_DATABASE',  'PARGO_DW'),
    schema    = os.environ.get('SNOWFLAKE_SCHEMA',    'RAW'),
)

DDL = [
    "CREATE DATABASE IF NOT EXISTS PARGO_DW",
    "CREATE SCHEMA  IF NOT EXISTS PARGO_DW.RAW",
    "USE DATABASE PARGO_DW",
    "USE SCHEMA   RAW",
    "GRANT USAGE  ON DATABASE PARGO_DW             TO ROLE LYRA_TRANSFORMER",
    "GRANT USAGE  ON SCHEMA   PARGO_DW.RAW         TO ROLE LYRA_TRANSFORMER",
    "GRANT ALL    ON FUTURE TABLES IN SCHEMA PARGO_DW.RAW TO ROLE LYRA_TRANSFORMER",
    "CREATE STAGE IF NOT EXISTS PARGO_DW.RAW.BULK_STAGE",

    """CREATE TABLE IF NOT EXISTS DIM_COURIERS (
        COURIER_ID        NUMBER PRIMARY KEY,
        COURIER_NAME      VARCHAR(200),
        REGION            VARCHAR(100),
        VEHICLE_TYPE      VARCHAR(100),
        HIRED_DATE        TIMESTAMP_NTZ)""",

    """CREATE TABLE IF NOT EXISTS DIM_CUSTOMERS (
        CUSTOMER_ID         NUMBER PRIMARY KEY,
        CUSTOMER_NAME       VARCHAR(300),
        MOBILE_NUMBER       VARCHAR(50),
        PROVINCE            VARCHAR(100),
        CITY                VARCHAR(150),
        REGISTRATION_DATE   TIMESTAMP_NTZ,
        CUSTOMER_SEGMENT    VARCHAR(100),
        ACTIVE_FLAG         BOOLEAN)""",

    """CREATE TABLE IF NOT EXISTS DIM_PICKUP_POINTS (
        PICKUP_POINT_ID   NUMBER PRIMARY KEY,
        STORE_NAME        VARCHAR(300),
        PARTNER_NAME      VARCHAR(200),
        PROVINCE          VARCHAR(100),
        CITY              VARCHAR(150),
        LATITUDE          FLOAT,
        LONGITUDE         FLOAT,
        OPENING_DATE      TIMESTAMP_NTZ,
        CAPACITY_PER_DAY  NUMBER,
        STATUS            VARCHAR(50))""",

    """CREATE TABLE IF NOT EXISTS DIM_RETAILERS (
        RETAILER_ID           NUMBER PRIMARY KEY,
        RETAILER_NAME         VARCHAR(300),
        INDUSTRY              VARCHAR(150),
        TIER                  VARCHAR(50),
        CONTRACT_START_DATE   TIMESTAMP_NTZ,
        RATE_PER_PARCEL_ZAR   FLOAT,
        INTEGRATION_TYPE      VARCHAR(100))""",

    """CREATE TABLE IF NOT EXISTS FACT_ORDERS (
        ORDER_ID          NUMBER, CUSTOMER_ID NUMBER, RETAILER_ID NUMBER,
        ORDER_CREATED_AT  TIMESTAMP_NTZ, ORDER_VALUE_ZAR FLOAT, CHANNEL VARCHAR(100),
        LOAD_YEAR NUMBER, LOAD_MONTH VARCHAR(7)
    ) CLUSTER BY (LOAD_YEAR, TO_DATE(ORDER_CREATED_AT))""",

    """CREATE TABLE IF NOT EXISTS FACT_PARCELS (
        PARCEL_ID NUMBER, ORDER_ID NUMBER, CUSTOMER_ID NUMBER, RETAILER_ID NUMBER,
        PICKUP_POINT_ID NUMBER, COURIER_ID NUMBER, WAYBILL_NUMBER VARCHAR(50),
        CREATED_AT TIMESTAMP_NTZ, DISPATCHED_AT TIMESTAMP_NTZ,
        ARRIVED_AT_POINT_AT TIMESTAMP_NTZ, NOTIFIED_AT TIMESTAMP_NTZ,
        COLLECTED_AT TIMESTAMP_NTZ, RTS_AT TIMESTAMP_NTZ,
        PARCEL_STATUS VARCHAR(50), PARCEL_VALUE_ZAR FLOAT, PARCEL_WEIGHT_KG FLOAT,
        DELIVERY_COST_ZAR FLOAT, SERVICE_TYPE VARCHAR(50), PROVINCE VARCHAR(100),
        LOAD_YEAR NUMBER, LOAD_MONTH VARCHAR(7)
    ) CLUSTER BY (LOAD_YEAR, TO_DATE(CREATED_AT))""",

    """CREATE TABLE IF NOT EXISTS FACT_TRACKING_EVENTS (
        TRACKING_EVENT_ID NUMBER, PARCEL_ID NUMBER, EVENT_TYPE VARCHAR(100),
        EVENT_TIMESTAMP TIMESTAMP_NTZ, LATITUDE FLOAT, LONGITUDE FLOAT,
        STATUS VARCHAR(100), SOURCE_SYSTEM VARCHAR(100),
        LOAD_YEAR NUMBER, LOAD_MONTH VARCHAR(7)
    ) CLUSTER BY (LOAD_YEAR, TO_DATE(EVENT_TIMESTAMP))""",

    """CREATE TABLE IF NOT EXISTS FACT_RETURNS (
        RETURN_ID NUMBER, PARCEL_ID NUMBER, RETAILER_ID NUMBER,
        RETURN_INITIATED_AT TIMESTAMP_NTZ, RETURN_REASON VARCHAR(200),
        RETURN_VALUE_ZAR FLOAT, DROP_OFF_POINT_ID NUMBER,
        LOAD_YEAR NUMBER, LOAD_MONTH VARCHAR(7)
    ) CLUSTER BY (LOAD_YEAR, TO_DATE(RETURN_INITIATED_AT))""",
]

# One COPY per table — processes all files in stage matching the prefix
DIM_COPY = """
    COPY INTO {table} FROM @BULK_STAGE
    FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE SNAPPY_COMPRESSION=TRUE)
    PATTERN = '.*{prefix}.*\\.parquet.*'
    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
    PURGE = TRUE"""

FACT_COPY = {
    "FACT_ORDERS": """
        COPY INTO FACT_ORDERS
            (ORDER_ID,CUSTOMER_ID,RETAILER_ID,ORDER_CREATED_AT,
             ORDER_VALUE_ZAR,CHANNEL,LOAD_YEAR,LOAD_MONTH)
        FROM (SELECT
            $1:order_id::NUMBER, $1:customer_id::NUMBER, $1:retailer_id::NUMBER,
            $1:order_created_at::TIMESTAMP_NTZ, $1:order_value_zar::FLOAT,
            $1:channel::VARCHAR, $1:year::NUMBER, $1:month::VARCHAR
        FROM @BULK_STAGE)
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE SNAPPY_COMPRESSION=TRUE)
        PATTERN = '.*orders_.*\\.parquet.*'
        PURGE = TRUE""",

    "FACT_PARCELS": """
        COPY INTO FACT_PARCELS
            (PARCEL_ID,ORDER_ID,CUSTOMER_ID,RETAILER_ID,PICKUP_POINT_ID,
             COURIER_ID,WAYBILL_NUMBER,CREATED_AT,DISPATCHED_AT,ARRIVED_AT_POINT_AT,
             NOTIFIED_AT,COLLECTED_AT,RTS_AT,PARCEL_STATUS,PARCEL_VALUE_ZAR,
             PARCEL_WEIGHT_KG,DELIVERY_COST_ZAR,SERVICE_TYPE,PROVINCE,LOAD_YEAR,LOAD_MONTH)
        FROM (SELECT
            $1:parcel_id::NUMBER, $1:order_id::NUMBER, $1:customer_id::NUMBER,
            $1:retailer_id::NUMBER, $1:pickup_point_id::NUMBER, $1:courier_id::NUMBER,
            $1:waybill_number::VARCHAR, $1:created_at::TIMESTAMP_NTZ,
            $1:dispatched_at::TIMESTAMP_NTZ, $1:arrived_at_point_at::TIMESTAMP_NTZ,
            $1:notified_at::TIMESTAMP_NTZ, $1:collected_at::TIMESTAMP_NTZ,
            $1:rts_at::TIMESTAMP_NTZ, $1:parcel_status::VARCHAR,
            $1:parcel_value_zar::FLOAT, $1:parcel_weight_kg::FLOAT,
            $1:delivery_cost_zar::FLOAT, $1:service_type::VARCHAR, $1:province::VARCHAR,
            $1:year::NUMBER, $1:month::VARCHAR
        FROM @BULK_STAGE)
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE SNAPPY_COMPRESSION=TRUE)
        PATTERN = '.*parcels_.*\\.parquet.*'
        PURGE = TRUE""",

    "FACT_TRACKING_EVENTS": """
        COPY INTO FACT_TRACKING_EVENTS
            (TRACKING_EVENT_ID,PARCEL_ID,EVENT_TYPE,EVENT_TIMESTAMP,
             LATITUDE,LONGITUDE,STATUS,SOURCE_SYSTEM,LOAD_YEAR,LOAD_MONTH)
        FROM (SELECT
            $1:tracking_event_id::NUMBER, $1:parcel_id::NUMBER,
            $1:event_type::VARCHAR, $1:event_timestamp::TIMESTAMP_NTZ,
            $1:latitude::FLOAT, $1:longitude::FLOAT,
            $1:status::VARCHAR, $1:source_system::VARCHAR,
            $1:year::NUMBER, $1:month::VARCHAR
        FROM @BULK_STAGE)
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE SNAPPY_COMPRESSION=TRUE)
        PATTERN = '.*tracking_events_.*\\.parquet.*'
        PURGE = TRUE""",

    "FACT_RETURNS": """
        COPY INTO FACT_RETURNS
            (RETURN_ID,PARCEL_ID,RETAILER_ID,RETURN_INITIATED_AT,
             RETURN_REASON,RETURN_VALUE_ZAR,DROP_OFF_POINT_ID,LOAD_YEAR,LOAD_MONTH)
        FROM (SELECT
            $1:return_id::NUMBER, $1:parcel_id::NUMBER, $1:retailer_id::NUMBER,
            $1:return_initiated_at::TIMESTAMP_NTZ, $1:return_reason::VARCHAR,
            $1:return_value_zar::FLOAT, $1:drop_off_point_id::NUMBER,
            $1:year::NUMBER, $1:month::VARCHAR
        FROM @BULK_STAGE)
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE SNAPPY_COMPRESSION=TRUE)
        PATTERN = '.*returns_.*\\.parquet.*'
        PURGE = TRUE""",
}


def put_all(cur, files: list[Path], label: str):
    """PUT all files in one batch. Snowflake connector sends them in parallel."""
    t0 = time.time()
    total = 0
    for f in files:
        cur.execute(
            f"PUT 'file://{f.as_posix()}' @BULK_STAGE "
            f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE PARALLEL=8"
        )
        total += 1
        if total % 10 == 0:
            print(f'    PUT {total}/{len(files)} {label}...', flush=True)
    print(f'    PUT done: {total} files in {time.time()-t0:.1f}s')


def copy_into(cur, table: str, sql: str) -> int:
    t0 = time.time()
    cur.execute(sql.strip())
    rows = sum(r[3] for r in cur.fetchall())
    print(f'    COPY INTO {table}: {rows:,} rows in {time.time()-t0:.1f}s')
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='../data/raw')
    ap.add_argument('--recreate', action='store_true')
    a = ap.parse_args()
    data_dir = Path(a.data_dir).resolve()

    print('='*70)
    print('PARGO DW — BATCH LOADER')
    print(f'  PUT all files -> stage, then ONE COPY INTO per table')
    print(f'  data dir: {data_dir}')
    print('='*70)

    con = snowflake.connector.connect(**SF)
    cur = con.cursor()
    print(f'\n[1] {cur.execute("SELECT CURRENT_USER(),CURRENT_ACCOUNT(),CURRENT_WAREHOUSE()").fetchone()}')

    print('\n[2] DDL...')
    if a.recreate:
        for t in ['FACT_RETURNS','FACT_TRACKING_EVENTS','FACT_PARCELS','FACT_ORDERS',
                  'DIM_RETAILERS','DIM_PICKUP_POINTS','DIM_CUSTOMERS','DIM_COURIERS']:
            cur.execute(f'DROP TABLE IF EXISTS {t}')
    for sql in DDL:
        cur.execute(sql.strip())
    print('    Tables + stage ready.')

    print('\n[3] PUT dimensions + COPY...')
    dims = [
        ('DIM_COURIERS',      [data_dir/'couriers.parquet'],      'couriers'),
        ('DIM_CUSTOMERS',     [data_dir/'customers.parquet'],     'customers'),
        ('DIM_PICKUP_POINTS', [data_dir/'pickup_points.parquet'], 'pickup_points'),
        ('DIM_RETAILERS',     [data_dir/'retailers.parquet'],     'retailers'),
    ]
    for table, files, prefix in dims:
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        if cur.fetchone()[0] > 0:
            print(f'  {table}: already loaded')
            continue
        existing = [f for f in files if f.exists()]
        if not existing:
            print(f'  {table}: file not found')
            continue
        print(f'  {table}:')
        put_all(cur, existing, table)
        sql = DIM_COPY.replace('{table}', table).replace('{prefix}', prefix)
        copy_into(cur, table, sql)

    print('\n[4] PUT all fact parquet files...')
    fact_entities = {
        'FACT_ORDERS':          'orders',
        'FACT_PARCELS':         'parcels',
        'FACT_TRACKING_EVENTS': 'tracking_events',
        'FACT_RETURNS':         'returns',
    }
    for table, entity in fact_entities.items():
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        if cur.fetchone()[0] > 0:
            print(f'  {table}: already loaded — skipping')
            continue
        files = sorted((data_dir/entity).glob('year=*/month=*/*.parquet'))
        print(f'  {table}: {len(files)} files')
        put_all(cur, files, entity)

        print(f'  COPY INTO {table} (all files at once)...')
        copy_into(cur, table, FACT_COPY[table])

    print('\n[5] Final row counts:')
    for t in ['DIM_COURIERS','DIM_CUSTOMERS','DIM_PICKUP_POINTS','DIM_RETAILERS',
              'FACT_ORDERS','FACT_PARCELS','FACT_TRACKING_EVENTS','FACT_RETURNS']:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'  {t:30s} {cur.fetchone()[0]:>15,}')

    print('\n[6] Verification:')
    for label, sql in [
        ('Parcels by year',  'SELECT LOAD_YEAR, COUNT(*) n FROM FACT_PARCELS GROUP BY 1 ORDER BY 1'),
        ('Status mix',       'SELECT PARCEL_STATUS, COUNT(*) FROM FACT_PARCELS GROUP BY 1 ORDER BY 2 DESC'),
        ('Events by source', 'SELECT SOURCE_SYSTEM, COUNT(*) FROM FACT_TRACKING_EVENTS GROUP BY 1 ORDER BY 2 DESC'),
        ('Top 5 retailers',  'SELECT r.RETAILER_NAME, COUNT(*) n FROM FACT_PARCELS p JOIN DIM_RETAILERS r ON p.RETAILER_ID=r.RETAILER_ID GROUP BY 1 ORDER BY 2 DESC LIMIT 5'),
    ]:
        print(f'\n  -- {label}')
        cur.execute(sql)
        for row in cur.fetchall():
            print(f'    {row}')

    cur.close()
    con.close()
    print('\nDone.')


if __name__ == '__main__':
    main()
