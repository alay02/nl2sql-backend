"""The :class:`AssetClass` interface.

An asset class supplies everything the generic NL2SQL engine needs to serve
questions about one financial domain (equities, fixed income, FX, ...).
The engine consumes an ``AssetClass`` and imports no domain constants directly,
so adding a new domain is one new subclass plus one registry line.

This is a pure-interface module: it defines the contract only. Concrete
configuration lives in the implementations (e.g. ``equities.py``).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Set


class AssetClass(ABC):
    """Domain-specific configuration for one financial asset class.

    Properties are the domain's data (schema, allow-lists, prompts, ...) and
    the two methods are behavior the engine calls. Concrete subclasses may
    hold these as plain attributes; the abstract properties only fix the
    read interface the engine relies on.
    """

    # ---- Identity -------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``"equities"``. Used by the registry."""

    # ---- Database shape -------------------------------------------------
    @property
    @abstractmethod
    def schema(self) -> str:
        """Human-readable schema description injected into the SQL prompt."""

    @property
    @abstractmethod
    def allowed_tables(self) -> Set[str]:
        """Tables the engine may query. Enforced by ``sql_guard``."""

    @property
    @abstractmethod
    def allowed_columns(self) -> Set[str]:
        """Columns considered valid for this asset class."""

    @property
    @abstractmethod
    def numeric_columns(self) -> Set[str]:
        """Columns holding numeric values (used for formatting / tolerance)."""

    # ---- Symbol dictionary + parser ------------------------------------
    @property
    @abstractmethod
    def symbols(self) -> List[str]:
        """Supported symbols/tickers for this asset class (lowercase)."""

    @abstractmethod
    def find_symbols(self, text: str) -> List[str]:
        """Return supported symbols mentioned as whole words in ``text``.

        Whole-word matching so a symbol like ``meta`` is not matched inside
        an unrelated word such as ``metadata``.
        """

    # ---- Clarification rules -------------------------------------------
    @property
    @abstractmethod
    def clarification_rules(self) -> Dict[str, List[str]]:
        """Keyword lists driving ambiguity detection.

        Expected keys: ``ambiguous``, ``time_indicators``,
        ``comparison_indicators``, ``volatility_measures``,
        ``performance_metrics``.
        """

    # ---- Prompts --------------------------------------------------------
    @property
    @abstractmethod
    def sql_generation_prompt(self) -> str:
        """Template for the SQL-generation prompt (``{schema}``/``{question}``)."""

    @property
    @abstractmethod
    def answer_summary_prompt(self) -> str:
        """Template for the answer-summary prompt."""

    # ---- Limits ---------------------------------------------------------
    @property
    @abstractmethod
    def default_limit(self) -> int:
        """Default ``LIMIT`` applied to non-aggregation queries."""

    # ---- Entitlements (future hook, directive #3) -----------------------
    @property
    def entitlement_rules(self) -> Dict[str, Any]:
        """Role-based access rules. Empty until entitlements are built.

        Concrete, not abstract: asset classes need not define this yet, so
        the default keeps today's implementations simple.
        """
        return {}
