"""Asset-class modules for the NL2SQL engine.

Each asset class (equities, and future ones) bundles the domain-specific
configuration the generic engine needs: schema, allow-lists, symbol
dictionary + parser, clarification keyword rules, prompts, and limits.

The engine (``src.core``) depends only on the :class:`AssetClass` interface,
never on a concrete asset's constants.
"""
