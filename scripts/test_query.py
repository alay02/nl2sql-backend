"""Minimal SQL connectivity check script."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is required. Please configure it in your environment.")

engine = create_engine(DATABASE_URL)

# sample test query
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT ticker, COUNT(*)
        FROM stock_data
        GROUP BY ticker;
    """))
    
    for row in result:
        print(row)
