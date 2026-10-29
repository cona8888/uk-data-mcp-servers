"""Bounded desk-study evidence and a reviewable ground-investigation gap register.

This layer composes the existing read-only tools. It does not interpret logs,
estimate material properties, place investigation locations or certify a site.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from .adapters.bgs import COLLECTIONS
from .coverage import incomplete_entries as _incomplete_entries
from .geo import bbox_around, validate_limit, validate_point
from .groundwater import groundwater_kind
from .results import error_envelope
from .transport import DataAccessError, utc_now

DEVELOPMENT_TYPES = (
    "general",
    "housing",
    "industrial",
    "solar_battery",
    "basement",
    "corridor",
    "brownfield",
)
NATIONS = ("England", "Scotland", "Wales", "Northern Ireland")
INDEXES = ("onshoreboreholeindex", "agsboreholeindex")
_REQUEST_KEYS = (
    "latitude",
    "longitude",
    "nation",
    "project_name",
    "development_type",
    "works_description",
    "radius_km",
    "limit_per_source",
    "max_borehole_pages",
    "max_groundwater_measures",
)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")
_DESIGN_PARAMETERS = (
    "effective_stress_friction_angle_deg",
    "undrained_shear_strength_kPa",
    "soil_stiffness_MPa",
    "permeability_m_per_s",
    "design_groundwater_level_mAOD",
    "allowable_bearing_pressure_kPa",
    "buried_utility_clearance_m",
)
ToolCall = Callable[[str, dict], Awaitable[dict]]


def validate_request(
    *,
    latitude: float,
    longitude: float,
    nation: str,
    project_name: str = "Untitled project",
    development_type: str = "general",
    works_description: str = "",
    radius_km: float = 1,
    limit_per_source: int = 10,
    max_borehole_pages: int = 3,
    max_groundwater_measures: int = 3,
) -> dict:
    """Validate the entire request before any provider or MCP call is made."""
    latitude, longitude = validate_point(latitude, longitude)
    if not isinstance(nation, str) or nation not in NATIONS:
        raise ValueError(f"nation must be one of {', '.join(NATIONS)}.")
    if not isinstance(project_name, str) or not project_name.strip() or len(project_name) > 120:
        raise ValueError("project_name must contain 1 to 120 characters.")
    if not isinstance(works_description, str) or len(works_description) > 2000:
        raise ValueError("works_description must be at most 2000 characters.")
    if not isinstance(development_type, str) or development_type not in DEVELOPMENT_TYPES:
        raise ValueError(f"development_type must be one of {', '.join(DEVELOPMENT_TYPES)}.")
    validate_limit(limit_per_source, maximum=20)
    validate_limit(max_borehole_pages, maximum=5)
    if (
        isinstance(max_groundwater_measures, bool)
        or not isinstance(max_groundwater_measures, int)
        or not 0 <= max_groundwater_measures <= 5
    ):
        raise ValueError("max_groundwater_measures must be an integer from 0 to 5.")
    bbox = bbox_around(latitude, longitude, radius_km)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "nation": nation,
        "project_name": project_name.strip(),
        "development_type": development_type,
        "works_description": works_description.strip(),
        "radius_km": float(radius_km),
        "limit_per_source": limit_per_source,
        "max_borehole_pages": max_borehole_pages,
        "max_groundwater_measures": max_groundwater_measures,
        "bgs_bbox_crs84": bbox,
    }


def _source_id(tool: str, arguments: dict) -> str:
    if tool == "bgs_features":
        return COLLECTIONS[arguments["collection"]]["source_id"]
    return {
        "ea_stations": "ea_flood",
        "ea_floods": "ea_flood",
        "ea_readings": "ea_flood",
        "hydrology_stations": "ea_hydrology",
        "hydrology_readings": "ea_hydrology",
        "planning_entities": "planning_data",
    }[tool]


async def _query(call: ToolCall, evidence: list, topic: str, tool: str, arguments: dict) -> dict:
    try:
        result = await call(tool, copy.deepcopy(arguments))
        if not isinstance(result, dict) or result.get("status") not in {
            "ok",
            "partial",
            "empty",
            "error",
        }:
            raise DataAccessError(
                "Tool returned no valid result envelope.", code="invalid_response"
            )
    except (DataAccessError, ValueError) as exc:
        result = error_envelope(_source_id(tool, arguments), exc, arguments)
    entry = {
        "id": f"query-{len(evidence) + 1:03d}",
        "topic": topic,
        "tool": tool,
        "arguments": copy.deepcopy(arguments),
        "status": result["status"],
        "result": result,
    }
    evidence.append(entry)
    return entry


def _measure_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith(("https://", "http://")):
        try:
            parts = urlsplit(value)
            prefix = "/hydrology/id/measures/"
            if (
                parts.hostname != "environment.data.gov.uk"
                or parts.username
                or parts.password
                or parts.port not in (None, 80, 443)
                or parts.query
                or parts.fragment
                or not parts.path.startswith(prefix)
            ):
                return None
            value = parts.path[len(prefix) :]
        except ValueError:
            return None
    return value if _IDENTIFIER.fullmatch(value) and ".." not in value else None


def _measures(
    stations: list, *, include_unclassified: bool = False
) -> list[tuple[str, dict]]:
    """Filter explicit series metadata before the follow-up budget is applied."""
    found: dict[str, dict] = {}
    for station in stations:
        if not isinstance(station, dict):
            continue
        measures = station.get("measures", [])
        if isinstance(measures, dict):
            measures = [measures]
        if not isinstance(measures, list):
            continue
        for measure in measures:
            if not isinstance(measure, dict):
                continue
            identifier = _measure_id(measure.get("notation")) or _measure_id(measure.get("@id"))
            if identifier and (
                include_unclassified or groundwater_kind(measure) == "confirmed"
            ):
                found.setdefault(identifier, station)
    return list(found.items())


def _confirmed_groundwater(measure: Any, identifier: str) -> bool:
    if groundwater_kind(measure) != "confirmed":
        return False
    returned_id = _measure_id(measure.get("notation")) or _measure_id(measure.get("@id"))
    return returned_id is None or returned_id == identifier


async def build_desk_study(
    call: ToolCall,
    *,
    latitude: float,
    longitude: float,
    nation: str,
    project_name: str = "Untitled project",
    development_type: str = "general",
    works_description: str = "",
    radius_km: float = 1,
    limit_per_source: int = 10,
    max_borehole_pages: int = 3,
    max_groundwater_measures: int = 3,
) -> dict:
    """Gather a bounded evidence bundle, candidate records and unanswered GI questions."""
    request = validate_request(
        latitude=latitude,
        longitude=longitude,
        nation=nation,
        project_name=project_name,
        development_type=development_type,
        works_description=works_description,
        radius_km=radius_km,
        limit_per_source=limit_per_source,
        max_borehole_pages=max_borehole_pages,
        max_groundwater_measures=max_groundwater_measures,
    )
    evidence: list[dict] = []
    omitted: list[str] = []
    bbox = request["bgs_bbox_crs84"]
    # Sequential requests also avoid multiplying provider load when pages are followed.
    for collection in ("bgsgeology625kbedrock", "bgsgeology625ksuperficial"):
        await _query(
            call,
            evidence,
            "regional_geology",
            "bgs_features",
            {
                "collection": collection,
                "bbox": bbox,
                "limit": limit_per_source,
            },
        )
    if nation != "Northern Ireland":
        for collection in INDEXES:
            arguments = {
                "collection": collection,
                "bbox": bbox,
                "limit": limit_per_source,
                "offset": 0,
                "include_geometry": True,
            }
            for page in range(max_borehole_pages):
                entry = await _query(
                    call, evidence, "historic_investigations", "bgs_features", arguments
                )
                entry["page_number"] = page + 1
                result = entry["result"]
                next_page = result.get("pagination", {}).get("next_page")
                if result["status"] == "error" or not next_page:
                    break
                # Do not accept changed collections, URLs, query bounds or non-advancing offsets.
                next_offset = next_page.get("offset") if isinstance(next_page, dict) else None
                current_offset = arguments["offset"]
                if (
                    isinstance(next_offset, bool)
                    or not isinstance(next_offset, int)
                    or not current_offset < next_offset <= 2_000_000
                    or not result.get("data")
                ):
                    entry["pagination_stop_reason"] = (
                        "Provider continuation did not advance safely."
                    )
                    break
                if page + 1 == max_borehole_pages:
                    entry["pagination_stop_reason"] = "Configured page limit reached."
                    break
                entry["pagination_followed"] = True
                arguments = {**arguments, "offset": next_offset}
        await _query(
            call,
            evidence,
            "recorded_landslides",
            "bgs_features",
            {
                "collection": "landslideindex",
                "bbox": bbox,
                "limit": limit_per_source,
                "include_geometry": True,
            },
        )
    else:
        omitted.append(
            "SOBI, AGS and landslide indexes omitted for Northern Ireland; obtain relevant GSNI records."
        )
    if nation == "England":
        location = {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "limit": limit_per_source,
        }
        for topic, tool in (
            ("surface_water_stations", "ea_stations"),
            ("current_flood_warnings", "ea_floods"),
        ):
            await _query(call, evidence, topic, tool, location)
        stations = await _query(
            call,
            evidence,
            "groundwater_stations",
            "hydrology_stations",
            {
                **location,
                "observed_property": "groundwaterLevel",
            },
        )
        await _query(
            call,
            evidence,
            "planning_authority",
            "planning_entities",
            {
                "dataset": "local-planning-authority",
                "latitude": latitude,
                "longitude": longitude,
                "limit": limit_per_source,
            },
        )
        station_records = stations["result"].get("data", [])
        measures = _measures(station_records)
        uncertain: dict[str, tuple[dict, str]] = {}
        for station in station_records:
            series = station.get("measures", []) if isinstance(station, dict) else []
            series = [series] if isinstance(series, dict) else series
            for measure in series if isinstance(series, list) else []:
                if not isinstance(measure, dict):
                    continue
                identifier = _measure_id(measure.get("notation")) or _measure_id(measure.get("@id"))
                kind = groundwater_kind(measure)
                if identifier and kind in {"unknown", "conflicting"}:
                    if identifier not in uncertain or kind == "conflicting":
                        uncertain[identifier] = (station, kind)
        conflicts = {identifier for identifier, (_, kind) in uncertain.items() if kind == "conflicting"}
        measures = [(identifier, station) for identifier, station in measures if identifier not in conflicts]
        confirmed_ids = {identifier for identifier, _ in measures}
        uncertain = {identifier: item for identifier, item in uncertain.items() if identifier not in confirmed_ids}
        unresolved = set(uncertain)
        # EA embeds compact measure references without observedProperty. Resolve
        # a bounded number of descriptions, rather than guessing from ID text.
        metadata_budget = min(10, 2 * max_groundwater_measures)
        inspections = 0
        for identifier, (station, kind) in uncertain.items():
            if kind == "conflicting":
                continue
            if len(measures) >= max_groundwater_measures or inspections >= metadata_budget:
                break
            inspections += 1
            entry = await _query(
                call, evidence, "groundwater_measure_metadata", "hydrology_readings",
                {"measure_id": identifier, "limit": 1, "metadata_only": True},
            )
            result = entry["result"]
            description = (result.get("metadata") or {}).get("measure", {})
            if entry["status"] != "error" and _confirmed_groundwater(description, identifier):
                measures.append((identifier, station))
                unresolved.discard(identifier)
                entry["groundwater_validation"] = {"status": "confirmed", "basis": "explicit series description"}
            elif entry["status"] != "error" and groundwater_kind(description) == "other":
                unresolved.discard(identifier)
                entry["groundwater_validation"] = {"status": "other", "basis": "not a groundwater series"}
        if unresolved:
            omitted.append(
                f"Skipped {len(unresolved)} series with missing or conflicting measurement-type "
                f"metadata after {inspections} bounded description lookups (maximum {metadata_budget}). "
                "Obtain explicit groundwaterLevel metadata before following them."
            )
        for identifier, _station in measures[:max_groundwater_measures]:
            entry = await _query(
                call,
                evidence,
                "groundwater_readings",
                "hydrology_readings",
                {
                    "measure_id": identifier,
                    "limit": limit_per_source,
                },
            )
            result = entry["result"]
            if entry["status"] != "error":
                measure = (result.get("metadata") or {}).get("measure", {})
                confirmed = _confirmed_groundwater(measure, identifier)
                entry["groundwater_validation"] = {
                    "status": "confirmed" if confirmed else "rejected",
                    "basis": "explicit returned measure metadata; not the station filter or ID text",
                }
                if not confirmed:
                    omitted.append(
                        f"{entry['id']}: returned metadata did not confirm the requested groundwater "
                        "series. Original response retained in the source register, excluded from "
                        "groundwater observations."
                    )
        if len(measures) > max_groundwater_measures:
            omitted.append(
                f"Groundwater follow-up capped at {max_groundwater_measures} of "
                f"{len(measures)} confirmed groundwater measure identifiers (provider order; not quality-ranked)."
            )
    else:
        omitted.append(
            "EA observations and Planning Data omitted outside England; obtain nation-specific sources."
        )
    return assemble_report(evidence, request, omitted_queries=omitted)


def _text(value: Any) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    value = str(value).strip()
    return (
        value
        if value and value.upper() not in {"N/A", "NULL", "NONE", "UNKNOWN", "NOT KNOWN"}
        else None
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _coordinates(feature: dict, properties: dict) -> tuple[float | None, float | None]:
    geometry = feature.get("geometry")
    if isinstance(geometry, dict) and geometry.get("type") == "Point":
        values = geometry.get("coordinates")
        if isinstance(values, (list, tuple)) and len(values) >= 2:
            longitude, latitude = _number(values[0]), _number(values[1])
            if (
                latitude is not None
                and longitude is not None
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                return latitude, longitude
    latitude = _number(properties.get("latitude", properties.get("lat")))
    longitude = _number(properties.get("longitude", properties.get("long")))
    if (
        latitude is not None
        and longitude is not None
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        return latitude, longitude
    return None, None


def _distance(latitude: float, longitude: float, request: dict) -> float:
    a, b = math.radians(request["latitude"]), math.radians(latitude)
    dlat, dlon = b - a, math.radians(longitude - request["longitude"])
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return round(6_371_008.8 * 2 * math.asin(min(1, math.sqrt(h))), 1)


def _safe_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and not parts.username
            and not parts.password
        ):
            return value
    except ValueError:
        pass
    return None


def _record_identity(feature: dict, properties: dict, fallback: str) -> str:
    for value in (
        feature.get("id"),
        properties.get("bgs_loca_id"),
        properties.get("bgs_id"),
        properties.get("id"),
        properties.get("reference"),
    ):
        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            value = int(value)
        if _text(value):
            return str(value)
    # A record without a provider ID/reference is retained separately, not guessed to be a duplicate.
    return fallback


def _investigations(evidence: list[dict], request: dict) -> list[dict]:
    found: dict[tuple[str, str], dict] = {}
    for entry in evidence:
        collection = entry["arguments"].get("collection")
        if collection not in INDEXES or entry["status"] == "error":
            continue
        for index, feature in enumerate(entry["result"].get("data", [])):
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties")
            properties = properties if isinstance(properties, dict) else {}
            identity = _record_identity(feature, properties, f"{entry['id']}-{index}")
            key = collection, identity
            if key in found:
                candidate = found[key]
                if entry["id"] not in candidate["evidence_ids"]:
                    candidate["evidence_ids"].append(entry["id"])
                candidate["duplicate_records"] += 1
                continue
            latitude, longitude = _coordinates(feature, properties)
            distance = _distance(latitude, longitude, request) if latitude is not None else None
            links = []
            for field, label in (
                ("scan_url", "Borehole scan"),
                ("ags_log_url", "AGS log"),
                ("ags_url", "AGS file"),
                ("sitereport", "Site report"),
                ("dad_item_url", "BGS accession"),
                ("url", "Provider record"),
            ):
                url = _safe_url(properties.get(field))
                if url and url not in {link["url"] for link in links}:
                    links.append({"label": label, "url": url})
            token = hashlib.sha256(f"{collection}:{identity}".encode()).hexdigest()[:12]
            depth = _number(properties.get("length"))
            if depth is None:
                depth = _number(properties.get("depth"))
            if collection == "agsboreholeindex" and depth is None:
                # BGS AGS_Export uses AGS4 LOCA_FDEP, "Final depth", in metres.
                # https://map.bgs.ac.uk/ArcGIS/rest/services/AGS/AGS_Export/MapServer/0
                # https://www.ags.org.uk/content/uploads/2022/02/AGS4-v-4.1.1-2022.pdf
                depth = _number(properties.get("loca_fdep"))
            reference = _text(properties.get("reference"))
            name = _text(properties.get("name"))
            if collection == "agsboreholeindex":
                reference = _text(properties.get("loca_id")) or reference
                name = _text(properties.get("proj_name")) or name
            found[key] = {
                "id": f"investigation-{token}",
                "collection": collection,
                "provider_id": identity,
                "reference": reference or identity,
                "name": name,
                "depth_m": depth if depth is not None and depth >= 0 else None,
                "year": _text(properties.get("year_known", properties.get("year"))),
                "updated_at": _text(properties.get("date_updated")),
                "position_precision": _text(properties.get("precision")),
                "latitude": latitude,
                "longitude": longitude,
                "distance_m": distance,
                "within_radius": distance <= request["radius_km"] * 1000
                if distance is not None
                else None,
                "links": links,
                "evidence_ids": [entry["id"]],
                "duplicate_records": 0,
                "provider_properties": copy.deepcopy(properties),
                "review": {"status": "unreviewed", "notes": ""},
            }
    return list(found.values())


def _groundwater(evidence: list[dict]) -> list[dict]:
    stations = [
        station
        for entry in evidence
        if entry["tool"] == "hydrology_stations"
        for station in entry["result"].get("data", [])
    ]
    lookup = dict(_measures(stations, include_unclassified=True))
    output = []
    for entry in evidence:
        if entry["tool"] != "hydrology_readings" or entry["arguments"].get("metadata_only"):
            continue
        identifier = entry["arguments"].get("measure_id")
        station = lookup.get(identifier, {})
        result = entry["result"]
        measure = (result.get("metadata") or {}).get("measure", {})
        if entry["status"] != "error" and (
            groundwater_kind(measure) != "confirmed"
            or entry.get("groundwater_validation", {}).get("status") == "rejected"
        ):
            continue
        output.append(
            {
                "id": entry["id"],
                "station_name": station.get("label"),
                "measure_id": identifier,
                "evidence_id": entry["id"],
                "status": entry["status"],
                "measure": copy.deepcopy(measure),
                "readings": copy.deepcopy(result.get("data", [])),
                "warnings": copy.deepcopy(result.get("warnings", [])),
                "retrieved_at_utc": result.get("retrieved_at_utc"),
            }
        )
    return output


def _gaps(
    evidence: list[dict], investigations: list[dict], request: dict, omitted: list[str]
) -> list[dict]:
    gaps: list[dict] = []

    def add(identifier, priority, topic, title, reason, actions, entries=()):
        gaps.append(
            {
                "id": identifier,
                "priority": priority,
                "topic": topic,
                "title": title,
                "reason": reason,
                "actions": list(actions),
                "evidence_ids": [e["id"] for e in entries],
                "status": "open",
                "notes": "",
            }
        )

    def by_topic(topic):
        return [e for e in evidence if e["topic"] == topic]

    add(
        "site-scope",
        "high",
        "project",
        "Confirm the site boundary and proposed works",
        "The search uses a supplied point and approximate enclosing box; it does not establish a site boundary or construction loads.",
        [
            "Confirm the boundary, levels, proposed structures, loading and access constraints.",
            "Agree the desk-study and investigation objectives with the project geotechnical engineer.",
        ],
    )
    add(
        "investigation-review",
        "high",
        "historic_investigations",
        "Review the original investigation records",
        f"{len(investigations)} unique index candidates were retrieved. Index entries do not establish usable stratigraphy or test parameters; search gaps remain possible.",
        [
            "Open the original logs or AGS files under their applicable terms.",
            "Review location precision, age, investigation purpose, depths, sampling and relevance to the proposed works.",
            "Record relevance and reasons for each candidate before planning additional investigation.",
        ],
        by_topic("historic_investigations"),
    )
    add(
        "detailed-ground-model",
        "high",
        "regional_geology",
        "Establish a site-specific conceptual ground model",
        "Implemented geology is 1:625,000 regional mapping. It cannot resolve local strata, fill, weathering or founding levels.",
        [
            "Obtain suitably detailed mapping and relevant historic records.",
            "Review a site walkover and original investigation logs; identify unresolved strata and geological boundaries.",
        ],
        by_topic("regional_geology"),
    )
    add(
        "groundwater-model",
        "high",
        "groundwater",
        "Establish site groundwater conditions",
        "Nearby stations and latest available readings do not establish the site's aquifer, seasonal groundwater range or pore pressures.",
        [
            "Review station/aquifer relevance, observation dates, units, datum and per-reading quality.",
            "Obtain relevant historical series and agree site monitoring where required.",
            "Keep groundwater elevation and depth below ground distinct.",
        ],
        by_topic("groundwater_stations") + by_topic("groundwater_readings"),
    )
    add(
        "design-parameters",
        "high",
        "material_properties",
        "Obtain evidence for geotechnical design parameters",
        "Strength, stiffness, permeability, bearing pressure and design groundwater level remain unestablished.",
        [
            "Define required parameters from the proposed works and conceptual ground model.",
            "Agree appropriate field and laboratory investigation, quality requirements and interpretation with the geotechnical engineer.",
        ],
    )
    add(
        "history-contamination",
        "high" if request["development_type"] == "brownfield" else "medium",
        "site_history",
        "Review site history and potential contamination",
        "This workflow does not retrieve a complete historic land-use record, remediation history or site contamination assessment.",
        [
            "Review historic maps, former uses, local records and relevant environmental reports.",
            "Define contamination questions and investigation needs from evidenced source-pathway-receptor relationships.",
        ],
    )
    add(
        "mining-ground-hazards",
        "medium",
        "ground_hazards",
        "Obtain relevant mining and ground-hazard evidence",
        "The implemented sources do not provide a comprehensive mine-workings, dissolution or ground-stability search.",
        [
            "Establish whether mining or other ground-hazard searches are relevant from detailed geology and site history.",
            "Obtain authorised records and investigate unresolved features where relevant.",
        ],
        by_topic("recorded_landslides"),
    )
    add(
        "utilities-access",
        "high",
        "utilities",
        "Confirm utilities and safe investigation access",
        "Public evidence does not establish buried utility positions, depths, absence or investigation clearance.",
        [
            "Obtain current asset-owner records and appropriate utility surveys.",
            "Confirm permissions, access, service avoidance and investigation constraints before intrusive work.",
        ],
    )
    add(
        "terrain-walkover",
        "medium",
        "terrain",
        "Review terrain, drainage and neighbouring assets",
        "The workflow does not ingest terrain surveys, drainage condition, structure condition or a site walkover.",
        [
            "Review site levels, slopes, drainage, adjacent structures and signs of previous movement during a walkover.",
            "Obtain surveyed levels and asset information appropriate to the proposed works.",
        ],
        by_topic("recorded_landslides")
        + by_topic("surface_water_stations")
        + by_topic("current_flood_warnings"),
    )
    extra = {
        "housing": (
            "housing-scope",
            "Resolve foundation and serviceability investigation questions",
            [
                "Confirm building layouts, loading, trees, drainage and allowable movement criteria.",
                "Use the reviewed ground model to define unresolved foundation and earthworks questions.",
            ],
        ),
        "industrial": (
            "industrial-scope",
            "Resolve floor, foundation and earthworks investigation questions",
            [
                "Confirm structural and slab loading, settlement tolerances and proposed cut/fill.",
                "Agree investigation questions for bearing strata, fill variability and earthworks materials.",
            ],
        ),
        "solar_battery": (
            "energy-scope",
            "Resolve support, platform and cable-route investigation questions",
            [
                "Confirm support systems, platform loads, cable routes, access and drainage.",
                "Agree investigation questions for shallow variability, installation constraints and platform performance.",
            ],
        ),
        "basement": (
            "excavation-scope",
            "Resolve excavation, groundwater and adjacent-asset questions",
            [
                "Confirm excavation geometry, retained heights, adjacent assets and movement criteria.",
                "Assess the evidence needed for groundwater control, permeability and support design with the project specialists.",
            ],
        ),
        "corridor": (
            "corridor-scope",
            "Extend coverage along the supplied alignment",
            [
                "Obtain the full alignment and proposed works; this point search covers only its local area.",
                "Review evidence by segment, deduplicate overlapping searches and identify crossing, slope and access questions.",
            ],
        ),
        "brownfield": (
            "brownfield-scope",
            "Resolve redevelopment and made-ground investigation questions",
            [
                "Review demolition, former structures, underground obstructions and remediation records.",
                "Coordinate geotechnical and contamination investigation objectives before defining intrusive work.",
            ],
        ),
    }
    if request["development_type"] in extra:
        identifier, title, actions = extra[request["development_type"]]
        add(
            identifier,
            "high",
            "project",
            title,
            "These are investigation questions based on the selected development type; they are not observed hazards or a design solution.",
            actions,
        )
    for entry in evidence:
        if entry["status"] == "error":
            add(
                f"failure-{entry['id']}",
                "high",
                "source_coverage",
                f"Resolve failed query {entry['id']}",
                f"The {entry['topic']} query failed. No absence finding can be made from this result.",
                [
                    "Review the recorded provider error and request parameters.",
                    "Retry appropriately or obtain equivalent evidence and preserve the original failure.",
                ],
                [entry],
            )
    for entry in _incomplete_entries(evidence):
        add(
            f"coverage-{entry['id']}",
            "medium",
            "source_coverage",
            f"Review incomplete query {entry['id']}",
            entry.get("pagination_stop_reason")
            or "This bounded query may omit further matching records or metadata.",
            [
                "Review pagination and provider metadata before treating the retrieved page as a complete search.",
                "If relevant, continue within an agreed request budget and retain the search history.",
            ],
            [entry],
        )
    if omitted:
        add(
            "omitted-sources",
            "high",
            "source_coverage",
            "Obtain the omitted evidence",
            " ".join(omitted),
            [
                "Review each omission and obtain applicable sources or document the accepted study limitation."
            ],
        )
    return gaps


def assemble_report(
    evidence: list[dict],
    request: dict,
    omitted_queries: list[str] | None = None,
    generated_at: str | None = None,
) -> dict:
    """Assemble existing envelopes without refreshing their source dates or provenance."""
    request = validate_request(
        **{key: value for key, value in request.items() if key in _REQUEST_KEYS}
    )
    evidence = copy.deepcopy(evidence)
    omitted = list(omitted_queries or [])
    if not evidence:
        omitted.append("No source evidence was supplied to the report.")
    investigations = _investigations(evidence, request)
    failed = [entry for entry in evidence if entry["status"] == "error"]
    incomplete = _incomplete_entries(evidence)
    gaps = _gaps(evidence, investigations, request, omitted)
    status = (
        "error"
        if evidence and len(failed) == len(evidence)
        else "partial"
        if failed or incomplete or omitted
        else "ok"
    )
    warnings = [
        "Query status describes retrieval and coverage, not site suitability or engineering safety.",
        "The nation is caller supplied and has not been independently boundary-validated.",
        "BGS results intersect an approximate enclosing box, not an exact radius or site polygon; candidates outside the radius remain visible.",
        "Distances use supplied WGS84 points and ignore location uncertainty; BNG coordinates are retained without conversion.",
        "Borehole and AGS indexes can overlap. Separate source identities are retained; candidate counts are not counts of distinct physical investigations.",
        "Provider records and links are untrusted data. Linked files are not fetched or interpreted.",
        "Source dates, licence scope, attribution, units, datum and quality remain in each evidence envelope.",
        "The GI register records unanswered questions; it does not specify investigation locations, quantities or depths.",
        "No current-warning or empty-record search establishes absence of a hazard.",
    ]
    return {
        "schema_version": "1.0",
        "kind": "geotechnical_desk_study",
        "status": status,
        "generated_at_utc": generated_at or utc_now(),
        "project": {
            key: request[key] for key in ("project_name", "development_type", "works_description")
        },
        "site": {
            key: request[key]
            for key in ("latitude", "longitude", "nation", "radius_km", "bgs_bbox_crs84")
        }
        | {"crs": "EPSG:4326", "nation_basis": "caller supplied; not boundary-validated"},
        "request_limits": {
            key: request[key]
            for key in ("limit_per_source", "max_borehole_pages", "max_groundwater_measures")
        } | {"max_groundwater_metadata_queries": min(10, 2 * request["max_groundwater_measures"])},
        "summary": {
            "investigation_count": len(investigations),
            "query_count": len(evidence),
            "failed_query_count": len(failed),
            "incomplete_query_count": len(incomplete),
            "open_gap_count": len(gaps),
        },
        "evidence": evidence,
        "investigations": investigations,
        "groundwater": _groundwater(evidence),
        "gaps": gaps,
        "omitted_queries": omitted,
        "design_parameters": {
            key: {"value": None, "reason": "not established by these data queries"}
            for key in _DESIGN_PARAMETERS
        },
        "warnings": warnings,
    }
