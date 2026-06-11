import os
"""
Pargo DW — TRUE BULK LOADER
PUT parquet files directly to Snowflake internal stage, then COPY INTO
with server-side column mapping. No pandas re-serialization.
Typical throughput: 500K-2M rows/sec vs ~20K rows/sec for write_pandas.
"""
import argparse, os, time
from pathlib import Path
import snowflake.connector
import pandas as pd

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

SETUP_SQL = [
    "CREATE DATABASE IF NOT EXISTS PARGO_DW",
    "CREATE SCHEMA IF NOT EXISTS PARGO_DW.RAW",
    "CREATE SCHEMA IF NOT EXISTS PARGO_DW.STAGING",
    "USE DATABASE PARGO_DW",
    "USE SCHEMA RAW",
    "GRANT USAGE ON DATABASE PARGO_DW TO ROLE LYRA_TRANSFORMER",
    "GRANT USAGE ON SCHEMA PARGO_DW.RAW TO ROLE LYRA_TRANSFORMER",
    "GRANT ALL ON FUTURE TABLES IN SCHEMA PARGO_DW.RAW TO ROLE LYRA_TRANSFORMER",
    # Internal stage for bulk loading
    "CREATE STAGE IF NOT EXISTS PARGO_DW.RAW.BULK_STAGE",
]

