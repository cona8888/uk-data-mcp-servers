"""Read-only BGS adapters using the official OGC API Service BETA.

Documentation:
https://ogcapi.bgs.ac.uk/collections?f=html
https://www.bgs.ac.uk/datasets/boreholes-index/
https://www.bgs.ac.uk/datasets/bgs-geology-625k/

The supported collections are deliberately reviewed individually. Discovery of
another collection is not a statement that its data have the same licence.
All spatial queries select bounding-box candidates, not exact site conditions.
"""

from __future__ import annotations

from typing import Any

from ..geo import validate_bbox
from ..results import envelope
from ..transport import DataAccessError, HttpClient

BGS_BASE = "https://ogcapi.bgs.ac.uk"

COLLECTIONS: dict[str, dict[str, Any]] = {
    "onshoreboreholeindex": {
        "source_id": "bgs_boreholes",
        "title": "Single Onshore Borehole Index (SOBI)",
        "coverage": "Great Britain, including onshore and near-shore records",
        "warnings": [
            "Index records are not interpreted soil profiles. Review original logs, "
            "record dates and position precision before assessing relevance to a site.",
            "Scan and AGS links are returned for inspection; their files are not downloaded "
            "or interpreted. Reuse of underlying reports may have separate terms.",
        ],
    },
    "agsboreholeindex": {
        "source_id": "bgs_ags",
        "title": "AGS borehole index",
        "coverage": "Donated and released AGS records; spatial coverage is incomplete",
        "warnings": [
            "This is an index of released AGS borehole locations and links, not a download "
            "of laboratory or in-situ test results. Availability depends on donor consent.",
            "BGS-generated borehole and project IDs can differ from original investigation IDs.",
        ],
    },
    "bgsgeology625kbedrock": {
        "source_id": "bgs_geology_625k",
        "title": "BGS Geology 625K bedrock",
        "coverage": "Great Britain and Northern Ireland",
        "nominal_scale_denominator": 625000,
    },
    "bgsgeology625ksuperficial": {
        "source_id": "bgs_geology_625k",
        "title": "BGS Geology 625K superficial deposits",
        "coverage": "Great Britain and Northern Ireland",
        "nominal_scale_denominator": 625000,
    },
    "bgsgeology625kfaults": {
        "source_id": "bgs_geology_625k",
        "title": "BGS Geology 625K faults",
        "coverage": "Great Britain and Northern Ireland",
        "nominal_scale_denominator": 625000,
    },
    "bgsgeology625kdykes": {
        "source_id": "bgs_geology_625k",
        "title": "BGS Geology 625K dykes",
        "coverage": "Great Britain and Northern Ireland",
        "nominal_scale_denominator": 625000,
    },
    "landslideindex": {
        "source_id": "bgs_landslides",
        "title": "National Landslide Database index",
        "coverage": "Great Britain; excludes Northern Ireland, Isle of Man and Channel Islands",
        "warnings": [
            "This is an incomplete and historically uneven inventory of landslide surveys. "
            "Point locations do not represent landslide extents or current movement.",
            "The same landslide can have multiple survey records; do not count all records "
            "as distinct events. Preserve location accuracy and unknown dates.",
            "The BGS National Landslide Database guide states that these data must not "
            "be used for insurance purposes.",
        ],
    },
}


