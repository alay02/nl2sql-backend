"""Create and seed etf_data and options_data tables with realistic synthetic data."""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("Set DATABASE_URL env var")

engine = create_engine(DATABASE_URL)

# ── ETF schema ──────────────────────────────────────────────────────────────
# OHLCV plus fund-specific fields: nav, expense_ratio, aum
ETFS = {
    "VOO":  {"base": 520.0, "nav_offset": -0.5, "expense_ratio": 0.03, "aum_b": 450},
    "QQQ":  {"base": 500.0, "nav_offset": -0.3, "expense_ratio": 0.20, "aum_b": 250},
    "IWM":  {"base": 210.0, "nav_offset": -0.4, "expense_ratio": 0.19, "aum_b": 65},
    "XLF":  {"base": 44.0,  "nav_offset": -0.1, "expense_ratio": 0.09, "aum_b": 40},
    "XLK":  {"base": 220.0, "nav_offset": -0.3, "expense_ratio": 0.09, "aum_b": 60},
    "GLD":  {"base": 240.0, "nav_offset": -0.2, "expense_ratio": 0.40, "aum_b": 55},
    "TLT":  {"base": 92.0,  "nav_offset": -0.1, "expense_ratio": 0.15, "aum_b": 50},
    "VTI":  {"base": 275.0, "nav_offset": -0.3, "expense_ratio": 0.03, "aum_b": 400},
    "ARKK": {"base": 55.0,  "nav_offset": -0.8, "expense_ratio": 0.75, "aum_b": 6},
}

# ── Options schema ──────────────────────────────────────────────────────────
# Underlying equities for which we generate options chains
OPTION_UNDERLYINGS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN"]
UNDERLYING_PRICES = {"NVDA": 130.0, "AAPL": 230.0, "TSLA": 250.0, "MSFT": 430.0, "AMZN": 200.0}

DAYS = 90
np.random.seed(42)
dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=DAYS)

# ─────────────────────────────────────────────────────────────────────────────
# Create tables
# ─────────────────────────────────────────────────────────────────────────────
with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS etf_data (
            ticker TEXT NOT NULL,
            "timestamp" TIMESTAMPTZ NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume BIGINT,
            nav DOUBLE PRECISION,
            expense_ratio DOUBLE PRECISION,
            aum DOUBLE PRECISION
        )
    """))
    conn.execute(text("DELETE FROM etf_data"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS options_data (
            underlying_ticker TEXT NOT NULL,
            "timestamp" TIMESTAMPTZ NOT NULL,
            expiration DATE NOT NULL,
            strike DOUBLE PRECISION NOT NULL,
            option_type TEXT NOT NULL,
            bid DOUBLE PRECISION,
            ask DOUBLE PRECISION,
            last_price DOUBLE PRECISION,
            volume BIGINT,
            open_interest BIGINT,
            implied_volatility DOUBLE PRECISION,
            delta DOUBLE PRECISION
        )
    """))
    conn.execute(text("DELETE FROM options_data"))
    conn.commit()

# ─────────────────────────────────────────────────────────────────────────────
# Seed ETF data
# ─────────────────────────────────────────────────────────────────────────────
print("Seeding ETF data...")
etf_rows = []
for ticker, info in ETFS.items():
    daily_returns = np.random.normal(0.0003, 0.015, DAYS)
    prices = [info["base"]]
    for r in daily_returns[1:]:
        prices.append(prices[-1] * (1 + r))

    for i, dt in enumerate(dates):
        close = round(prices[i], 2)
        intraday = np.random.uniform(0.003, 0.018)
        open_p = round(close * (1 + np.random.uniform(-intraday, intraday)), 2)
        high = round(max(open_p, close) * (1 + np.random.uniform(0.001, intraday)), 2)
        low = round(min(open_p, close) * (1 - np.random.uniform(0.001, intraday)), 2)
        vol = int(np.random.lognormal(16.5, 0.6))
        nav = round(close + info["nav_offset"] + np.random.uniform(-0.3, 0.3), 2)
        aum = round(info["aum_b"] * 1e9 * (1 + np.random.uniform(-0.02, 0.02)), 0)

        etf_rows.append({
            "ticker": ticker,
            "timestamp": dt,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
            "nav": nav,
            "expense_ratio": info["expense_ratio"],
            "aum": aum,
        })

