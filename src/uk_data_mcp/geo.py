"""Explicit WGS84 coordinates; no silent British National Grid conversion."""

import math


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    return float(value)


def validate_point(latitude: float, longitude: float) -> tuple[float, float]:
    """Broad UK bounding rectangle, not a country-boundary or coverage check."""
    latitude = _finite(latitude, "latitude")
    longitude = _finite(longitude, "longitude")
    if not 49.0 <= latitude <= 61.5 or not -9.5 <= longitude <= 2.5:
        raise ValueError(
            "Expected UK WGS84 decimal degrees: latitude 49..61.5, longitude -9.5..2.5; do not pass easting/northing."
        )
    return latitude, longitude


def validate_bbox(bbox: list[float], max_span_degrees: float = 2.0) -> list[float]:
    """Return [west, south, east, north] in OGC CRS84 (longitude, latitude)."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("bbox must contain [west, south, east, north] in decimal degrees.")
    west, south, east, north = [_finite(v, "bbox coordinate") for v in bbox]
    validate_point(south, west)
    validate_point(north, east)
    if west >= east or south >= north:
        raise ValueError("bbox requires west < east and south < north.")
    if east - west > max_span_degrees or north - south > max_span_degrees:
        raise ValueError(
            f"Use a smaller area: each bbox span must be <= {max_span_degrees} degrees."
        )
    return [west, south, east, north]


def validate_limit(limit: int, maximum: int = 100) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise ValueError(f"limit must be an integer from 1 to {maximum}.")
    return limit


def validate_offset(offset: int) -> int:
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 100_000:
        raise ValueError("offset must be an integer from 0 to 100000.")
    return offset


def bbox_around(latitude: float, longitude: float, radius_km: float) -> list[float]:
    """Approximate enclosing box for discovery; not a survey buffer or exact radius."""
    latitude, longitude = validate_point(latitude, longitude)
    radius_km = _finite(radius_km, "radius_km")
    if not 0.1 <= radius_km <= 20:
        raise ValueError("radius_km must be between 0.1 and 20 km.")
    dy = radius_km / 110.0
    dx = radius_km / (110.0 * math.cos(math.radians(latitude)))
    return validate_bbox(
        [
            max(-9.5, longitude - dx),
            max(49.0, latitude - dy),
            min(2.5, longitude + dx),
            min(61.5, latitude + dy),
        ]
    )
