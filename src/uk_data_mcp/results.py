"""Evidence envelopes prevent provider failures being confused with absent hazards."""

from .registry import get_source
from .transport import DataAccessError, FetchResult, utc_now


def envelope(
    source_id: str,
    data: list | dict,
    *,
    requests: list[FetchResult] | None = None,
    query: dict | None = None,
    warnings: list[str] | None = None,
    total: int | None = None,
    truncated: bool = False,
    next_page: dict | None = None,
    metadata: dict | None = None,
    status: str | None = None,
) -> dict:
    requests = requests or []
    source = get_source(source_id)
    status = status or ("partial" if truncated else "ok" if data else "empty")
    if status not in {"ok", "partial", "empty", "error"}:
        raise ValueError("Invalid envelope status")
    return {
        "schema_version": "1.0",
        "source_id": source_id,
        "status": status,
        "source": source,
        "retrieved_at_utc": requests[-1].retrieved_at if requests else utc_now(),
        "query": query or {},
        "data": data,
        "pagination": {
            "returned": len(data),
            "total_reported_by_provider": total,
            "truncated": truncated,
            "next_page": next_page,
        },
        "provenance": [r.provenance() for r in requests],
        "metadata": metadata or {},
        "warnings": list(
            dict.fromkeys(
                [
                    *(warnings or []),
                    *source.get("limitations", []),
                    "An empty result is not evidence that a hazard, asset or geological feature is absent.",
                    "Retrieved timestamps describe access time; use record observation dates for freshness.",
                ]
            )
        ),
        "use": "Data discovery and preliminary screening; does not certify site safety or establish design parameters.",
    }


def error_envelope(
    source_id: str, error: DataAccessError | ValueError, query: dict | None = None
) -> dict:
    result = envelope(source_id, [], query=query, status="error")
    result["error"] = {
        "code": getattr(error, "code", "invalid_input"),
        "message": str(error),
        "url": getattr(error, "url", None),
        "http_status": getattr(error, "status_code", None),
    }
    result["pagination"]["returned"] = 0
    return result
