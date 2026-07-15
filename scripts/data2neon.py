import os
import glob
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DATA_DIR = os.path.expanduser("~/Downloads/data")  # Change to your data folder path

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is required. Please configure it in your environment.")

engine = create_engine(DATABASE_URL)

files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
assert files, f"No csv files found in {DATA_DIR}"

all_df = []
for fp in files:
    ticker = os.path.splitext(os.path.basename(fp))[0].upper()  # e.g., AMZN.csv -> AMZN

    df = pd.read_csv(fp, header=None, names=["timestamp","open","high","low","close","volume"])

    df = df.rename(columns={df.columns[0]: "ts_excel"})  # First column contains timestamp numeric value
    df["ticker"] = ticker
    df = df[["ticker", "ts_excel", "open", "high", "low", "close", "volume"]]
    all_df.append(df)

big = pd.concat(all_df, ignore_index=True)

# Load into staging_stock_data (overwrite/append as needed)
big.to_sql("staging_stock_data", engine, if_exists="append", index=False, method="multi", chunksize=5000)

print("Loaded rows:", len(big))
