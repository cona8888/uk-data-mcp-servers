"""Bounded, read-only Environment Agency adapters.

Provider documentation:
https://environment.data.gov.uk/flood-monitoring/doc/reference
https://environment.data.gov.uk/hydrology/doc/reference

Observation times, datum labels and quality flags are preserved. These tools
do not calculate design flood risk or infer site groundwater conditions.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from ..geo import validate_limit, validate_point
from ..results import envelope
from ..transport import DataAccessError, FetchResult, HttpClient

FLOOD_BASE = "https://environment.data.gov.uk/flood-monitoring"
HYDROLOGY_BASE = "https://environment.data.gov.uk/hydrology"

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")
_COVERAGE = "Environment Agency service for England; not UK-wide coverage."
_RADIUS_WARNING = (
    "The provider's location filter may approximate the radius with a bounding box. "
    "Results are a bounded page, not an exhaustive survey of this site."
)
_DATUM_WARNING = (
    "Retain the supplied units and vertical datum: mASD (station datum), mAOD "
    "(Ordnance Datum), groundwater depth and flood depth are different quantities."
)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) or ".." in value:
        raise ValueError(f"{name} must be a provider identifier, not a URL or path.")
    return value


def _offset(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
        raise ValueError("offset must be an integer between 0 and 1000000.")
    return value


def _radius(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("radius_km must be a finite number from 0.1 to 50.")
    if not math.isfinite(value) or not 0.1 <= value <= 50:
        raise ValueError("radius_km must be a finite number from 0.1 to 50.")
    return float(value)


def _items(result: FetchResult) -> list[dict[str, Any]]:
    payload = result.data
    if not isinstance(payload, dict) or "items" not in payload:
        raise DataAccessError(
            "EA response has no items field.", code="invalid_response", url=result.url
        )
    items = payload["items"]
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise DataAccessError("EA items must be records.", code="invalid_response", url=result.url)
    return items


def _meta(result: FetchResult) -> dict[str, Any]:
    meta = result.data.get("meta", {})
    return meta if isinstance(meta, dict) else {}


def _page(
    result: FetchResult, limit: int, offset: int
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    items = _items(result)
    applied_limit = _meta(result).get("limit", limit)
    if isinstance(applied_limit, bool) or not isinstance(applied_limit, int) or applied_limit < 1:
        applied_limit = limit
    cap = min(limit, applied_limit)
    records = items[:limit]
    possibly_more = len(items) >= cap
    return (
        records,
        possibly_more,
        {
            "offset": offset,
            "requested_limit": limit,
            "upstream_limit": applied_limit,
            "returned": len(records),
            "has_more": None if possibly_more else False,
            "complete_snapshot": False,
        },
    )


def _location_query(latitude: float, longitude: float, radius_km: float, limit: int, offset: int):
    latitude, longitude = validate_point(latitude, longitude)
    radius_km = _radius(radius_km)
    limit = validate_limit(limit)
    offset = _offset(offset)
    query = {
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "limit": limit,
        "offset": offset,
    }
    params = {
        "lat": latitude,
        "long": longitude,
        "dist": radius_km,
        "_limit": limit,
        "_offset": offset,
    }
    return query, params


async def ea_stations(
    client: HttpClient,
    latitude: float,
    longitude: float,
    radius_km: float = 5,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """One page of EA level/flow/rainfall stations near WGS84 coordinates."""
    query, params = _location_query(latitude, longitude, radius_km, limit, offset)
    result = await client.get_json(f"{FLOOD_BASE}/id/stations.json", params=params)
    records, partial, pagination = _page(result, query["limit"], query["offset"])
    return envelope(
        "ea_flood",
        records,
        requests=[result],
        query=query,
        warnings=[_COVERAGE, _RADIUS_WARNING, _DATUM_WARNING],
        truncated=partial or query["offset"] > 0,
        next_page={**query, "offset": query["offset"] + len(records)}
        if partial and records
        else None,
        metadata={
            "upstream_metadata": _meta(result),
            "pagination": pagination,
            "crs": "EPSG:4326",
            "observation_type": "station_metadata",
        },
    )


async def ea_floods(
    client: HttpClient,
    latitude: float,
    longitude: float,
    radius_km: float = 5,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """One page of currently active warnings/alerts near a point; not flood risk."""
    query, params = _location_query(latitude, longitude, radius_km, limit, offset)
    params["min-severity"] = 3
    query["min_severity"] = 3
    result = await client.get_json(f"{FLOOD_BASE}/id/floods.json", params=params)
    records, partial, pagination = _page(result, query["limit"], query["offset"])
    next_query = {k: v for k, v in query.items() if k != "min_severity"}
    return envelope(
        "ea_flood",
        records,
        requests=[result],
        query=query,
        warnings=[
            _COVERAGE,
            _RADIUS_WARNING,
            "Current warnings and alerts are not a flood risk assessment. No returned warnings "
            "does not establish absence of flood risk, past flooding or future flooding.",
            "The beta API has no guaranteed service level and does not replace official flood-warning channels.",
        ],
        truncated=partial or query["offset"] > 0,
        next_page={**next_query, "offset": query["offset"] + len(records)}
        if partial and records
        else None,
        metadata={
            "upstream_metadata": _meta(result),
            "pagination": pagination,
            "crs": "EPSG:4326",
            "observation_type": "current_operational_warnings",
        },
    )


def _reading_warnings(records: list[dict[str, Any]], retrieved_at: Any) -> list[str]:
    warnings = [
        _COVERAGE,
        _DATUM_WARNING,
        "Latest means the most recent available observation, not a measurement at retrieval time. "
        "Preserve observation timestamps and per-reading quality flags.",
    ]
    for item in records:
        quality = item.get("quality")
        if isinstance(quality, dict):
            quality = quality.get("label", quality.get("@id", ""))
        if isinstance(quality, str) and "unchecked" in quality.lower():
            warnings.append(
                "At least one returned reading is marked Unchecked by the provider. A measure name "
                "or identifier containing 'qualified' does not override this per-reading flag."
            )
            break
    try:
        retrieval_date = date.fromisoformat(str(retrieved_at)[:10])
    except ValueError:
        retrieval_date = None
    if retrieval_date:
        for item in records:
            raw_date = item.get("date") or item.get("dateTime")
            try:
                observed_date = date.fromisoformat(str(raw_date)[:10])
            except ValueError:
                continue
            if (retrieval_date - observed_date).days > 2:
                warnings.append(
                    "At least one latest observation predates retrieval by more than two calendar days. "
                    "Check the recorded observation date before treating it as current."
                )
                break
    return warnings


async def ea_readings(client: HttpClient, station_id: str, limit: int = 20) -> dict[str, Any]:
    """Latest readings for a station's measures, retaining full measure unit/datum metadata."""
    station_id = _identifier(station_id, "station_id")
    limit = validate_limit(limit)
    result = await client.get_json(
        f"{FLOOD_BASE}/id/stations/{station_id}/readings.json",
        params={"latest": "", "_limit": limit, "_view": "full"},
    )
    records, partial, pagination = _page(result, limit, 0)
    return envelope(
        "ea_flood",
        records,
        requests=[result],
        query={"station_id": station_id, "limit": limit, "latest": True},
        warnings=_reading_warnings(records, result.retrieved_at),
        truncated=partial,
        metadata={
            "upstream_metadata": _meta(result),
            "pagination": pagination,
            "observation_type": "latest_readings",
        },
    )


