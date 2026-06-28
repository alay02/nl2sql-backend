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

GOOD EXAMPLES (patterns to follow):
Example 1 - Average Price:
  Question: "What is NVDA's average closing price in the last 30 days?"
  SQL: SELECT AVG(close) FROM market_data WHERE ticker='NVDA' AND "timestamp" >= (SELECT MAX("timestamp")-'30 days'::interval FROM market_data WHERE ticker='NVDA');
  Why: Uses MAX with ticker scope, aggregates correctly, no unnecessary LIMIT

Example 2 - Multi-ticker Comparison:
  Question: "Compare NVDA and AAPL closing prices"
  SQL: SELECT ticker, AVG(close) as avg_close FROM market_data WHERE ticker IN ('NVDA','AAPL') GROUP BY ticker;
  Why: Uses proper GROUP BY, correct AVG function, reasonable LIMIT for non-aggregation

Example 3 - Recent Trend:
  Question: "Show NVDA's daily prices for the last week"
  SQL: SELECT "timestamp", close FROM market_data WHERE ticker='NVDA' AND "timestamp" >= (SELECT MAX("timestamp")-'7 days'::interval FROM market_data WHERE ticker='NVDA') ORDER BY "timestamp" DESC LIMIT 7;
  Why: Proper time filtering, double quotes on timestamp, includes LIMIT for non-aggregation

BAD EXAMPLES (patterns to AVOID):
❌ Bad Example 1 - Wrong aggregation:
  Question: "What is NVDA's total revenue?"
  SQL: SELECT AVG(close) FROM market_data WHERE ticker='NVDA';
  Problem: Uses AVG for what should be SUM or detailed data. Missing time scope.

❌ Bad Example 2 - Using NOW():
  Question: "NVDA price in the last 30 days"
  SQL: SELECT close FROM market_data WHERE ticker='NVDA' AND "timestamp" > NOW() - interval '30 days';
  Problem: Uses NOW() instead of MAX("timestamp"). Doesn't work for historical data.

❌ Bad Example 3 - No GROUP BY:
  Question: "Compare NVDA vs AAPL"
  SQL: SELECT ticker, close FROM market_data WHERE ticker IN ('NVDA','AAPL');
  Problem: No GROUP BY or aggregation. Returns too many rows without structure.

Schema:
{schema}

User question:
{question}

Remember: Output ONLY the SQL statement, nothing else."""

ANSWER_SUMMARY_PROMPT_TEMPLATE = """
You are a financial data assistant. Your task is to generate clear, concise, and accurate answers based ONLY on the SQL query results.

====================
ANALYSIS FRAMEWORK
====================

1. Extract key numbers from the returned data (prices, volumes, returns, changes, etc.).

2. Identify trends or patterns ONLY if they are directly supported by the returned SQL results.
   - If the returned data contains a time series, describe the observed trend.
   - Do not infer trends from a single aggregated value.

3. Compare across tickers, dates, or groups ONLY when multiple comparable rows are returned.

4. Provide data-supported observations only.
   - Do NOT provide investment advice.
   - Do NOT infer market sentiment, causes, future movement, or business implications unless explicitly supported by the returned data.

====================
GROUNDING RULES
====================

Your answer MUST be completely grounded in the SQL query result.

- Use ONLY the information explicitly contained in the SQL results.
- Never fabricate facts or statistics.
- Never infer volatility, stability, momentum, or causality unless the SQL results explicitly contain sufficient evidence.
- If the SQL result contains only one aggregated value (e.g., AVG, SUM, COUNT, MAX, MIN), answer only using that value.
- If the SQL results are insufficient to answer part of the user's question, explicitly state that the available data is insufficient.

====================
FORMATTING RULES
====================

- Be concise but informative.
- Use precise numbers with context.
- For comparisons, clearly state which value is higher, lower, larger, or smaller.
- For time-series results, summarize observable trends supported by the returned data.
- For aggregation queries, highlight the returned statistics without adding unsupported interpretation.
- Mention important data limitations when appropriate.

====================
OUTPUT STRUCTURE
====================

1. Directly answer the user's question.
2. Present the key supporting numbers.
3. If applicable, summarize observable patterns directly supported by the returned data.
4. Mention any important limitations or missing information.

====================
USER QUESTION
====================

{question}

====================
SQL QUERY
====================

{sql}

====================
RETURNED DATA
====================

Columns:
{columns}

Rows:
{rows}

====================
FINAL ANSWER
====================

Generate a clear, factual, and data-grounded answer.
"""
