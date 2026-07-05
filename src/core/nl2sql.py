"""SQL generation, validation, and execution"""
import re
from typing import Any, Dict

from src.config import settings
from src.constants import (
    DB_SCHEMA,
    DB_SCHEMAS,
    DEFAULT_LIMIT,
    SQL_GENERATION_PROMPT_TEMPLATE,
    SQL_GENERATION_PROMPT_ETFS,
    SQL_GENERATION_PROMPT_OPTIONS,
    SQL_KEYWORDS_BANNED,
    SUPPORTED_TICKERS,
    SUPPORTED_ETF_TICKERS,
    SUPPORTED_OPTION_UNDERLYINGS,
    TIME_INDICATORS,
    AMBIGUOUS_KEYWORDS,
    COMPARISON_INDICATORS,
    VOLATILITY_MEASURES,
    PERFORMANCE_METRICS,
)

SQL_PROMPTS = {
    "equities": SQL_GENERATION_PROMPT_TEMPLATE,
    "etfs": SQL_GENERATION_PROMPT_ETFS,
    "options": SQL_GENERATION_PROMPT_OPTIONS,
}
from src.core.sql_guard import guard_sql
from src.exceptions import ClarificationNeeded, DatabaseError, SQLGenerationError
from src.utils.db import get_db_engine
from src.utils.llm import get_openai_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_sql(question: str, product_type: str = "equities") -> str:
    """
    Generate SQL from natural language question using LLM.

    Args:
        question: Natural language question
        product_type: One of "equities", "etfs", "options"

    Returns:
        Generated SQL string

    Raises:
        SQLGenerationError: If SQL generation fails
    """
    try:
        client = get_openai_client()

        schema = DB_SCHEMAS.get(product_type, DB_SCHEMA)
        prompt_template = SQL_PROMPTS.get(product_type, SQL_GENERATION_PROMPT_TEMPLATE)
        prompt = prompt_template.format(
            schema=schema,
            question=question,
            limit=DEFAULT_LIMIT,
        )
        
        logger.debug(f"Generating SQL for question: {question}")
        
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.LLM_TEMPERATURE,
        )
        
        sql = response.choices[0].message.content.strip()
        
        # Remove markdown code fences if present
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        logger.debug(f"Generated SQL: {sql[:100]}...")
        
        return sql
    except Exception as e:
        logger.error(f"SQL generation failed: {e}")
        raise SQLGenerationError(f"Failed to generate SQL: {str(e)}")


def run_sql(sql: str) -> Dict[str, Any]:
    """
    Execute SQL query and return results.
    
    Args:
        sql: SQL query to execute
        
    Returns:
        Dict with 'columns' and 'rows' keys
        
    Raises:
        DatabaseError: If query execution fails
    """
    try:
        engine = get_db_engine()
        from sqlalchemy import text
        
        logger.debug(f"Executing SQL: {sql[:100]}...")
        
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            cols = list(result.keys())
            rows = []
            
            for r in result.fetchall():
                # Handle datetime and other non-JSON-serializable objects
                rr = []
                for v in r:
                    if hasattr(v, "isoformat"):
                        rr.append(v.isoformat())
                    else:
                        rr.append(v)
                rows.append(rr)
        
        logger.debug(f"Query returned {len(rows)} rows")
        
        return {"columns": cols, "rows": rows}
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database query failed: {str(e)}")


# ==================== SQL Security Layer ====================


def clean_sql(raw: str) -> str:
    """
    Clean SQL string by removing markdown formatting.
    
    Args:
        raw: Raw SQL string
        
    Returns:
        Cleaned SQL string
    """
    sql = raw.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def enforce_select_only(sql: str) -> str:
    """
    Enforce that only SELECT or WITH queries are allowed.
    
    Args:
        sql: SQL to validate
        
    Returns:
        Validated SQL
        
    Raises:
        SQLGenerationError: If SQL violates rules
    """
    s = sql.strip().lower()
    
    # forbid multiple statements: only one statement allowed
    if ";" in sql.strip()[:-1]:
        raise SQLGenerationError("Rejected: multiple SQL statements detected.")
    
    # must be SELECT or WITH ... SELECT
    if not (s.startswith("select") or s.startswith("with")):
        raise SQLGenerationError("Rejected: only SELECT queries are allowed.")
    
    # forbid dangerous keywords
    if any(b in s for b in SQL_KEYWORDS_BANNED):
        raise SQLGenerationError("Rejected: dangerous SQL keyword detected.")
    
    return sql


def ensure_limit(sql: str, default_limit: int = DEFAULT_LIMIT) -> str:
    """
    Ensure query has appropriate LIMIT clause.
    
    Args:
        sql: SQL query
        default_limit: Default limit value
        
    Returns:
        SQL with LIMIT added if needed
    """
    if re.search(r"\blimit\b", sql, flags=re.IGNORECASE):
        return sql.rstrip(";") + ";"
    
    # Skip LIMIT for aggregation queries
    if any(agg in sql.lower() for agg in ["avg(", "sum(", "max(", "min(", "count("]):
        return sql
    
    return sql.rstrip(";") + f"\nLIMIT {default_limit};"


