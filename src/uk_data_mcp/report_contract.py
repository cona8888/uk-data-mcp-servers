"""Semantic integrity rules for Groundwork report schema 1.0.

Used by the authoritative Python validator for CLI, browser imports and exports.
Source evidence is never repaired, replaced or assigned invented observations.
"""

from __future__ import annotations

from datetime import datetime

from .coverage import incomplete_entries
from .geo import bbox_around, validate_bbox

NATIONS = ("England", "Scotland", "Wales", "Northern Ireland")
DEVELOPMENTS = ("general", "housing", "industrial", "solar_battery", "basement", "corridor", "brownfield")
STATUSES = ("ok", "partial", "empty", "error")


def _identifier(value: object, path: str, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{path} must be a nonempty, bounded string.")
    return value


def validate_integrity(report: dict) -> None:
    """Called after structural/finite-JSON checks; does not mutate the report."""
    project, site = report["project"], report["site"]
    _identifier(project["project_name"], "project.project_name", 120)
    if project.get("development_type", "general") not in DEVELOPMENTS:
        raise ValueError("Unsupported project.development_type.")
    works = project.get("works_description", "")
    if not isinstance(works, str) or len(works) > 2000:
        raise ValueError("project.works_description must be text of at most 2000 characters.")
    if site.get("nation") not in NATIONS:
        raise ValueError("site.nation must name one of the four UK nations.")
    bbox_around(site.get("latitude"), site.get("longitude"), site.get("radius_km"))
    if site.get("bgs_bbox_crs84") is not None:
        validate_bbox(site["bgs_bbox_crs84"])
    if site.get("crs", "EPSG:4326") != "EPSG:4326":
        raise ValueError("site coordinates must use EPSG:4326.")
    try:
        timestamp = datetime.fromisoformat(report["generated_at_utc"].replace("Z", "+00:00"))
        if timestamp.utcoffset() is None:
            raise ValueError("missing time zone")
    except (ValueError, TypeError) as exc:
        raise ValueError("generated_at_utc must be an ISO timestamp with a time zone.") from exc
    if report.get("workspace") is not None and not isinstance(report["workspace"], dict):
        raise ValueError("workspace must be an object.")
    ids = set()
    def page_integer(value: object, path: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{path} must be a nonnegative integer.")

    for index, entry in enumerate(report["evidence"]):
        identifier = _identifier(entry["id"], f"evidence[{index}].id", 200)
        ids.add(identifier)
        _identifier(entry.get("tool"), f"evidence[{index}].tool")
        status = entry.get("status")
        if status not in STATUSES or status != entry["result"].get("status"):
            raise ValueError(f"Evidence {identifier} has inconsistent query and result statuses.")
        pagination = entry["result"].get("pagination") or {}
        continuation = pagination.get("next_page")
        if continuation is not None and not isinstance(continuation, dict):
            raise ValueError(f"Evidence {identifier} next_page must be an object or null.")
        for key in ("returned", "total_reported_by_provider"):
            if pagination.get(key) is not None:
                page_integer(pagination[key], f"{identifier}.pagination.{key}")
        if continuation and "offset" in continuation:
            page_integer(continuation["offset"], f"{identifier}.next_page.offset")
        if entry["tool"] == "bgs_features":
            page_integer(entry["arguments"].get("offset", 0), f"{identifier}.arguments.offset")
            if not isinstance(entry["result"].get("data", []), list):
                raise ValueError(f"BGS evidence {identifier} data must be an array.")
        if entry.get("pagination_followed") is not None and not isinstance(entry["pagination_followed"], bool):
            raise ValueError(f"{identifier}.pagination_followed must be a boolean.")
        if entry["result"].get("error") and status != "error":
            raise ValueError(f"Evidence {identifier} contains an error under a non-error status.")
    for collection in ("evidence", "investigations", "gaps", "groundwater"):
        if len(report[collection]) > 2000:
            raise ValueError(f"{collection} exceeds the 2000-record workspace limit.")
    for collection in ("investigations", "gaps"):
        seen = set()
        for index, item in enumerate(report[collection]):
            identifier = _identifier(item.get("id"), f"{collection}[{index}].id")
            if identifier in seen:
                raise ValueError(f"{collection} IDs must be unique.")
            seen.add(identifier)
            for ref in item.get("evidence_ids", []):
                if ref not in ids:
                    raise ValueError(f"{collection}[{index}] references missing evidence {ref!r}.")
            notes = (item.get("review") or {}).get("notes", "") if collection == "investigations" else item.get("notes", "")
            if len(notes) > 20_000:
                raise ValueError(f"{collection}[{index}] notes exceed 20000 characters.")
    for index, item in enumerate(report["groundwater"]):
        ref = item.get("evidence_id")
        if not isinstance(ref, str) or ref not in ids:
            raise ValueError(f"groundwater[{index}] references missing evidence {ref!r}.")


def derived_fields(report: dict) -> tuple[dict, str]:
    """Recompute display counts and aggregate retrieval status from retained evidence."""
    evidence = report["evidence"]
    failed = sum(entry["status"] == "error" for entry in evidence)
    incomplete = len(incomplete_entries(evidence))
    counts = {
        "investigation_count": len(report["investigations"]),
        "query_count": len(evidence),
        "failed_query_count": failed,
        "incomplete_query_count": incomplete,
        "open_gap_count": sum(item.get("status", "open") != "closed" for item in report["gaps"]),
    }
    status = (
        "error" if evidence and failed == len(evidence)
        else "partial" if failed or incomplete or report["omitted_queries"] or not evidence
        else "ok"
    )
    return counts, status
