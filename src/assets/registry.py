"""Asset-class registry — the engine's lookup for concrete asset classes.

Adding a future asset class is one subclass plus one entry in ``_REGISTRY``.
"""

from typing import Dict

from src.assets.base import AssetClass
from src.assets.equities import EquitiesAssetClass

DEFAULT_ASSET_CLASS = "equities"

# One shared instance per asset class; they are stateless configuration objects.
_REGISTRY: Dict[str, AssetClass] = {
    "equities": EquitiesAssetClass(),
}


def get_asset_class(name: str = DEFAULT_ASSET_CLASS) -> AssetClass:
    """Return the asset class registered under ``name``.

    Called with no argument it returns the default (equities), which is what
    the engine does today.

    Raises:
        KeyError: if ``name`` is not a registered asset class.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(
            f"Unknown asset class {name!r}. Registered asset classes: {known}"
        ) from None