df_etf = pd.DataFrame(etf_rows)
df_etf.to_sql("etf_data", engine, if_exists="append", index=False, method="multi", chunksize=5000)
print(f"  ETF: {len(df_etf)} rows ({len(ETFS)} tickers × {DAYS} days)")

# ─────────────────────────────────────────────────────────────────────────────
# Seed Options data
# ─────────────────────────────────────────────────────────────────────────────
print("Seeding Options data...")
option_rows = []

# Generate weekly expiration dates (next 8 Fridays from the last date)
last_date = dates[-1]
expirations = pd.date_range(last_date + pd.Timedelta(days=1), periods=8, freq="W-FRI")

for underlying in OPTION_UNDERLYINGS:
    base_price = UNDERLYING_PRICES[underlying]
    daily_returns = np.random.normal(0.0005, 0.02, DAYS)
    prices = [base_price]
    for r in daily_returns[1:]:
        prices.append(prices[-1] * (1 + r))

    for i, dt in enumerate(dates):
        spot = prices[i]
        # Generate options chain: 5 strikes around the spot for each expiration
        for exp_date in expirations:
            dte = (exp_date - dt).days
            if dte <= 0:
                continue

            strike_offsets = [-0.10, -0.05, 0.0, 0.05, 0.10]
            for offset in strike_offsets:
                strike = round(spot * (1 + offset), 0)
                for opt_type in ["call", "put"]:
                    base_iv = 0.30 + abs(offset) * 0.5 + np.random.uniform(-0.03, 0.03)
                    moneyness = (spot - strike) / spot if opt_type == "call" else (strike - spot) / spot
                    time_factor = (dte / 365) ** 0.5

                    # Simplified pricing
                    intrinsic = max(0, spot - strike) if opt_type == "call" else max(0, strike - spot)
                    time_value = spot * base_iv * time_factor * 0.4
                    mid_price = round(intrinsic + time_value, 2)
                    mid_price = max(mid_price, 0.01)

                    spread = round(mid_price * np.random.uniform(0.02, 0.08), 2)
                    spread = max(spread, 0.01)
                    bid = round(mid_price - spread / 2, 2)
                    ask = round(mid_price + spread / 2, 2)
                    bid = max(bid, 0.01)

                    # Delta approximation
                    if opt_type == "call":
                        delta = round(0.5 + moneyness * 2.5, 4)
                        delta = max(0.01, min(0.99, delta))
                    else:
                        delta = round(-0.5 + moneyness * 2.5, 4)
                        delta = max(-0.99, min(-0.01, delta))

                    opt_vol = int(np.random.lognormal(5, 1.5))
                    oi = int(np.random.lognormal(7, 1.2))

                    option_rows.append({
                        "underlying_ticker": underlying,
                        "timestamp": dt,
                        "expiration": exp_date.date(),
                        "strike": strike,
                        "option_type": opt_type,
                        "bid": bid,
                        "ask": ask,
                        "last_price": mid_price,
                        "volume": opt_vol,
                        "open_interest": oi,
                        "implied_volatility": round(base_iv, 4),
                        "delta": delta,
                    })

# Subsample options to keep DB reasonable (~50k rows instead of 500k+)
# Keep every 5th trading day's full chain
df_opts = pd.DataFrame(option_rows)
sampled_dates = dates[::5]
df_opts = df_opts[df_opts["timestamp"].isin(sampled_dates)]
df_opts.to_sql("options_data", engine, if_exists="append", index=False, method="multi", chunksize=5000)
print(f"  Options: {len(df_opts)} rows ({len(OPTION_UNDERLYINGS)} underlyings, {len(sampled_dates)} dates)")

print("\nDone.")
