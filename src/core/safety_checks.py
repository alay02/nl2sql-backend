"""SQL safety validation and security checks"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from src.constants import ALLOWED_TABLES, ALLOWED_COLUMNS, SUPPORTED_TICKERS, TIME_INDICATORS
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Individual Check Functions ====================


def check_select_only(sql: str) -> bool:
    """
    Verify that SQL is a SELECT or WITH query.
    
    Args:
        sql: SQL query to check
        
    Returns:
        True if query is SELECT/WITH only
    """
    if not sql:
        return False
    s = sql.strip().lower()
    return s.startswith("select") or s.startswith("with")


def check_no_table_modification(sql: str) -> bool:
    """
    Verify that SQL does not modify, create, or drop tables.
    
    Args:
        sql: SQL query to check
        
    Returns:
        True if query does not modify tables
    """
    if not sql:
        return False
    s = sql.lower()
    banned = [
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
    return not any(b in s for b in banned)


def check_source_correct(sql: str) -> bool:
    """
    Verify that SQL only accesses allowed tables.
    
    Args:
        sql: SQL query to check
        
    Returns:
        True if query only uses allowed tables
    """
    if not sql:
        return False
    s = sql.lower()
    
    # Find table names after FROM or JOIN
    tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", s)
    if not tables:
        return False
    
    return all(t in ALLOWED_TABLES for t in tables)


def check_time_window_correct(question: str, sql: str) -> bool:
    """
    Verify that time window handling is correct.
    
    Rules:
    1. If question mentions time-related keywords, SQL should not use NOW()
    2. If question mentions ticker names, time window should use MAX(timestamp)
    
    Args:
        question: Original question
        sql: Generated SQL
        
    Returns:
        True if time window is correct
    """
    if not sql:
        return False
    
    q = question.lower()
    s = sql.lower()
    
    # Check if question uses time keywords
    needs_time_rule = any(k in q for k in TIME_INDICATORS)
    
    if not needs_time_rule:
        return True
    
    # Historical data should not use NOW()
    if "now(" in s:
        return False
    
    # If specific ticker is mentioned, time window should include MAX(timestamp)
    mentioned_tickers = [t.upper() for t in SUPPORTED_TICKERS if t in q]
    
    if mentioned_tickers:
        # Should use MAX(timestamp) for time windowing
        if 'max("timestamp")' not in s and "max(timestamp)" not in s:
            return False
    
    return True


def check_permission_granted(exec_status: str, error_message: str = "") -> bool:
    """
    Verify that backend has database execution permissions.
    
    Args:
        exec_status: Query execution status
        error_message: Error message if any
        
    Returns:
        True unless permission-related error occurred
    """
    # These statuses indicate successful execution or non-permission errors
    if exec_status in {"ok", "no_data", "clarify"}:
        return True
    
    # Check for permission-related errors
    msg = (error_message or "").lower()
    permission_markers = ["permission denied", "not authorized", "insufficient privilege"]
    if any(m in msg for m in permission_markers):
        return False
    
    # Other errors default to True (may be SQL logic errors, not permission issues)
    return True


def check_connection_stable(exec_status: str, error_message: str = "") -> bool:
    """
    Verify that database connection is stable.
    
    Args:
        exec_status: Query execution status
        error_message: Error message if any
        
    Returns:
        False if connection-related error occurred, True otherwise
    """
    if exec_status != "error":
        return True
    
    # Check for connection-related errors
    msg = (error_message or "").lower()
    connection_markers = [
        "connection",
        "ssl",
        "pool",
        "timeout",
        "closed",
        "disconnected",
    ]
    
    return not any(marker in msg for marker in connection_markers)


# ==================== Comprehensive Safety Check ====================


def build_safety_checks(
    question: str,
    sql: Optional[str],
    status: str,
    message: str = "",
) -> Dict[str, Any]:
    """
    Build comprehensive three-stage safety checks.
    
    Stages:
    1. sql_generation: Verify SQL is safe to generate
    2. safety_validation: Verify business rules are followed
    3. execution: Verify execution state
    
    Args:
        question: Original question
        sql: Generated SQL (may be None for clarify/error)
        status: Query execution status
        message: Error message if any
        
    Returns:
        Dict with three safety check stages
    """
    logger.debug("Building safety checks...")
    
    return {
        "sql_generation": {
            "select_only": check_select_only(sql) if sql else False,
            "no_table_modification": check_no_table_modification(sql) if sql else False,
            "source_correct": check_source_correct(sql) if sql else False,
        },
        "safety_validation": {
            "time_window_correct": check_time_window_correct(question, sql) if sql else False,
        },
        "execution": {
            "permission_granted": check_permission_granted(status, message),
            "connection_stable": check_connection_stable(status, message),
        },
    }