def _check_integer(value: int, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _count(value: Any) -> int | None:
    """Accept actual counts, not bools, strings, negative numbers or NaNs."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


async def bgs_collections(client: HttpClient) -> dict[str, Any]:
    """Discover BGS collections and mark which seven this adapter supports.

    This is a live discovery call. Unsupported collections remain discoverable
    without being silently enabled or assigned the licence of another dataset.
    """
    response = await client.get_json(f"{BGS_BASE}/collections", params={"f": "json"})
    if not isinstance(response.data, dict) or not isinstance(
        response.data.get("collections"), list
    ):
        raise DataAccessError(
            "BGS returned an invalid collection catalogue",
            code="invalid_response",
            url=response.url,
        )
    records: list[dict[str, Any]] = []
    for item in response.data["collections"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise DataAccessError(
                "BGS collection metadata is missing a valid collection ID",
                code="invalid_response",
                url=response.url,
            )
        collection_id = item["id"]
        supported = COLLECTIONS.get(collection_id)
        records.append(
            {
                "id": collection_id,
                "title": item.get("title", collection_id),
                "description": item.get("description"),
                "extent": item.get("extent"),
                "available_in_adapter": supported is not None,
                "source_id": supported["source_id"] if supported else None,
                "metadata_url": f"{BGS_BASE}/collections/{collection_id}?f=json",
                "licence_review": "reviewed for this adapter"
                if supported
                else "dataset-specific review required",
            }
        )
    return envelope(
        "bgs_ogc",
        records,
        requests=[response],
        total=len(records),
        warnings=[
            "BGS labels this service BETA; its interface and available collections can change.",
            "Discovery does not grant permission to reuse every collection. Only collections "
            "marked available_in_adapter can be queried by this version.",
        ],
        metadata={"supported_collection_ids": list(COLLECTIONS), "service_status": "BETA"},
    )


async def bgs_features(
    client: HttpClient,
    collection: str,
    bbox: list[float],
    limit: int = 20,
    offset: int = 0,
    include_geometry: bool = False,
) -> dict[str, Any]:
    """Get one bounded page of BGS features intersecting a CRS84 bbox.

    Bbox order is [west, south, east, north], in longitude/latitude degrees.
    Offset pagination and skipGeometry were checked against the live service on
    2026-10-27. No arbitrary URLs, scan downloads, or raw filters are accepted.
    """
    if not isinstance(collection, str) or collection not in COLLECTIONS:
        raise ValueError(f"Unsupported BGS collection. Choose one of: {', '.join(COLLECTIONS)}")
    limit = _check_integer(limit, "limit", 1, 100)
    offset = _check_integer(offset, "offset", 0, 2_000_000)
    if not isinstance(include_geometry, bool):
        raise ValueError("include_geometry must be a boolean")
    checked_bbox = validate_bbox(bbox, max_span_degrees=2.0)
    params = {
        "f": "json",
        "bbox": ",".join(str(coordinate) for coordinate in checked_bbox),
        "limit": limit,
        "offset": offset,
        "skipGeometry": "false" if include_geometry else "true",
    }
    response = await client.get_json(f"{BGS_BASE}/collections/{collection}/items", params=params)
    document = response.data
    if (
        not isinstance(document, dict)
        or document.get("type") != "FeatureCollection"
        or not isinstance(document.get("features"), list)
    ):
        raise DataAccessError(
            "BGS returned an invalid GeoJSON feature collection",
            code="invalid_response",
            url=response.url,
        )
    features = document["features"]
    if len(features) > limit:
        raise DataAccessError(
            "BGS returned more features than the requested page limit",
            code="invalid_response",
            url=response.url,
        )
    if any(
        not isinstance(feature, dict) or feature.get("type") != "Feature" for feature in features
    ):
        raise DataAccessError(
            "BGS returned an invalid GeoJSON feature", code="invalid_response", url=response.url
        )

    # Defend the compact-output contract if an upstream version ignores skipGeometry.
    records = [
        dict(feature, geometry=None) if not include_geometry else dict(feature)
        for feature in features
    ]
    total = _count(document.get("numberMatched"))
    links = document.get("links", [])
    upstream_has_next = isinstance(links, list) and any(
        isinstance(link, dict) and link.get("rel") == "next" for link in links
    )
    has_more = upstream_has_next or (total is not None and total > offset + len(records))
    next_offset = offset + len(records)
    # Never follow a provider-supplied URL: build validated arguments for the same tool.
    next_page = None
    if has_more and records and next_offset <= 2_000_000:
        next_page = {
            "collection": collection,
            "bbox": checked_bbox,
            "limit": limit,
            "offset": next_offset,
            "include_geometry": include_geometry,
        }

    policy = COLLECTIONS[collection]
    warnings = [
        "Results are candidates intersecting the requested bounding box, not a determination "
        "of the ground conditions at an exact point.",
        "An empty result is not evidence that a feature, borehole or hazard is absent.",
        "These records do not supply validated site-specific geotechnical design parameters.",
        "Retrieval and API response times are not survey dates; source dates are preserved separately.",
    ]
    warnings.extend(policy.get("warnings", []))
    if policy.get("nominal_scale_denominator") == 625000:
        warnings.append(
            "The nominal mapping scale is 1:625,000: use this generalised geology for "
            "regional or national context, not parcel boundaries, foundation design or "
            "a site-specific ground model."
        )
    if has_more:
        warnings.append("Only one page is returned; more matching records may exist.")
    if has_more and not records:
        warnings.append(
            "The provider reports additional records but returned an empty page; pagination cannot advance."
        )
    reported_returned = _count(document.get("numberReturned"))
    if reported_returned is not None and reported_returned != len(records):
        warnings.append("The provider's numberReturned differs from the actual feature count.")

    query = {
        "collection": collection,
        "bbox": checked_bbox,
        "limit": limit,
        "offset": offset,
        "include_geometry": include_geometry,
    }
    metadata = {
        "collection": collection,
        "title": policy["title"],
        "coverage": policy["coverage"],
        "coordinate_reference_system": "OGC:CRS84",
        "coordinate_order": "longitude, latitude",
        "selection_method": "bounding_box_intersection",
        "geometry_requested": include_geometry,
        "geometry_included": include_geometry
        and any(record.get("geometry") is not None for record in records),
        "service_status": "BETA",
        "upstream_timestamp": document.get("timeStamp"),
        "upstream_number_returned": reported_returned,
        "collection_url": f"{BGS_BASE}/collections/{collection}",
    }
    if "nominal_scale_denominator" in policy:
        metadata["nominal_scale_denominator"] = policy["nominal_scale_denominator"]

    return envelope(
        policy["source_id"],
        records,
        requests=[response],
        query=query,
        warnings=warnings,
        total=total,
        truncated=bool(has_more) or offset > 0,
        next_page=next_page,
        metadata=metadata,
    )