async def hydrology_stations(
    client: HttpClient,
    latitude: float,
    longitude: float,
    radius_km: float = 5,
    limit: int = 20,
    offset: int = 0,
    observed_property: str = "groundwaterLevel",
) -> dict[str, Any]:
    """EA hydrology station metadata; defaults to groundwater stations."""
    allowed = {"groundwaterLevel", "waterFlow", "waterLevel", "rainfall"}
    if not isinstance(observed_property, str) or observed_property not in allowed:
        raise ValueError(f"observed_property must be one of {', '.join(sorted(allowed))}.")
    query, params = _location_query(latitude, longitude, radius_km, limit, offset)
    params["observedProperty"] = observed_property
    query["observed_property"] = observed_property
    result = await client.get_json(f"{HYDROLOGY_BASE}/id/stations.json", params=params)
    records, partial, pagination = _page(result, query["limit"], query["offset"])
    return envelope(
        "ea_hydrology",
        records,
        requests=[result],
        query=query,
        warnings=[
            _COVERAGE,
            _RADIUS_WARNING,
            _DATUM_WARNING,
            "A nearby groundwater station may monitor a different aquifer. Its level does not "
            "establish the site's groundwater depth, pore pressure or seasonal maximum.",
        ],
        truncated=partial or query["offset"] > 0,
        next_page={**query, "offset": query["offset"] + len(records)}
        if partial and records
        else None,
        metadata={
            "upstream_metadata": _meta(result),
            "pagination": pagination,
            "crs": "EPSG:4326",
            "observation_type": "station_metadata",
        },
    )


async def hydrology_readings(
    client: HttpClient, measure_id: str, limit: int = 20, *, metadata_only: bool = False
) -> dict[str, Any]:
    """Latest reading for one hydrology series, with the series' explicit unit metadata."""
    measure_id = _identifier(measure_id, "measure_id")
    limit = validate_limit(limit)
    if not isinstance(metadata_only, bool):
        raise ValueError("metadata_only must be a boolean.")
    # The desk-study composer can inspect a compact station's unknown series
    # before spending its readings budget. This option never fetches readings.
    # Sequential requests respect EA hydrology's request-volume guidance.
    measure_result = await client.get_json(f"{HYDROLOGY_BASE}/id/measures/{measure_id}.json")
    measure_records = _items(measure_result)
    if len(measure_records) != 1:
        raise DataAccessError(
            "Expected one EA hydrology measure description.",
            code="invalid_response",
            url=measure_result.url,
        )
    if metadata_only:
        return envelope(
            "ea_hydrology", measure_records, requests=[measure_result], total=1,
            query={"measure_id": measure_id, "limit": limit, "metadata_only": True},
            metadata={"measure": measure_records[0], "observation_type": "measure_metadata"},
            warnings=["Series metadata only; no water-level observations were retrieved."],
        )
    result = await client.get_json(
        f"{HYDROLOGY_BASE}/id/measures/{measure_id}/readings.json",
        params={"latest": "", "_limit": limit, "_view": "full"},
    )
    records, partial, pagination = _page(result, limit, 0)
    warnings = _reading_warnings(records, result.retrieved_at)
    warnings.append(
        "Groundwater elevation in mAOD is not depth below ground. A compatible surveyed ground "
        "elevation and the borehole context are required for that conversion."
    )
    return envelope(
        "ea_hydrology",
        records,
        requests=[measure_result, result],
        query={"measure_id": measure_id, "limit": limit, "latest": True},
        warnings=warnings,
        truncated=partial,
        metadata={
            "measure": measure_records[0],
            "upstream_metadata": _meta(result),
            "pagination": pagination,
            "observation_type": "latest_readings",
        },
    )
