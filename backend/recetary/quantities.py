"""Parse free-form quantity strings into (value, unit) when possible.

Spanish-language inputs from the recipe corpus, e.g.:
    "400 gramos"      -> (400.0, "g")
    "1 sobre"         -> (1.0, "sobre")
    "2 cucharaditas"  -> (2.0, "cucharadita")
    "1/2 cucharada"   -> (0.5, "cucharada")
    "al gusto"        -> (None, None)
"""
from __future__ import annotations

import re
from typing import Optional

# Canonical unit normalization (left = source token, right = canonical).
_UNIT_NORMALIZE: dict[str, str] = {
    "gramo": "g", "gramos": "g", "gr": "g", "g": "g",
    "kilo": "kg", "kilos": "kg", "kilogramo": "kg", "kilogramos": "kg", "kg": "kg",
    "miligramo": "mg", "miligramos": "mg", "mg": "mg",
    "litro": "l", "litros": "l", "l": "l",
    "mililitro": "ml", "mililitros": "ml", "ml": "ml",
    "unidad": "ud", "unidades": "ud", "ud": "ud", "uds": "ud",
    "cucharada": "cucharada", "cucharadas": "cucharada",
    "cucharadita": "cucharadita", "cucharaditas": "cucharadita",
    "sobre": "sobre", "sobres": "sobre",
    "diente": "diente", "dientes": "diente",
    "lata": "lata", "latas": "lata",
    "bote": "bote", "botes": "bote",
    "paquete": "paquete", "paquetes": "paquete",
    "ramita": "ramita", "ramitas": "ramita",
    "puñado": "puñado", "puñados": "puñado",
    "pizca": "pizca", "pizcas": "pizca",
    "taza": "taza", "tazas": "taza",
    "rodaja": "rodaja", "rodajas": "rodaja",
}

_NUMBER_RE = re.compile(
    r"^\s*(?P<num>\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s+(?P<unit>[a-zA-Záéíóúñü]+)",
    re.IGNORECASE,
)


def _parse_number(token: str) -> Optional[float]:
    token = token.strip().replace(",", ".")
    if "/" in token:
        try:
            num, den = (float(x.strip()) for x in token.split("/", 1))
            return num / den if den else None
        except ValueError:
            return None
    try:
        return float(token)
    except ValueError:
        return None


def parse_quantity(raw: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    if not raw:
        return None, None
    match = _NUMBER_RE.match(raw)
    if not match:
        return None, None
    value = _parse_number(match.group("num"))
    if value is None:
        return None, None
    unit_token = match.group("unit").lower()
    unit = _UNIT_NORMALIZE.get(unit_token, unit_token)
    return value, unit
