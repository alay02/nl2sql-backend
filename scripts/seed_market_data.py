"""Seed stock_data table with realistic synthetic data for all supported tickers."""
import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("Set DATABASE_URL env var")

TICKERS = {
    "NVDA": 130.0,
    "AAPL": 230.0,
    "TSLA": 250.0,
    "MSFT": 430.0,
    "AMZN": 200.0,
    "GOOGL": 175.0,
    "META": 550.0,
    "SPY": 570.0,
    "QQQ": 500.0,
}

DAYS = 504
np.random.seed(42)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stock_data (
            ticker TEXT NOT NULL,
            "timestamp" TIMESTAMPTZ NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume BIGINT
        )
    """))
    conn.execute(text("DELETE FROM stock_data"))
    conn.commit()

dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=DAYS)

all_rows = []
for ticker, base_price in TICKERS.items():
    daily_returns = np.random.normal(0.0005, 0.02, DAYS)
    prices = [base_price]
    for r in daily_returns[1:]:
        prices.append(prices[-1] * (1 + r))

    for i, dt in enumerate(dates):
        close = round(prices[i], 2)
        intraday = np.random.uniform(0.005, 0.025)
        open_p = round(close * (1 + np.random.uniform(-intraday, intraday)), 2)
        high = round(max(open_p, close) * (1 + np.random.uniform(0.001, intraday)), 2)
        low = round(min(open_p, close) * (1 - np.random.uniform(0.001, intraday)), 2)
        vol = int(np.random.lognormal(17, 0.5))
        all_rows.append({
            "ticker": ticker,
            "timestamp": dt,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        })

df = pd.DataFrame(all_rows)
df.to_sql("stock_data", engine, if_exists="append", index=False, method="multi", chunksize=5000)
print(f"Loaded {len(df)} rows ({len(TICKERS)} tickers × {DAYS} days)")