TABLES = {
    "DIM_COURIERS": """
        CREATE TABLE IF NOT EXISTS DIM_COURIERS (
            COURIER_ID        NUMBER       NOT NULL PRIMARY KEY,
            COURIER_NAME      VARCHAR(200),
            REGION            VARCHAR(100),
            VEHICLE_TYPE      VARCHAR(100),
            HIRED_DATE        TIMESTAMP_NTZ
        )""",
    "DIM_CUSTOMERS": """
        CREATE TABLE IF NOT EXISTS DIM_CUSTOMERS (
            CUSTOMER_ID         NUMBER       NOT NULL PRIMARY KEY,
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
            PICKUP_POINT_ID   NUMBER       NOT NULL PRIMARY KEY,
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
            RETAILER_ID           NUMBER       NOT NULL PRIMARY KEY,
            RETAILER_NAME         VARCHAR(300),
            INDUSTRY              VARCHAR(150),
            TIER                  VARCHAR(50),
            CONTRACT_START_DATE   TIMESTAMP_NTZ,
            RATE_PER_PARCEL_ZAR   FLOAT,
            INTEGRATION_TYPE      VARCHAR(100)
        )""",
    "FACT_ORDERS": """
        CREATE TABLE IF NOT EXISTS FACT_ORDERS (
            ORDER_ID          NUMBER,
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
            PARCEL_ID              NUMBER,
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
            TRACKING_EVENT_ID  NUMBER,
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
            RETURN_ID             NUMBER,
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

# COPY INTO SQL for each fact table — maps parquet column names to table columns.
# Parquet files have 'year'/'month'; table has LOAD_YEAR/LOAD_MONTH.
FACT_COPY = {
    "FACT_ORDERS": """
        COPY INTO FACT_ORDERS (
            ORDER_ID, CUSTOMER_ID, RETAILER_ID, ORDER_CREATED_AT,
            ORDER_VALUE_ZAR, CHANNEL, LOAD_YEAR, LOAD_MONTH
        )
        FROM (SELECT
            $1:order_id::NUMBER,
            $1:customer_id::NUMBER,
            $1:retailer_id::NUMBER,
            $1:order_created_at::TIMESTAMP_NTZ,
            $1:order_value_zar::FLOAT,
            $1:channel::VARCHAR,
            $1:year::NUMBER,
            $1:month::VARCHAR
        FROM @BULK_STAGE/{file})
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE)
        PURGE = TRUE""",

    "FACT_PARCELS": """
        COPY INTO FACT_PARCELS (
            PARCEL_ID, ORDER_ID, CUSTOMER_ID, RETAILER_ID, PICKUP_POINT_ID,
            COURIER_ID, WAYBILL_NUMBER, CREATED_AT, DISPATCHED_AT,
            ARRIVED_AT_POINT_AT, NOTIFIED_AT, COLLECTED_AT, RTS_AT,
            PARCEL_STATUS, PARCEL_VALUE_ZAR, PARCEL_WEIGHT_KG,
            DELIVERY_COST_ZAR, SERVICE_TYPE, PROVINCE, LOAD_YEAR, LOAD_MONTH
        )
        FROM (SELECT
            $1:parcel_id::NUMBER,
            $1:order_id::NUMBER,
            $1:customer_id::NUMBER,
            $1:retailer_id::NUMBER,
            $1:pickup_point_id::NUMBER,
            $1:courier_id::NUMBER,
            $1:waybill_number::VARCHAR,
            $1:created_at::TIMESTAMP_NTZ,
            $1:dispatched_at::TIMESTAMP_NTZ,
            $1:arrived_at_point_at::TIMESTAMP_NTZ,
            $1:notified_at::TIMESTAMP_NTZ,
            $1:collected_at::TIMESTAMP_NTZ,
            $1:rts_at::TIMESTAMP_NTZ,
            $1:parcel_status::VARCHAR,
            $1:parcel_value_zar::FLOAT,
            $1:parcel_weight_kg::FLOAT,
            $1:delivery_cost_zar::FLOAT,
            $1:service_type::VARCHAR,
            $1:province::VARCHAR,
            $1:year::NUMBER,
            $1:month::VARCHAR
        FROM @BULK_STAGE/{file})
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE)
        PURGE = TRUE""",

    "FACT_TRACKING_EVENTS": """
        COPY INTO FACT_TRACKING_EVENTS (
            TRACKING_EVENT_ID, PARCEL_ID, EVENT_TYPE, EVENT_TIMESTAMP,
            LATITUDE, LONGITUDE, STATUS, SOURCE_SYSTEM, LOAD_YEAR, LOAD_MONTH
        )
        FROM (SELECT
            $1:tracking_event_id::NUMBER,
            $1:parcel_id::NUMBER,
            $1:event_type::VARCHAR,
            $1:event_timestamp::TIMESTAMP_NTZ,
            $1:latitude::FLOAT,
            $1:longitude::FLOAT,
            $1:status::VARCHAR,
            $1:source_system::VARCHAR,
            $1:year::NUMBER,
            $1:month::VARCHAR
        FROM @BULK_STAGE/{file})
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE)
        PURGE = TRUE""",

    "FACT_RETURNS": """
        COPY INTO FACT_RETURNS (
            RETURN_ID, PARCEL_ID, RETAILER_ID, RETURN_INITIATED_AT,
            RETURN_REASON, RETURN_VALUE_ZAR, DROP_OFF_POINT_ID,
            LOAD_YEAR, LOAD_MONTH
        )
        FROM (SELECT
            $1:return_id::NUMBER,
            $1:parcel_id::NUMBER,
            $1:retailer_id::NUMBER,
            $1:return_initiated_at::TIMESTAMP_NTZ,
            $1:return_reason::VARCHAR,
            $1:return_value_zar::FLOAT,
            $1:drop_off_point_id::NUMBER,
            $1:year::NUMBER,
            $1:month::VARCHAR
        FROM @BULK_STAGE/{file})
        FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE)
        PURGE = TRUE""",
}

# Dim tables use MATCH_BY_COLUMN_NAME — no reserved words in dim schemas
DIM_COPY = """
    COPY INTO {table}
    FROM @BULK_STAGE/{file}
    FILE_FORMAT = (TYPE=PARQUET USE_VECTORIZED_SCANNER=TRUE SNAPPY_COMPRESSION=TRUE)
    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
    PURGE = TRUE"""


def bulk_load(cur, local_path: Path, table: str, copy_sql: str) -> tuple[int, float]:
    """PUT a parquet file to stage then COPY INTO table. Returns (rows, seconds)."""
    t0 = time.time()
    fname = local_path.name
    # PUT — quote path to handle spaces; parquet already snappy-compressed
    cur.execute(
        f"PUT 'file://{local_path.as_posix()}' @BULK_STAGE "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE PARALLEL=8"
    )
    # COPY INTO
    sql = copy_sql.replace('{file}', fname)
    cur.execute(sql)
    rows = sum(r[3] for r in cur.fetchall())   # rows_loaded column
    return rows, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='../data/raw')
    ap.add_argument('--recreate', action='store_true')
    a = ap.parse_args()
    data_dir = Path(a.data_dir).resolve()

    print('='*70)
    print('PARGO DW — BULK LOADER (PUT + COPY INTO)')
    print(f'  data dir : {data_dir}')
    print('='*70)

    sfcon = snowflake.connector.connect(**SF)
    cur = sfcon.cursor()
    print(f'\n[1] Connected: {cur.execute("SELECT CURRENT_USER(), CURRENT_ACCOUNT(), CURRENT_WAREHOUSE()").fetchone()}')

    print('\n[2] Setup…')
    for sql in SETUP_SQL:
        cur.execute(sql)

    print('\n[3] Tables…')
    if a.recreate:
        for t in reversed(list(TABLES)):
            cur.execute(f'DROP TABLE IF EXISTS {t}')
            print(f'  Dropped {t}')
    for t, ddl in TABLES.items():
        cur.execute(ddl.strip())
        print(f'  OK {t}')

    print('\n[4] Dimensions (PUT + COPY MATCH_BY_COLUMN_NAME)…')
    dim_files = {
        'DIM_COURIERS':      'couriers.parquet',
        'DIM_CUSTOMERS':     'customers.parquet',
        'DIM_PICKUP_POINTS': 'pickup_points.parquet',
        'DIM_RETAILERS':     'retailers.parquet',
    }
    for tbl, fname in dim_files.items():
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        if cur.fetchone()[0] > 0:
            print(f'  {tbl}: already loaded')
            continue
        path = data_dir / fname
        copy_sql = DIM_COPY.replace('{table}', tbl).replace('{file}', fname)
        rows, secs = bulk_load(cur, path, tbl, copy_sql)
        print(f'  {tbl}: {rows:,} rows in {secs:.1f}s  ({rows/secs:,.0f} rows/s)')

    print('\n[5] Facts (PUT + COPY INTO with column mapping)…')
    fact_map = {
        'FACT_ORDERS':          'orders',
        'FACT_PARCELS':         'parcels',
        'FACT_TRACKING_EVENTS': 'tracking_events',
        'FACT_RETURNS':         'returns',
    }
    # Collect all partitions
    all_periods = set()
    for entity in fact_map.values():
        for f in (data_dir / entity).glob('year=*/month=*/*.parquet'):
            y = int(next(p for p in f.parts if p.startswith('year=')).split('=')[1])
            m = int(next(p for p in f.parts if p.startswith('month=')).split('=')[1])
            all_periods.add((y, m))
    all_periods = sorted(all_periods)
    print(f'  {len(all_periods)} partitions to load')

    grand = {t: 0 for t in fact_map}
    t_total = time.time()

    for pi, (yr, mo) in enumerate(all_periods, 1):
        for tbl, entity in fact_map.items():
            pattern = data_dir / entity / f'year={yr}' / f'month={mo:02d}'
            files = list(pattern.glob('*.parquet'))
            if not files:
                continue
            # Idempotency check
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE LOAD_YEAR={yr} AND LOAD_MONTH='{yr}-{mo:02d}'")
            if cur.fetchone()[0] > 0:
                cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE LOAD_YEAR={yr} AND LOAD_MONTH='{yr}-{mo:02d}'")
                grand[tbl] += cur.fetchone()[0]
                continue
            for fpath in files:
                rows, secs = bulk_load(cur, fpath, tbl, FACT_COPY[tbl])
                grand[tbl] += rows

        elapsed = time.time() - t_total
        rate = sum(grand.values()) / elapsed if elapsed > 0 else 0
        print(
            f'  [{pi:>2}/{len(all_periods)}] {yr}-{mo:02d} | '
            f'orders={grand["FACT_ORDERS"]:>10,} '
            f'parcels={grand["FACT_PARCELS"]:>10,} '
            f'events={grand["FACT_TRACKING_EVENTS"]:>12,} '
            f'returns={grand["FACT_RETURNS"]:>8,} | '
            f'{rate:,.0f} rows/s',
            flush=True
        )

    print('\n[6] Final counts:')
    for tbl in list(dim_files) + list(fact_map):
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        print(f'  {tbl:30s} {cur.fetchone()[0]:>15,}')

    print('\n[7] Verification:')
    checks = [
        ("Parcels by year",      "SELECT LOAD_YEAR, COUNT(*) n FROM FACT_PARCELS GROUP BY 1 ORDER BY 1"),
        ("Status breakdown",     "SELECT PARCEL_STATUS, COUNT(*) n FROM FACT_PARCELS GROUP BY 1 ORDER BY 2 DESC"),
        ("Events by source",     "SELECT SOURCE_SYSTEM, COUNT(*) n FROM FACT_TRACKING_EVENTS GROUP BY 1 ORDER BY 2 DESC"),
        ("Return reasons",       "SELECT RETURN_REASON, COUNT(*) n FROM FACT_RETURNS GROUP BY 1 ORDER BY 2 DESC"),
        ("Top 5 retailers",      "SELECT r.RETAILER_NAME, COUNT(*) n FROM FACT_PARCELS p JOIN DIM_RETAILERS r ON p.RETAILER_ID=r.RETAILER_ID GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
        ("Orphan events",        "SELECT COUNT(*) FROM FACT_TRACKING_EVENTS e WHERE NOT EXISTS (SELECT 1 FROM FACT_PARCELS p WHERE p.PARCEL_ID=e.PARCEL_ID)"),
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