def secure_sql(raw_sql: str) -> str:
    """
    Apply all security validations to SQL.
    
    Args:
        raw_sql: Raw SQL string
        
    Returns:
        Secured SQL string
    """
    sql = clean_sql(raw_sql)
    sql = guard_sql(sql)
    sql = ensure_limit(sql)
    return sql


# ==================== Clarification Detection ====================


# Matches an explicit, quantified time window such as "30 days", "past 2 weeks",
# "last 3 months", or "this year" - anything that pins the query to a concrete period.
_EXPLICIT_TIME_WINDOW_RE = re.compile(
    r"\b\d+\s*(?:day|week|month|quarter|year)s?\b"
    r"|\b(?:last|past|previous|trailing|this)\s+(?:\d+\s+)?(?:day|week|month|quarter|year)s?\b",
    flags=re.IGNORECASE,
)

# Single-word relative terms that fully specify a time window on their own.
_EXPLICIT_TIME_TERMS = ("today", "yesterday")


def has_explicit_time_window(question: str) -> bool:
    """
    Check whether the question already specifies a concrete time window.

    Replaces a brittle hardcoded list (which only recognised exact strings like
    "30 days" or "1 month") so natural phrasings such as "past 2 weeks" or
    "last 3 months" are correctly recognised and not flagged as ambiguous.

    Args:
        question: Natural language question

    Returns:
        True if a concrete time window is present, False otherwise
    """
    q = question.lower()
    if _EXPLICIT_TIME_WINDOW_RE.search(q):
        return True
    return any(term in q for term in _EXPLICIT_TIME_TERMS)


def find_mentioned_tickers(question: str) -> list:
    """
    Find supported tickers mentioned as whole words in the question.

    Uses word boundaries so a ticker like "meta" is not matched inside an
    unrelated word such as "metadata".

    Args:
        question: Natural language question

    Returns:
        List of supported tickers found in the question
    """
    q = question.lower()
    return [
        ticker
        for ticker in SUPPORTED_TICKERS
        if re.search(rf"\b{re.escape(ticker)}\b", q)
    ]


def needs_clarification(question: str, product_type: str = "equities") -> Dict[str, Any]:
    """
    Check if the question needs clarification before SQL generation.

    Args:
        question: Natural language question
        product_type: Product type — used to skip inapplicable checks
        
    Returns:
        Dict with 'needs_clarify' bool and 'missing_slots' if clarification needed
    """
    q_lower = question.lower()
    
    # Check if any ambiguous keyword is present
    has_ambiguous = any(keyword in q_lower for keyword in AMBIGUOUS_KEYWORDS)
    
    if not has_ambiguous:
        return {"needs_clarify": False}
    
    missing_slots = {}
    
    # Check for time window ambiguity
    has_time_ambiguity = any(indicator in q_lower for indicator in TIME_INDICATORS)
    if has_time_ambiguity and not has_explicit_time_window(question):
        missing_slots["time_window"] = (
            "Please specify a time period (e.g., 'past 30 days', 'last month')"
        )
    
    # Check for comparison ambiguity
    has_comparison = any(indicator in q_lower for indicator in COMPARISON_INDICATORS)
    if has_comparison:
        mentioned_tickers = find_mentioned_tickers(question)
        if len(mentioned_tickers) < 2:
            missing_slots["comparison_baseline"] = (
                "Please specify what to compare against (e.g., 'NVDA compared to AAPL')"
            )
    
    # Check for volatility ambiguity (skip for options — IV is a concrete column)
    if "volatility" in q_lower and product_type != "options" and not any(
        measure in q_lower for measure in VOLATILITY_MEASURES
    ) and "implied" not in q_lower:
        missing_slots["volatility_measure"] = (
            "Please specify how to measure volatility "
            "(e.g., 'standard deviation of returns', 'price range')"
        )
    
    # Check for performance ambiguity
    if "performance" in q_lower and not any(
        metric in q_lower for metric in PERFORMANCE_METRICS
    ):
        missing_slots["performance_metric"] = (
            "Please specify performance metric (e.g., 'price return', 'volume')"
        )
    
    if missing_slots:
        return {"needs_clarify": True, "missing_slots": missing_slots}
    
    return {"needs_clarify": False}


# ==================== Main Query Processing ====================


