"""Load the raw file into Postgres as raw.online_retail, unchanged apart from column names.

Usage: python scripts/load_raw.py data/raw/online_retail_II.xlsx
Env:   DATABASE_URL (default points at the docker-compose Postgres)
"""
import os
import sys
from sqlalchemy import create_engine, text
from _common import read_file

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://retainx:retainx@localhost:5432/retainx")


def main(path: str) -> None:
    df = read_file(path)
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(text("create schema if not exists raw"))
        conn.execute(text("create schema if not exists analytics"))
        conn.execute(text("drop table if exists raw.online_retail cascade"))
    df.to_sql("online_retail", engine, schema="raw", index=False, chunksize=50_000, method="multi")
    with engine.connect() as conn:
        n = conn.execute(text("select count(*) from raw.online_retail")).scalar()
    print(f"Loaded {n:,} rows into raw.online_retail (file had {len(df):,}).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
