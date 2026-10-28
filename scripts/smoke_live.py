"""Opt-in low-volume live checks. Run after installation; does not call an AI model."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from uk_data_mcp.service import DataService
from uk_data_mcp.transport import HttpClient, utc_now

CHECKS = [
    ("bgs_collections", {}),
    (
        "bgs_features",
        {"collection": "onshoreboreholeindex", "bbox": [-1.94, 52.44, -1.92, 52.46], "limit": 2},
    ),
    (
        "bgs_features",
        {"collection": "bgsgeology625kbedrock", "bbox": [-1.94, 52.44, -1.92, 52.46], "limit": 2},
    ),
    (
        "bgs_features",
        {
            "collection": "bgsgeology625ksuperficial",
            "bbox": [-1.94, 52.44, -1.92, 52.46],
            "limit": 2,
        },
    ),
    (
        "bgs_features",
        {"collection": "bgsgeology625kfaults", "bbox": [-1.94, 52.44, -1.92, 52.46], "limit": 2},
    ),
    (
        "bgs_features",
        {"collection": "bgsgeology625kdykes", "bbox": [-1.94, 52.44, -1.92, 52.46], "limit": 2},
    ),
    (
        "bgs_features",
        {"collection": "agsboreholeindex", "bbox": [-1.94, 52.44, -1.92, 52.46], "limit": 2},
    ),
    (
        "bgs_features",
        {"collection": "landslideindex", "bbox": [-1.94, 52.44, -1.92, 52.46], "limit": 2},
    ),
    ("ea_stations", {"latitude": 52.45, "longitude": -1.93, "limit": 2}),
    ("ea_floods", {"latitude": 52.45, "longitude": -1.93, "limit": 2}),
    ("ea_readings", {"station_id": "4039", "limit": 3}),
    ("hydrology_stations", {"latitude": 52.45, "longitude": -1.93, "limit": 2}),
    (
        "hydrology_readings",
        {
            "measure_id": "0957e811-a4b7-45c1-8b50-2896a1598fe6-gw-dipped-i-mAOD-qualified",
            "limit": 2,
        },
    ),
    (
        "planning_entities",
        {"dataset": "local-planning-authority", "latitude": 52.45, "longitude": -1.93, "limit": 2},
    ),
    ("data_gov_search", {"query": "borehole", "limit": 1}),
    ("os_products", {"query": "roads", "limit": 2}),
    ("os_downloads", {"product_id": "OpenRoads", "limit": 2}),
    ("dft_traffic", {"year": 2024, "road_name": "A38", "limit": 2}),
]


async def run():
    rows = []
    async with HttpClient() as http:
        service = DataService(http)
        for tool, arguments in CHECKS:
            started = time.monotonic()
            result = await service.call(tool, arguments)
            rows.append(
                {
                    "tool": tool,
                    "arguments": arguments,
                    "status": result.get("status"),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "returned": result.get("pagination", {}).get("returned"),
                    "total_reported_by_provider": result.get("pagination", {}).get(
                        "total_reported_by_provider"
                    ),
                    "provenance": result.get("provenance", []),
                    "error": result.get("error"),
                }
            )
    return {
        "generated_at_utc": utc_now(),
        "kind": "public_api_live_checks",
        "checks": rows,
        "failed": sum(r["status"] == "error" for r in rows),
        "interpretation": "HTTP/API checks only. Empty or partial is not an absence-of-hazard finding.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = asyncio.run(run())
    encoded = json.dumps(value, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "checks": len(value["checks"]),
                    "failed": value["failed"],
                    "output": str(args.output),
                }
            )
        )
    else:
        print(encoded)
    raise SystemExit(1 if value["failed"] else 0)


if __name__ == "__main__":
    main()