def eval_one(question: str, product_type: str = "equities") -> Dict[str, Any]:
    """
    Process a question through the entire NL2SQL pipeline.

    Args:
        question: Natural language question from user
        product_type: One of "equities", "etfs", "options"

    Returns:
        Dict with status, SQL, data, and metadata
    """
    if not question or not question.strip():
        logger.warning("Received empty question")
        return {
            "status": "error",
            "sql": None,
            "data": None,
            "message": "Question cannot be empty",
        }

    question = question.strip()
    logger.info(f"Processing question ({product_type}): {question}")

    # Check if clarification is needed first
    clarify_check = needs_clarification(question, product_type=product_type)
    if clarify_check["needs_clarify"]:
        logger.info("Question needs clarification")
        return {
            "status": "clarify",
            "missing_slots": clarify_check["missing_slots"],
            "message": "The question needs clarification to generate an accurate query.",
        }

    try:
        # Generate SQL using the product-specific prompt and schema
        raw_sql = generate_sql(question, product_type=product_type)
        sql = secure_sql(raw_sql)
        
        # 1.2 Optimization: Validate and correct SQL
        validator = SQLValidator()
        validation_result = validator.validate(sql)
        
        if not validation_result["valid"] and len(validation_result["issues"]) > 0:
            logger.info(f"SQL validation issues found: {validation_result['issues']}")
            corrector = SQLCorrector()
            sql = corrector.correct(sql, question)
            sql = secure_sql(sql)  # Re-secure after correction
            logger.info(f"SQL corrected using LLM")
        
        # Execute query
        data = run_sql(sql)
        
        # Check if data is empty
        if len(data["rows"]) == 0:
            logger.info("Query returned no rows")
            return {
                "status": "no_data",
                "sql": sql,
                "data": data,
                "message": "No data found for the given query conditions.",
            }
        
        # Check if all values are None
        if all(all(v is None for v in row) for row in data["rows"]):
            logger.info("Query returned only NULL values")
            return {
                "status": "no_data",
                "sql": sql,
                "data": data,
                "message": "Query executed but returned no valid values.",
            }
        
        logger.info("Query successful")
        return {
            "status": "ok",
            "sql": sql,
            "data": data,
            "message": "",
            "meta": {
                "has_limit": "limit" in sql.lower(),
                "uses_now": "now(" in sql.lower(),
            },
        }
    
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        return {
            "status": "error",
            "sql": None,
            "data": None,
            "message": str(e),
        }


class SQLValidator:
    """Validates SQL queries for common mistakes"""
    
    def validate(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL and identify issues.
        
        Returns:
            {
                "valid": bool,
                "issues": [{"type": str, "message": str}],
                "suggested_fix": str or None
            }
        """
        issues = []
        
        # Check 1: Aggregation without GROUP BY (except COUNT(*))
        has_agg = any(agg in sql.upper() for agg in ["AVG(", "SUM(", "MAX(", "MIN("])
        has_group = "GROUP BY" in sql.upper()
        if has_agg and not has_group:
            issues.append({
                "type": "aggregation_warning",
                "message": "Aggregation function detected without GROUP BY - verify this is intentional"
            })
        
        # Check 2: Using NOW() for historical data
        if "NOW()" in sql.upper():
            issues.append({
                "type": "now_function",
                "message": "Using NOW() - consider using MAX(\"timestamp\") for historical data"
            })
        
        # Check 3: Missing LIMIT on SELECT
        if "LIMIT" not in sql.upper() and "GROUP BY" not in sql.upper():
            issues.append({
                "type": "missing_limit",
                "message": "Missing LIMIT clause - this could return too many rows"
            })
        
        # Check 4: Check for time window conditions
        has_time_filter = "timestamp" in sql.lower() and (">" in sql or ">" in sql)
        if "ticker" in sql.lower() and not has_time_filter:
            issues.append({
                "type": "missing_time_filter",
                "message": "Query on ticker but no time window - consider adding date filtering"
            })
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suggested_fix": None
        }


class SQLCorrector:
    """Corrects SQL based on validation issues"""
    
    def correct(self, sql: str, question: str) -> str:
        """
        Attempt to correct SQL errors using LLM.
        
        Args:
            sql: Original SQL
            question: Original question for context
            
        Returns:
            Corrected SQL string
        """
        try:
            client = get_openai_client()
            
            correction_prompt = f"""Given the SQL and question below, suggest corrections if needed.
            
Question: {question}

Current SQL: {sql}

Common issues to check:
1. Missing GROUP BY with aggregation functions
2. Inappropriate use of NOW() - should use MAX("timestamp") for historical data
3. Unnecessary complex joins
4. Missing LIMIT clause

If the SQL looks correct, output it unchanged. If there are issues, output ONLY the corrected SQL statement.

Output ONLY the SQL, nothing else."""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": correction_prompt}],
                temperature=0.2,
                max_tokens=300
            )
            
            corrected = response.choices[0].message.content.strip()
            logger.info(f"SQL corrected - Original: {sql[:50]}... -> Corrected: {corrected[:50]}...")
            return corrected
            
        except Exception as e:
            logger.warning(f"SQL correction failed, using original: {e}")
            return sql
