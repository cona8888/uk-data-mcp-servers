"""Reviewed provider catalogue, with implemented adapters distinguished from a roadmap."""

import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def all_sources() -> list[dict]:
    return json.loads(files("uk_data_mcp").joinpath("sources.json").read_text(encoding="utf-8"))


def get_source(source_id: str) -> dict:
    for source in all_sources():
        if source["id"] == source_id:
            # Keep the cached catalogue immutable to callers.
            return json.loads(json.dumps(source))
    raise ValueError(f"Unknown source ID: {source_id}")


def list_sources(query: str = "", implemented_only: bool = False) -> dict:
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError("query must be at most 200 characters.")
    found = [
        s
        for s in all_sources()
        if (not implemented_only or s["status"] == "implemented")
        and query.lower() in json.dumps(s).lower()
    ]
    return {
        "schema_version": "1.0",
        "kind": "reviewed_source_registry",
        "reviewed_on": "2026-10-27",
        "count": len(found),
        "sources": found,
        "warnings": [
            "This is a curated, incomplete catalogue. A listed provider is not necessarily an implemented connector.",
            "Review each dataset's current licence and coverage; provider access is not a blanket reuse permission.",
        ],
    }
