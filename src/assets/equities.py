"""Equities — the first concrete :class:`AssetClass`.

Wrapper-first (per the modularization plan): this module *re-exposes* the
existing equities configuration from ``src.constants`` rather than copying
it, so behavior is provably unchanged. A follow-up PR will inline the values
here and trim ``constants.py`` to generic-only.
"""

import re
from typing import Dict, List, Set

from src.assets.base import AssetClass
from src.constants import (
    AMBIGUOUS_KEYWORDS,
    ANSWER_SUMMARY_PROMPT_TEMPLATE,
    COMPARISON_INDICATORS,
    DB_SCHEMA,
    DEFAULT_LIMIT,
    PERFORMANCE_METRICS,
    SQL_GENERATION_PROMPT_TEMPLATE,
    SUPPORTED_TICKERS,
    TIME_INDICATORS,
    VOLATILITY_MEASURES,
)


class EquitiesAssetClass(AssetClass):
    """US equities over the ``stock_data`` daily-bar table."""

    @property
    def name(self) -> str:
        return "equities"

    # ---- Database shape -------------------------------------------------
    @property
    def schema(self) -> str:
        return DB_SCHEMA

    @property
    def allowed_tables(self) -> Set[str]:
        # Equities-only. The global constants.ALLOWED_TABLES now spans every
        # product; this per-asset list is what keeps an equities question from
        # reaching etf_data / options_data / crypto_data.
        return {"stock_data"}

    @property
    def allowed_columns(self) -> Set[str]:
        # The columns of stock_data. (constants.ALLOWED_COLUMNS is now a merged
        # superset across all products, so it is not wrapped here.)
        return {"ticker", "timestamp", "open", "high", "low", "close", "volume"}

    @property
    def numeric_columns(self) -> Set[str]:
        # The numeric columns of stock_data (everything but ticker/timestamp).
        return {"open", "high", "low", "close", "volume"}

    # ---- Symbol dictionary + parser ------------------------------------
    @property
    def symbols(self) -> List[str]:
        return list(SUPPORTED_TICKERS)

    def find_symbols(self, text: str) -> List[str]:
        """Whole-word ticker matching (same logic as core.nl2sql today)."""
        q = text.lower()
        return [
            ticker
            for ticker in self.symbols
            if re.search(rf"\b{re.escape(ticker)}\b", q)
        ]

    # ---- Clarification rules -------------------------------------------
    @property
    def clarification_rules(self) -> Dict[str, List[str]]:
        return {
            "ambiguous": list(AMBIGUOUS_KEYWORDS),
            "time_indicators": list(TIME_INDICATORS),
            "comparison_indicators": list(COMPARISON_INDICATORS),
            "volatility_measures": list(VOLATILITY_MEASURES),
            "performance_metrics": list(PERFORMANCE_METRICS),
        }

    # ---- Prompts --------------------------------------------------------
    @property
    def sql_generation_prompt(self) -> str:
        return SQL_GENERATION_PROMPT_TEMPLATE

    @property
    def answer_summary_prompt(self) -> str:
        return ANSWER_SUMMARY_PROMPT_TEMPLATE

    # ---- Limits ---------------------------------------------------------
    @property
    def default_limit(self) -> int:
        return DEFAULT_LIMIT
