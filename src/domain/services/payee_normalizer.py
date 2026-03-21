"""Payee name normalization for consistent learning lookups."""

from typing import Dict

# Pre-built normalization lookup: variant -> canonical name
_PAYEE_NORMALIZATIONS: Dict[str, str] = {}
_NORMALIZATION_RULES = {
    "mcdonalds": ["mcdonald's", "mc donald's", "mc donalds"],
    "home burguer": ["home burger", "homeburger", "home-burger"],
    "exito": ["éxito", "almacenes éxito", "almacenes exito"],
    "carulla": ["carulla fresh market", "supermercados carulla"],
    "olimpica": ["olímpica", "supermercados olimpica", "supermercados olímpica"],
    "falabella": ["saga falabella", "tiendas falabella"],
    "uber": ["uber technologies", "uber trip"],
    "netflix": ["netflix.com", "netflix inc"],
    "spotify": ["spotify premium", "spotify music"],
}
for _canonical, _variants in _NORMALIZATION_RULES.items():
    for _variant in _variants:
        _PAYEE_NORMALIZATIONS[_variant] = _canonical


def normalize_payee(payee: str) -> str:
    """Normalize payee name for consistency."""
    if not payee:
        return "unknown"

    normalized = payee.lower().strip()
    normalized = normalized.replace("'", "").replace('"', "")
    normalized = normalized.replace(".", "").replace(",", "")

    # O(1) lookup for exact variant matches
    if normalized in _PAYEE_NORMALIZATIONS:
        return _PAYEE_NORMALIZATIONS[normalized]

    # Substring match for partial variants (e.g. "uber technologies inc")
    for variant, canonical in _PAYEE_NORMALIZATIONS.items():
        if variant in normalized:
            return canonical

    return normalized
