"""Planning point queries and data.gov.uk dataset discovery.

Dataset discovery exposes metadata, not an automatic right to download, reuse
or redistribute the underlying resources. Resource URLs are returned as data;
this module never follows them.
"""

from __future__ import annotations

import re
from typing import Any

from ..geo import validate_limit, validate_point
from ..results import envelope
from ..transport import DataAccessError, HttpClient

PLANNING_BASE = "https://www.planning.data.gov.uk"
# The documented data.gov.uk/api/action endpoint redirects to this canonical
# production CKAN host, verified 2026-10-27. No arbitrary redirect host is needed.
CATALOGUE_BASE = "https://ckan.publishing.service.gov.uk/api/action"
_DATASET = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
_FIELDS = (
    "entity",
    "name",
    "dataset",
    "reference",
    "entry-date",
    "start-date",
    "end-date",
    "point",
)


def _offset(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
        raise ValueError("offset must be an integer between 0 and 1000000.")
    return value


def _count(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


async def planning_entities(
    client: HttpClient,
    dataset: str,
    latitude: float,
    longitude: float,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """One projected page of an England planning dataset intersecting a point."""
    if not isinstance(dataset, str) or not _DATASET.fullmatch(dataset):
        raise ValueError("dataset must be a Planning Data dataset slug, not a URL or path.")
    latitude, longitude = validate_point(latitude, longitude)
    limit, offset = validate_limit(limit), _offset(offset)
    query = {
        "dataset": dataset,
        "latitude": latitude,
        "longitude": longitude,
        "limit": limit,
        "offset": offset,
    }
    params = {
        "dataset": dataset,
        "latitude": latitude,
        "longitude": longitude,
        "limit": limit,
        "offset": offset,
        "field": list(_FIELDS),
    }
    result = await client.get_json(f"{PLANNING_BASE}/entity.json", params=params)
    payload = result.data
    if not isinstance(payload, dict) or not isinstance(payload.get("entities"), list):
        raise DataAccessError(
            "Planning Data response has no entities list.", code="invalid_response", url=result.url
        )
    if any(not isinstance(item, dict) for item in payload["entities"]):
        raise DataAccessError(
            "Planning entities must be records.", code="invalid_response", url=result.url
        )
    # Projection is also applied locally in case a provider stops honouring field.
    records = [
        {key: item[key] for key in _FIELDS if key in item} for item in payload["entities"][:limit]
    ]
    total = _count(payload.get("count"))
    links = payload.get("links", {})
    next_reported = isinstance(links, dict) and bool(links.get("next"))
    partial = (
        next_reported
        or len(payload["entities"]) > limit
        or (total > offset + len(records) if total is not None else len(records) >= limit)
    )
    warnings = [
        "Planning Data covers England and coverage varies by dataset and local authority. "
        "No returned records does not establish absence of planning constraints.",
        "This is a geometry-intersects-point query, not a nearby search or a search of a site boundary. "
        "Point assets such as listed buildings may not match an arbitrary coordinate.",
        "Geometry is omitted from returned records to keep responses bounded; only selected metadata fields are returned.",
        "Entry and start/end dates are source metadata; they are not proof of a current planning determination.",
    ]
    metadata: dict[str, Any] = {
        "coverage": "England",
        "crs": "EPSG:4326",
        "spatial_predicate": "intersects_point",
        "fields": list(_FIELDS),
        "geometry_omitted": True,
        "licence_status": "unknown_until_dataset_metadata_checked",
        "dataset_page": f"{PLANNING_BASE}/dataset/{dataset}",
        "pagination": {"offset": offset, "limit": limit, "returned": len(records), "total": total},
    }
    requests = [result]
    metadata_failed = False
    try:
        dataset_result = await client.get_json(f"{PLANNING_BASE}/dataset/{dataset}.json")
        requests.append(dataset_result)
        dataset_metadata = dataset_result.data
        if not isinstance(dataset_metadata, dict) or dataset_metadata.get("dataset") != dataset:
            raise DataAccessError(
                "Planning dataset metadata did not match the requested dataset.",
                code="invalid_response",
                url=dataset_result.url,
            )
        wanted = (
            "dataset",
            "name",
            "description",
            "text",
            "licence",
            "licence-text",
            "attribution",
            "attribution-text",
            "phase",
            "entry-date",
            "start-date",
            "end-date",
        )
        metadata["dataset_metadata"] = {
            key: dataset_metadata[key] for key in wanted if key in dataset_metadata
        }
        metadata["licence_status"] = (
            "provider_declared" if dataset_metadata.get("licence") else "unknown"
        )
        metadata["licence_evidence_url"] = dataset_result.url
        if not dataset_metadata.get("licence"):
            warnings.append(
                "The dataset metadata did not state a licence; verify reuse terms with the publisher."
            )
    except DataAccessError:
        metadata_failed = True
        warnings.append(
            "Dataset licence/attribution metadata could not be retrieved; reuse permission remains unverified."
        )
    return envelope(
        "planning_data",
        records,
        requests=requests,
        query=query,
        warnings=warnings,
        total=total,
        truncated=partial or offset > 0,
        next_page={**query, "offset": offset + len(records)} if partial and records else None,
        metadata=metadata,
        status="partial" if metadata_failed else None,
    )


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id",
        "name",
        "title",
        "license_id",
        "license_title",
        "license_url",
        "isopen",
        "metadata_created",
        "metadata_modified",
        "url",
        "version",
    )
    item = {key: record[key] for key in keep if key in record}
    publisher = record.get("organization")
    if isinstance(publisher, dict):
        item["publisher"] = {
            key: publisher[key] for key in ("id", "name", "title") if key in publisher
        }
    notes = record.get("notes")
    if isinstance(notes, str):
        item["notes"] = notes[:3000]
        item["notes_truncated"] = len(notes) > 3000
    # Keep access constraints and attribution rather than inferring an open
    # licence from the fact that the catalogue entry is publicly readable.
    extras = record.get("extras", [])
    if isinstance(extras, list):
        item["access_and_coverage_metadata"] = [
            extra
            for extra in extras
            if isinstance(extra, dict)
            and isinstance(extra.get("key"), str)
            and any(
                token in extra["key"].lower()
                for token in (
                    "access",
                    "licen",
                    "attribution",
                    "constraint",
                    "spatial",
                    "temporal",
                    "frequency",
                )
            )
        ]
    resources = record.get("resources", [])
    if not isinstance(resources, list):
        resources = []
    resource_fields = (
        "id",
        "name",
        "format",
        "url",
        "mimetype",
        "last_modified",
        "license",
        "licence",
    )
    item["resources"] = [
        {key: resource[key] for key in resource_fields if key in resource}
        for resource in resources[:20]
        if isinstance(resource, dict)
    ]
    item["resources_truncated"] = len(resources) > 20
    item["resource_count"] = len(resources)
    item["reuse_status"] = (
        "publisher_declares_open_check_licence"
        if record.get("isopen") is True
        else "restricted_or_unconfirmed_check_publisher_terms"
    )
    return item


async def data_gov_search(
    client: HttpClient, query: str, limit: int = 10, offset: int = 0
) -> dict[str, Any]:
    """Search dataset metadata in data.gov.uk; never follows resource download URLs."""
    if (
        not isinstance(query, str)
        or not query.strip()
        or len(query) > 500
        or any(ord(c) < 32 for c in query)
    ):
        raise ValueError("query must contain 1 to 500 printable characters.")
    query = query.strip()
    limit, offset = validate_limit(limit), _offset(offset)
    result = await client.get_json(
        f"{CATALOGUE_BASE}/package_search",
        params={"q": query, "rows": limit, "start": offset},
    )
    payload = result.data
    if (
        not isinstance(payload, dict)
        or payload.get("success") is not True
        or not isinstance(payload.get("result"), dict)
    ):
        raise DataAccessError(
            "data.gov.uk catalogue reported an unsuccessful search.",
            code="invalid_response",
            url=result.url,
        )
    upstream = payload["result"]
    records = upstream.get("results")
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise DataAccessError(
            "data.gov.uk search did not return dataset records.",
            code="invalid_response",
            url=result.url,
        )
    items = [_summary(record) for record in records[:limit]]
    total = _count(upstream.get("count"))
    partial = len(records) > limit or (
        total > offset + len(items) if total is not None else len(items) >= limit
    )
    query_info = {"query": query, "limit": limit, "offset": offset}
    return envelope(
        "data_gov_uk",
        items,
        requests=[result],
        query=query_info,
        total=total,
        truncated=partial or offset > 0,
        next_page={**query_info, "offset": offset + len(items)} if partial and items else None,
        warnings=[
            "Catalogue results are dataset metadata. Resource files have not been downloaded or validated.",
            "A public catalogue entry is not permission to reuse the dataset. Check publisher access restrictions, "
            "dataset/resource licences and attribution before downloading, processing or redistribution.",
            "metadata_modified is the catalogue record's modification time, not the observation date or freshness of the data.",
            "Dataset geography varies across UK providers. Notes are capped at 3000 characters and resource lists at 20 per dataset.",
        ],
        metadata={
            "coverage": "UK catalogue; individual datasets vary",
            "discovery_only": True,
            "resource_urls_followed": False,
            "canonical_endpoint_note": "Documented data.gov.uk/api/action redirects to this production CKAN host.",
            "documentation": "https://guidance.data.gov.uk/get_data/api_documentation/",
            "pagination": {
                "offset": offset,
                "limit": limit,
                "returned": len(items),
                "total": total,
            },
        },
    )
