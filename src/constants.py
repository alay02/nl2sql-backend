"""Application constants and configurations"""

# ==================== Database Schema ====================
DB_SCHEMA = """
Table: market_data
Columns:
- ticker (TEXT)
- timestamp (TIMESTAMPTZ)
- open (DOUBLE)
- high (DOUBLE)
- low (DOUBLE)
- close (DOUBLE)
- volume (BIGINT)
"""

# ==================== Allowed Resources ====================
ALLOWED_TABLES = {"market_data"}
ALLOWED_COLUMNS = {"ticker", "timestamp", "open", "high", "low", "close", "volume"}

# ==================== Supported Data ====================
SUPPORTED_TICKERS = ["nvda", "aapl", "tsla", "msft", "amzn", "googl", "meta", "spy", "qqq"]

# ==================== Clarification Keywords ====================
AMBIGUOUS_KEYWORDS = [
    "recent",
    "performed better",
    "performed worse",
    "volatility",
    "trend",
    "performance",
    "better",
    "worse",
    "highest",
    "lowest",
    "top",
    "bottom",
    "most",
    "least",
]

TIME_INDICATORS = ["recent", "last", "past", "week", "month", "year", "day", "days"]

COMPARISON_INDICATORS = ["better", "worse", "than", "compared to", "vs", "versus"]

VOLATILITY_MEASURES = ["standard deviation", "variance", "range", "beta", "stdev", "vix"]

PERFORMANCE_METRICS = ["return", "price change", "volume", "market cap", "performance of"]

# ==================== SQL Rules ====================
DEFAULT_LIMIT = 200
SQL_KEYWORDS_BANNED = [
    "drop ",
    "delete ",
    "update ",
    "insert ",
    "alter ",
    "create ",
    "truncate ",
    "grant ",
    "revoke ",
]

# ==================== Data Processing ====================
FLOAT_TOLERANCE = 1e-6

