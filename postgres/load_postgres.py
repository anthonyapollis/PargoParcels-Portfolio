"""
Bulk-load the generated parquet into PostgreSQL via COPY (fastest path).
Streams month partitions one at a time so memory stays flat at full scale.

Usage:
    python load_postgres.py --dsn "postgresql://user:pass@localhost:5432/pargo_oltp" \
                            --data ../data/raw
"""
import argparse, glob, io, os
import pandas as pd
import psycopg2

DIMS = ["retailers", "pickup_points", "couriers", "customers"]
FACTS = ["orders", "parcels", "tracking_events", "returns"]

def copy_df(cur, df, table):
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cur.copy_expert(
        f"COPY pargo.{table} ({','.join(df.columns)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--data", default="../data/raw")
    args = ap.parse_args()
    conn = psycopg2.connect(args.dsn); conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET search_path TO pargo;")

    for t in DIMS:
        f = os.path.join(args.data, f"{t}.parquet")
        df = pd.read_parquet(f)
        copy_df(cur, df, t); conn.commit()
        print(f"{t}: {len(df):,} rows")

    for t in FACTS:
        total = 0
        for f in sorted(glob.glob(os.path.join(args.data, t, "year=*", "month=*", "*.parquet"))):
            df = pd.read_parquet(f)
            # OLTP holds clean data: drop the dirt injected for the warehouse story
            if t == "parcels":
                df = df.drop_duplicates(subset="parcel_id")
            copy_df(cur, df, t); conn.commit()
            total += len(df)
        print(f"{t}: {total:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__":
    main()
