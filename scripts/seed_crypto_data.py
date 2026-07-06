"""Create crypto_data table and load real crypto OHLCV data from CSV."""
import os
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("Set DATABASE_URL env var")

engine = create_engine(DATABASE_URL)

# CSV columns: ticker, asset_name, date, open, high, low, close, volume
df = pd.read_csv("dataset/crypto_data.csv")
df = df.rename(columns={"date": "timestamp"})
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS crypto_data (
            ticker TEXT NOT NULL,
            asset_name TEXT,
            "timestamp" TIMESTAMPTZ NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume BIGINT
        )
    """))
    conn.execute(text("DELETE FROM crypto_data"))
    conn.commit()

df.to_sql("crypto_data", engine, if_exists="append", index=False, method="multi", chunksize=5000)
print(f"Loaded {len(df)} rows into crypto_data ({df['ticker'].nunique()} tickers)")
