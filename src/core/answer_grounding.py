"""Answer grounding validation for NL2SQL responses."""

from typing import Any, Dict, List


def validate_answer_grounding(sql: str, data: Dict[str, Any], final_answer: str) -> Dict[str, Any]:
    """
    Validate whether the final natural-language answer is grounded in the SQL result.
    """
    sql_lower = (sql or "").lower()
    answer_lower = (final_answer or "").lower()
    columns = [str(c).lower() for c in data.get("columns", [])]
    rows = data.get("rows", [])

    issues: List[str] = []

    has_single_aggregate = (
        len(rows) == 1
        and len(columns) == 1
        and any(fn in sql_lower for fn in ["avg(", "sum(", "count(", "max(", "min("])
    )

    has_time_series = any(c in columns for c in ["timestamp", "date", "month"])
    has_volatility_metric = any(
        c in columns
        for c in ["stddev", "stddev_pop", "stddev_samp", "variance", "range", "volatility", "return"]
    )

    mentions_trend = any(
        word in answer_lower
        for word in ["trend", "trending", "increasing", "decreasing", "stable", "upward", "downward"]
    )

    mentions_volatility = any(
        word in answer_lower
        for word in ["volatility", "volatile", "variance", "standard deviation"]
    )

    mentions_causality = any(
        phrase in answer_lower
        for phrase in ["because", "due to", "driven by", "caused by", "as a result of"]
    )

    if has_single_aggregate and mentions_trend:
        issues.append("Answer mentions trend or stability based on a single aggregate value.")

    if mentions_trend and not has_time_series and has_single_aggregate:
        issues.append("Answer infers trend without time-series output.")

    if mentions_volatility and not has_volatility_metric:
        issues.append("Answer mentions volatility without a volatility-related SQL result.")

    if mentions_causality:
        issues.append("Answer includes causal language that may not be supported by SQL results.")

    return {
        "answer_grounded": len(issues) == 0,
        "unsupported_claims": issues,
    }