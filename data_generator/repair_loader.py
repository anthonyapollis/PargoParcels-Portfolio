import os
"""
Repair loader: runs COPY INTO for FACT_TRACKING_EVENTS + FACT_RETURNS
using ON_ERROR=SKIP_FILE to tolerate the one corrupt parquet file.
Files are already in the stage from the previous PUT run.
"""
import time
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

def main():
    con = snowflake.connector.connect(**SF)
    cur = con.cursor()
    print(f'Connected: {cur.execute("SELECT CURRENT_USER(),CURRENT_ACCOUNT()").fetchone()}')

    # Check what is already loaded
    for t in ['FACT_TRACKING_EVENTS','FACT_RETURNS']:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'  {t}: {cur.fetchone()[0]:,} rows currently')

    # --- FACT_TRACKING_EVENTS ---
    cur.execute('SELECT COUNT(*) FROM FACT_TRACKING_EVENTS')
    if cur.fetchone()[0] == 0:
        print('\nCOPY INTO FACT_TRACKING_EVENTS (ON_ERROR=SKIP_FILE)...')
        t0 = time.time()
        cur.execute("""
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
            ON_ERROR = SKIP_FILE
            PURGE = TRUE
        """)
        rows = sum(r[3] for r in cur.fetchall())
        print(f'  Loaded {rows:,} rows in {time.time()-t0:.1f}s')
    else:
        print('\nFACT_TRACKING_EVENTS already has rows, skipping COPY INTO')

    # --- FACT_RETURNS: PUT + COPY ---
    cur.execute('SELECT COUNT(*) FROM FACT_RETURNS')
    if cur.fetchone()[0] == 0:
        from pathlib import Path
        data_dir = Path('../data/raw').resolve()
        returns_files = sorted((data_dir / 'returns').glob('year=*/month=*/*.parquet'))
        print(f'\nPUT {len(returns_files)} returns files...')
        t0 = time.time()
        for i, f in enumerate(returns_files, 1):
            cur.execute(
                f"PUT 'file://{f.as_posix()}' @BULK_STAGE "
                f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE PARALLEL=8"
            )
            if i % 10 == 0:
                print(f'  PUT {i}/{len(returns_files)}...')
        print(f'  PUT done in {time.time()-t0:.1f}s')

        print('COPY INTO FACT_RETURNS...')
        t0 = time.time()
        cur.execute("""
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
            ON_ERROR = SKIP_FILE
            PURGE = TRUE
        """)
        rows = sum(r[3] for r in cur.fetchall())
        print(f'  FACT_RETURNS: {rows:,} rows in {time.time()-t0:.1f}s')
    else:
        print('\nFACT_RETURNS already has rows, skipping')

    print('\n=== Final row counts ===')
    for t in ['DIM_COURIERS','DIM_CUSTOMERS','DIM_PICKUP_POINTS','DIM_RETAILERS',
              'FACT_ORDERS','FACT_PARCELS','FACT_TRACKING_EVENTS','FACT_RETURNS']:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'  {t:30s} {cur.fetchone()[0]:>15,}')

    print('\n=== Verification queries ===')
    for label, sql in [
        ('Parcels by year',   'SELECT LOAD_YEAR, COUNT(*) FROM FACT_PARCELS GROUP BY 1 ORDER BY 1'),
        ('Status mix',        'SELECT PARCEL_STATUS, COUNT(*) FROM FACT_PARCELS GROUP BY 1 ORDER BY 2 DESC LIMIT 5'),
        ('Events by source',  'SELECT SOURCE_SYSTEM, COUNT(*) FROM FACT_TRACKING_EVENTS GROUP BY 1 ORDER BY 2 DESC'),
        ('Top 5 retailers',   'SELECT r.RETAILER_NAME, COUNT(*) n FROM FACT_PARCELS p JOIN DIM_RETAILERS r ON p.RETAILER_ID=r.RETAILER_ID GROUP BY 1 ORDER BY 2 DESC LIMIT 5'),
        ('Return reasons',    'SELECT RETURN_REASON, COUNT(*) FROM FACT_RETURNS GROUP BY 1 ORDER BY 2 DESC LIMIT 5'),
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
