"""Classify series from explicit EA measurement metadata, never from ID substrings.

Provider field definitions: https://environment.data.gov.uk/hydrology/doc/reference
A station-level groundwater filter does not classify every series at that station.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

_OTHER_PROPERTIES = {
    "rainfall", "waterflow", "flow", "waterlevel", "level", "temperature",
    "dissolvedoxygen", "fdom", "bga", "turbidity", "chlorophyll", "conductivity",
    "ammonium", "nitrate", "ph",
}


def _tokens(value: Any) -> list[str]:
    if isinstance(value, dict):
        values = [value.get(key) for key in ("@id", "notation", "label")]
    else:
        values = [value]
    tokens = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            continue
        if item.startswith(("http://", "https://")):
            try:
                parsed = urlsplit(item)
                item = parsed.fragment or parsed.path.rstrip("/").rsplit("/", 1)[-1]
            except ValueError:
                continue
        tokens.append(re.sub(r"[^a-z0-9]", "", item.lower()))
    return tokens


def groundwater_kind(measure: Any) -> str:
    """Return confirmed, other, conflicting or unknown without changing metadata."""
    if not isinstance(measure, dict):
        return "unknown"
    tokens = _tokens(measure.get("observedProperty")) + _tokens(measure.get("parameterName"))
    groundwater = "groundwaterlevel" in tokens
    other = any(token in _OTHER_PROPERTIES for token in tokens)
    if groundwater and other:
        return "conflicting"
    if groundwater:
        return "confirmed"
    return "other" if other else "unknown"
