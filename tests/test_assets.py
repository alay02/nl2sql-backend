"""Tests for the asset-class package (src/assets/).

Covers the three areas from the modularization plan: interface conformance
(EquitiesAssetClass provides every member with the right shape), registry
behavior (default lookup, unknown names fail loudly), and find_symbols
whole-word matching.

Pure configuration/parsing logic; no database or LLM access required.
"""
import os

os.environ.setdefault("DATABASE_URL", "dummy://test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import pytest  # noqa: E402

from src import constants  # noqa: E402
from src.assets.base import AssetClass  # noqa: E402
from src.assets.equities import EquitiesAssetClass  # noqa: E402
from src.assets.registry import (  # noqa: E402
    DEFAULT_ASSET_CLASS,
    get_asset_class,
)


# ---------- interface conformance ----------

class TestInterfaceConformance:
    """EquitiesAssetClass satisfies the AssetClass contract."""

    def setup_method(self):
        self.asset = EquitiesAssetClass()

    def test_is_an_asset_class(self):
        assert isinstance(self.asset, AssetClass)

    def test_base_class_cannot_be_instantiated(self):
        # The socket itself is abstract; only concrete plugs can be built.
        with pytest.raises(TypeError):
            AssetClass()

    def test_name(self):
        assert self.asset.name == "equities"

    def test_schema_mentions_equities_table(self):
        assert "stock_data" in self.asset.schema

    def test_allowed_tables_is_equities_only(self):
        # Per-asset scope: equities must not reach other products' tables,
        # even though constants.ALLOWED_TABLES now spans all products.
        assert self.asset.allowed_tables == {"stock_data"}
        assert isinstance(self.asset.allowed_tables, set)

    def test_allowed_columns_are_equities_only(self):
        assert self.asset.allowed_columns == {
            "ticker", "timestamp", "open", "high", "low", "close", "volume",
        }
        # None of the ETF/options columns from the merged global set leak in.
        assert "nav" not in self.asset.allowed_columns
        assert "strike" not in self.asset.allowed_columns

    def test_numeric_columns_subset_of_allowed(self):
        assert self.asset.numeric_columns <= self.asset.allowed_columns
        assert "close" in self.asset.numeric_columns
        assert "ticker" not in self.asset.numeric_columns

    def test_symbols_match_constants(self):
        # Wrapper-first: the ticker list is still sourced from constants.
        assert self.asset.symbols == list(constants.SUPPORTED_TICKERS)

    def test_clarification_rules_keys(self):
        assert sorted(self.asset.clarification_rules) == [
            "ambiguous",
            "comparison_indicators",
            "performance_metrics",
            "time_indicators",
            "volatility_measures",
        ]

    def test_prompts_have_placeholders(self):
        assert "{schema}" in self.asset.sql_generation_prompt
        assert "{question}" in self.asset.sql_generation_prompt
        assert "{rows}" in self.asset.answer_summary_prompt

    def test_default_limit(self):
        assert self.asset.default_limit == constants.DEFAULT_LIMIT

    def test_entitlement_rules_default_empty(self):
        # Inherited concrete default; entitlements are a future hook.
        assert self.asset.entitlement_rules == {}

    def test_returned_collections_are_copies(self):
        # Mutating what a caller receives must not corrupt shared state.
        self.asset.symbols.append("fake")
        self.asset.allowed_tables.add("users")
        assert "fake" not in self.asset.symbols
        assert "users" not in self.asset.allowed_tables


# ---------- registry ----------

class TestRegistry:
    def test_default_is_equities(self):
        assert DEFAULT_ASSET_CLASS == "equities"
        assert get_asset_class().name == "equities"

    def test_lookup_by_name(self):
        assert get_asset_class("equities").name == "equities"

    def test_returns_asset_class_instance(self):
        assert isinstance(get_asset_class(), AssetClass)

    def test_unknown_name_raises_keyerror(self):
        with pytest.raises(KeyError) as exc:
            get_asset_class("bonds")
        # The error should tell the caller what IS registered.
        assert "equities" in str(exc.value)


# ---------- find_symbols whole-word matching ----------

class TestFindSymbols:
    def setup_method(self):
        self.asset = EquitiesAssetClass()

    def test_finds_single_ticker(self):
        assert self.asset.find_symbols("What is NVDA's average price?") == ["nvda"]

    def test_case_insensitive(self):
        assert self.asset.find_symbols("compare AaPl and MSFT") == ["aapl", "msft"]

    def test_meta_not_matched_inside_metadata(self):
        assert self.asset.find_symbols("show me the metadata for this table") == []

    def test_meta_matched_as_whole_word(self):
        assert self.asset.find_symbols("how did meta perform?") == ["meta"]

    def test_no_tickers(self):
        assert self.asset.find_symbols("what tables exist?") == []

    def test_matches_core_find_mentioned_tickers(self):
        # The parser must behave identically to the engine's current logic
        # (core.nl2sql.find_mentioned_tickers) so a later step can delegate
        # to it without changing behavior.
        from src.core.nl2sql import find_mentioned_tickers

        for question in [
            "compare meta vs metadata for aapl",
            "NVDA and TSLA last week",
            "nothing relevant here",
            "spy vs qqq performance",
        ]:
            assert self.asset.find_symbols(question) == find_mentioned_tickers(
                question
            )