# ==================== LLM Prompts ====================
SQL_GENERATION_PROMPT_TEMPLATE = """
You are a PostgreSQL expert. Generate SQL following Chain-of-Thought methodology.

STEP 1: ANALYZE THE QUESTION
- Identify the metrics requested (price, volume, volatility, etc.)
- Identify the tickers involved
- Identify the time period
- Identify any aggregations or comparisons needed

STEP 2: DETERMINE THE QUERY TYPE
- Is this a single ticker query or multi-ticker comparison?
- Should results be aggregated (SUM, AVG, MAX, MIN)?
- Do we need to group by ticker or time?

STEP 3: CONSTRUCT THE SQL
Apply these rules STRICTLY:
- Do NOT include markdown code fences: no ``` symbols
- Do NOT include explanations or comments
- Use double quotes around column names like "timestamp"
- Only query from table market_data
- Always add LIMIT {limit} for non-aggregation queries
- For multi-ticker comparison, use GROUP BY ticker when appropriate
- For time-based queries, anchor to latest available data:
  * Use MAX("timestamp") to find the most recent data point
  * When filtering by ticker, compute MAX("timestamp") within that ticker scope
  * For multi-ticker queries, use MAX("timestamp") over the selected tickers

TIME WINDOW RULES:
- Never use NOW() - always use MAX("timestamp") for historical data
- If user mentions "recent", "last N days", or "past N days":
  * Calculate the date range from the latest available timestamp
  * Example: If latest date is 2025-01-20, "last 5 days" = 2025-01-15 to 2025-01-20

FINANCIAL CALCULATION RULES:
- Daily return = (close - previous_close) / previous_close. Use LAG(close) OVER (PARTITION BY ticker ORDER BY "timestamp") to get previous_close.
- Average return = AVG of daily returns over a period, NOT (last_close - first_close) / first_close.
- Cumulative return = (last_close - first_close) / first_close. Use FIRST_VALUE and LAST_VALUE or a subquery.
- Volatility = STDDEV(daily_return) over a period. Always compute daily returns first, then take STDDEV.
- Intraday range = high - low for a single day.
- Average True Range (ATR) approximation = AVG(high - low) over N days.
- VWAP = SUM(close * volume) / SUM(volume).
- Price change = close - open for intraday, or close - LAG(close) for day-over-day.
- Percentage change = 100.0 * (close - LAG(close)) / LAG(close).
- Drawdown = (close - MAX(close) OVER preceding rows) / MAX(close) OVER preceding rows.
- When asked about "return" without qualification, default to daily return using LAG.

REFERENCE EXAMPLES (50 patterns covering common question types):

--- BASIC RETRIEVAL ---
Example 1:
  Q: "Show the latest 10 rows for NVDA."
  SQL: SELECT * FROM market_data WHERE ticker = 'NVDA' ORDER BY "timestamp" DESC LIMIT 10;

Example 2:
  Q: "What was AAPL's most recent closing price?"
  SQL: SELECT close FROM market_data WHERE ticker = 'AAPL' ORDER BY "timestamp" DESC LIMIT 1;

Example 3:
  Q: "When was the last data point recorded for TSLA?"
  SQL: SELECT MAX("timestamp") AS latest_timestamp FROM market_data WHERE ticker = 'TSLA';

Example 4:
  Q: "Show all tickers in the database."
  SQL: SELECT DISTINCT ticker FROM market_data ORDER BY ticker;

Example 5:
  Q: "How many data points do we have for MSFT?"
  SQL: SELECT COUNT(*) AS row_count FROM market_data WHERE ticker = 'MSFT';

--- SIMPLE AGGREGATION ---
Example 6:
  Q: "What is the average closing price of NVDA?"
  SQL: SELECT AVG(close) AS avg_close FROM market_data WHERE ticker = 'NVDA';

Example 7:
  Q: "What is the total trading volume of AAPL?"
  SQL: SELECT SUM(volume) AS total_volume FROM market_data WHERE ticker = 'AAPL';

Example 8:
  Q: "What is the highest price GOOGL ever reached?"
  SQL: SELECT MAX(high) AS max_high FROM market_data WHERE ticker = 'GOOGL';

Example 9:
  Q: "What is the lowest price AMZN has traded at?"
  SQL: SELECT MIN(low) AS min_low FROM market_data WHERE ticker = 'AMZN';

Example 10:
  Q: "What is NVDA's average daily trading volume?"
  SQL: SELECT AVG(volume) AS avg_daily_volume FROM market_data WHERE ticker = 'NVDA';

--- TIME-WINDOWED QUERIES ---
Example 11:
  Q: "What is the average close of NVDA over the last 7 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT AVG(close) AS avg_close FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days';

Example 12:
  Q: "Show TSLA's daily prices for the last 2 weeks."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'TSLA') SELECT "timestamp", open, high, low, close, volume FROM market_data WHERE ticker = 'TSLA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days' ORDER BY "timestamp" ASC LIMIT 200;

Example 13:
  Q: "What was AAPL's total volume over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'AAPL') SELECT SUM(volume) AS total_volume FROM market_data WHERE ticker = 'AAPL' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 14:
  Q: "Show GOOGL data between 2025-09-01 and 2025-09-15."
  SQL: SELECT * FROM market_data WHERE ticker = 'GOOGL' AND "timestamp" >= '2025-09-01' AND "timestamp" < '2025-09-16' ORDER BY "timestamp" ASC LIMIT 200;

Example 15:
  Q: "What was NVDA's highest close in the last 90 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT MAX(close) AS max_close FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '90 days';

--- DAILY RETURNS ---
Example 16:
  Q: "What is the average daily return of NVDA over the last week?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'NVDA') SELECT AVG((close - prev_close) / prev_close) AS avg_daily_return FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days';

Example 17:
  Q: "Show AAPL's daily returns for the last 10 trading days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'AAPL'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'AAPL') SELECT "timestamp", ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS daily_return_pct FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '10 days' ORDER BY "timestamp" DESC LIMIT 10;

Example 18:
  Q: "What was TSLA's best single-day return in the last month?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'TSLA'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'TSLA') SELECT "timestamp", ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS daily_return_pct FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY daily_return_pct DESC LIMIT 1;

Example 19:
  Q: "What was NVDA's worst single-day return in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'NVDA') SELECT "timestamp", ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS daily_return_pct FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY daily_return_pct ASC LIMIT 1;

Example 20:
  Q: "How many days did MSFT have a positive return in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'MSFT'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'MSFT') SELECT COUNT(*) AS positive_days FROM daily WHERE prev_close IS NOT NULL AND close > prev_close AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

--- CUMULATIVE RETURN ---
Example 21:
  Q: "What is NVDA's cumulative return over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA'), period AS (SELECT * FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), first_close AS (SELECT close FROM period ORDER BY "timestamp" ASC LIMIT 1), last_close AS (SELECT close FROM period ORDER BY "timestamp" DESC LIMIT 1) SELECT ROUND(((lc.close - fc.close) / fc.close * 100)::numeric, 4) AS cumulative_return_pct FROM first_close fc, last_close lc;

Example 22:
  Q: "Compare the cumulative return of AAPL and GOOGL over the last 60 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker IN ('AAPL', 'GOOGL')), period AS (SELECT * FROM market_data WHERE ticker IN ('AAPL', 'GOOGL') AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days'), firsts AS (SELECT DISTINCT ON (ticker) ticker, close AS first_close FROM period ORDER BY ticker, "timestamp" ASC), lasts AS (SELECT DISTINCT ON (ticker) ticker, close AS last_close FROM period ORDER BY ticker, "timestamp" DESC) SELECT f.ticker, ROUND(((l.last_close - f.first_close) / f.first_close * 100)::numeric, 4) AS cumulative_return_pct FROM firsts f JOIN lasts l ON f.ticker = l.ticker ORDER BY cumulative_return_pct DESC;

--- VOLATILITY ---
Example 23:
  Q: "What is NVDA's volatility over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'NVDA') SELECT ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS daily_return_volatility FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 24:
  Q: "Which stock is the most volatile over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data), daily AS (SELECT ticker, "timestamp", close, LAG(close) OVER (PARTITION BY ticker ORDER BY "timestamp") AS prev_close FROM market_data) SELECT ticker, ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS volatility FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY ticker ORDER BY volatility DESC LIMIT 1;

Example 25:
  Q: "Compare the volatility of NVDA, AAPL, and TSLA over the last 60 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker IN ('NVDA', 'AAPL', 'TSLA')), daily AS (SELECT ticker, "timestamp", close, LAG(close) OVER (PARTITION BY ticker ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker IN ('NVDA', 'AAPL', 'TSLA')) SELECT ticker, ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS volatility FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days' GROUP BY ticker ORDER BY volatility DESC;

--- INTRADAY RANGE AND ATR ---
Example 26:
  Q: "What is NVDA's average intraday range over the last 14 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT ROUND(AVG(high - low)::numeric, 4) AS avg_intraday_range FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days';

Example 27:
  Q: "What is the average true range (ATR) approximation for TSLA over 14 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'TSLA') SELECT ROUND(AVG(high - low)::numeric, 4) AS atr_approx FROM market_data WHERE ticker = 'TSLA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days';

Example 28:
  Q: "Which day had the largest intraday range for AMZN in the last month?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'AMZN') SELECT "timestamp", high, low, ROUND((high - low)::numeric, 4) AS intraday_range FROM market_data WHERE ticker = 'AMZN' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY intraday_range DESC LIMIT 1;

--- VWAP ---
Example 29:
  Q: "What is NVDA's VWAP over the last 5 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT ROUND((SUM(close * volume) / SUM(volume))::numeric, 4) AS vwap FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '5 days';

Example 30:
  Q: "Compare VWAP of AAPL and MSFT over the last 10 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker IN ('AAPL', 'MSFT')) SELECT ticker, ROUND((SUM(close * volume) / SUM(volume))::numeric, 4) AS vwap FROM market_data WHERE ticker IN ('AAPL', 'MSFT') AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '10 days' GROUP BY ticker ORDER BY ticker;

--- PRICE CHANGE AND PERCENTAGE CHANGE ---
Example 31:
  Q: "How much did NVDA's price change yesterday?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA'), latest AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'NVDA' ORDER BY "timestamp" DESC LIMIT 2) SELECT "timestamp", ROUND((close - prev_close)::numeric, 4) AS price_change, ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS change_pct FROM latest WHERE prev_close IS NOT NULL;

Example 32:
  Q: "Show TSLA's day-over-day price changes for the last week."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'TSLA'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'TSLA') SELECT "timestamp", ROUND((close - prev_close)::numeric, 4) AS price_change, ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS change_pct FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' ORDER BY "timestamp" DESC LIMIT 200;

Example 33:
  Q: "What was the intraday change (open to close) for META today?"
  SQL: SELECT "timestamp", open, close, ROUND((close - open)::numeric, 4) AS intraday_change, ROUND(((close - open) / open * 100)::numeric, 4) AS intraday_change_pct FROM market_data WHERE ticker = 'META' ORDER BY "timestamp" DESC LIMIT 1;

--- MULTI-TICKER COMPARISON ---
Example 34:
  Q: "Compare the average close of NVDA and AAPL over the last 7 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker IN ('NVDA', 'AAPL')) SELECT ticker, AVG(close) AS avg_close FROM market_data WHERE ticker IN ('NVDA', 'AAPL') AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' GROUP BY ticker ORDER BY ticker;

Example 35:
  Q: "Which ticker had the highest average volume in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data) SELECT ticker, AVG(volume) AS avg_volume FROM market_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY ticker ORDER BY avg_volume DESC LIMIT 1;

Example 36:
  Q: "Rank all tickers by their average close price in the last 14 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data) SELECT ticker, ROUND(AVG(close)::numeric, 4) AS avg_close FROM market_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days' GROUP BY ticker ORDER BY avg_close DESC;

Example 37:
  Q: "Which stock outperformed SPY in the last month by cumulative return?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data), period AS (SELECT * FROM market_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), firsts AS (SELECT DISTINCT ON (ticker) ticker, close AS first_close FROM period ORDER BY ticker, "timestamp" ASC), lasts AS (SELECT DISTINCT ON (ticker) ticker, close AS last_close FROM period ORDER BY ticker, "timestamp" DESC), returns AS (SELECT f.ticker, ROUND(((l.last_close - f.first_close) / f.first_close * 100)::numeric, 4) AS cum_return FROM firsts f JOIN lasts l ON f.ticker = l.ticker) SELECT r.ticker, r.cum_return FROM returns r WHERE r.cum_return > (SELECT cum_return FROM returns WHERE ticker = 'SPY') AND r.ticker != 'SPY' ORDER BY r.cum_return DESC;

--- DRAWDOWN ---
Example 38:
  Q: "What is NVDA's maximum drawdown in the last 60 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA'), period AS (SELECT "timestamp", close, MAX(close) OVER (ORDER BY "timestamp" ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_max FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days') SELECT ROUND((MIN((close - running_max) / running_max) * 100)::numeric, 4) AS max_drawdown_pct FROM period;

Example 39:
  Q: "When did AAPL hit its maximum drawdown in the last 90 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'AAPL'), period AS (SELECT "timestamp", close, MAX(close) OVER (ORDER BY "timestamp" ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_max FROM market_data WHERE ticker = 'AAPL' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '90 days') SELECT "timestamp", ROUND(((close - running_max) / running_max * 100)::numeric, 4) AS drawdown_pct FROM period ORDER BY drawdown_pct ASC LIMIT 1;

--- MOVING AVERAGES ---
Example 40:
  Q: "Show NVDA's 7-day moving average of close price for the last month."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT "timestamp", close, ROUND(AVG(close) OVER (ORDER BY "timestamp" ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)::numeric, 4) AS ma_7 FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY "timestamp" ASC LIMIT 200;

Example 41:
  Q: "Is TSLA's current price above or below its 20-day moving average?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'TSLA'), ma AS (SELECT "timestamp", close, AVG(close) OVER (ORDER BY "timestamp" ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma_20 FROM market_data WHERE ticker = 'TSLA') SELECT "timestamp", close, ROUND(ma_20::numeric, 4) AS ma_20, CASE WHEN close > ma_20 THEN 'ABOVE' ELSE 'BELOW' END AS position FROM ma WHERE "timestamp" = (SELECT max_ts FROM anchor);

Example 42:
  Q: "Show the 50-day and 200-day moving averages for AAPL."
  SQL: SELECT "timestamp", close, ROUND(AVG(close) OVER (ORDER BY "timestamp" ROWS BETWEEN 49 PRECEDING AND CURRENT ROW)::numeric, 4) AS ma_50, ROUND(AVG(close) OVER (ORDER BY "timestamp" ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)::numeric, 4) AS ma_200 FROM market_data WHERE ticker = 'AAPL' ORDER BY "timestamp" DESC LIMIT 1;

--- VOLUME ANALYSIS ---
Example 43:
  Q: "What was NVDA's highest volume day in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT "timestamp", volume, close FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY volume DESC LIMIT 1;

Example 44:
  Q: "How does AAPL's recent volume compare to its 30-day average?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'AAPL'), avg_vol AS (SELECT AVG(volume) AS avg_30d_volume FROM market_data WHERE ticker = 'AAPL' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), latest AS (SELECT volume AS latest_volume FROM market_data WHERE ticker = 'AAPL' ORDER BY "timestamp" DESC LIMIT 1) SELECT l.latest_volume, ROUND(a.avg_30d_volume::numeric, 0) AS avg_30d_volume, ROUND((l.latest_volume / a.avg_30d_volume * 100)::numeric, 2) AS volume_vs_avg_pct FROM latest l, avg_vol a;

Example 45:
  Q: "Which ticker had the most unusual volume spike in the last week?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data), avg_vol AS (SELECT ticker, AVG(volume) AS avg_volume FROM market_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY ticker), recent AS (SELECT ticker, MAX(volume) AS max_recent_volume FROM market_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' GROUP BY ticker) SELECT r.ticker, r.max_recent_volume, ROUND(a.avg_volume::numeric, 0) AS avg_30d_volume, ROUND((r.max_recent_volume / a.avg_volume)::numeric, 2) AS volume_ratio FROM recent r JOIN avg_vol a ON r.ticker = a.ticker ORDER BY volume_ratio DESC LIMIT 1;

--- GAP ANALYSIS ---
Example 46:
  Q: "Did NVDA gap up or down today?"
  SQL: WITH recent AS (SELECT "timestamp", open, close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'NVDA' ORDER BY "timestamp" DESC LIMIT 2) SELECT "timestamp", prev_close, open, ROUND((open - prev_close)::numeric, 4) AS gap, CASE WHEN open > prev_close THEN 'GAP UP' WHEN open < prev_close THEN 'GAP DOWN' ELSE 'NO GAP' END AS gap_direction FROM recent WHERE prev_close IS NOT NULL;

Example 47:
  Q: "Show the largest gap ups for TSLA in the last month."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'TSLA'), gaps AS (SELECT "timestamp", open, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM market_data WHERE ticker = 'TSLA') SELECT "timestamp", ROUND((open - prev_close)::numeric, 4) AS gap, ROUND(((open - prev_close) / prev_close * 100)::numeric, 4) AS gap_pct FROM gaps WHERE prev_close IS NOT NULL AND open > prev_close AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY gap_pct DESC LIMIT 5;

--- EXTREMES AND STREAKS ---
Example 48:
  Q: "On how many of the last 30 days did NVDA close higher than it opened?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'NVDA') SELECT COUNT(*) AS green_days FROM market_data WHERE ticker = 'NVDA' AND close > open AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 49:
  Q: "What is the 52-week high and low for AAPL?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker = 'AAPL') SELECT MAX(high) AS week_52_high, MIN(low) AS week_52_low FROM market_data WHERE ticker = 'AAPL' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '365 days';

Example 50:
  Q: "Show the top 5 highest-volume days across all tickers in the last month."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data) SELECT ticker, "timestamp", volume FROM market_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY volume DESC LIMIT 5;

--- CORRELATION AND SPREAD ---
Example 51:
  Q: "What is the average price spread between NVDA and AAPL over the last 14 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker IN ('NVDA', 'AAPL')), nvda AS (SELECT "timestamp"::date AS dt, close FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days'), aapl AS (SELECT "timestamp"::date AS dt, close FROM market_data WHERE ticker = 'AAPL' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days') SELECT ROUND(AVG(n.close - a.close)::numeric, 4) AS avg_spread FROM nvda n JOIN aapl a ON n.dt = a.dt;

Example 52:
  Q: "Show the daily close ratio of NVDA to AAPL over the last 2 weeks."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM market_data WHERE ticker IN ('NVDA', 'AAPL')), nvda AS (SELECT "timestamp"::date AS dt, close AS nvda_close FROM market_data WHERE ticker = 'NVDA' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days'), aapl AS (SELECT "timestamp"::date AS dt, close AS aapl_close FROM market_data WHERE ticker = 'AAPL' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days') SELECT n.dt, n.nvda_close, a.aapl_close, ROUND((n.nvda_close / a.aapl_close)::numeric, 4) AS ratio FROM nvda n JOIN aapl a ON n.dt = a.dt ORDER BY n.dt ASC LIMIT 200;

Example 53:
  Q: "How many trading days of data are available for each ticker?"
  SQL: SELECT ticker, COUNT(*) AS trading_days, MIN("timestamp") AS first_date, MAX("timestamp") AS last_date FROM market_data GROUP BY ticker ORDER BY ticker;

BAD EXAMPLES (patterns to AVOID):
- NEVER use NOW() — always use MAX("timestamp") for time anchoring.
- NEVER compute return as AVG(close) — return requires LAG to get previous close.
- NEVER compare tickers without GROUP BY or separate subqueries.
- NEVER omit LIMIT on non-aggregation SELECT queries.
- NEVER use columns not in the schema (there is no "return", "change", or "pct_change" column).

Schema:
{schema}

User question:
{question}

Remember: Output ONLY the SQL statement, nothing else."""

ANSWER_SUMMARY_PROMPT_TEMPLATE = """
You are a financial data assistant. Your task is to generate clear, concise answers based on data.

ANALYSIS FRAMEWORK:
1. Extract key numbers from the data (prices, volumes, changes)
2. Identify trends or patterns
3. Compare across tickers if multi-ticker data
4. Provide actionable insights

FORMATTING RULES:
- Be concise but informative (2-3 sentences for simple queries, up to 5 for complex)
- Use precise numbers with context (e.g., "NVDA closed at $145.32, up 2.5%")
- For comparisons, clearly state the direction (higher/lower/better/worse)
- For time-series data, describe the trend
- For aggregations, highlight the most relevant statistics

OUTPUT STRUCTURE:
1. Direct answer to the question
2. Key supporting numbers from the data
3. Any important qualifications or data limitations

User Question:
{question}

SQL Query:
{sql}

Data Columns: {columns}
Data Rows:
{rows}

Generate a direct, fact-based answer:
"""
