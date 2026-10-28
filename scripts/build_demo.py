"""Repackage the dated public Birmingham snapshot without making network calls."""

import json
from pathlib import Path

from uk_data_mcp.deskstudy import assemble_report


def main():
    root = Path(__file__).resolve().parents[1]
    snapshot = json.loads(
        (root / "examples" / "birmingham_evidence.json").read_text(encoding="utf-8")
    )
    evidence = []
    topics = {
        "bgsgeology625kbedrock": ("regional_geology", "bgs_features"),
        "bgsgeology625ksuperficial": ("regional_geology", "bgs_features"),
        "onshoreboreholeindex": ("historic_investigations", "bgs_features"),
        "landslideindex": ("recorded_landslides", "bgs_features"),
        "ea_stations": ("surface_water_stations", "ea_stations"),
        "ea_floods": ("current_flood_warnings", "ea_floods"),
        "hydrology_stations": ("groundwater_stations", "hydrology_stations"),
        "planning_authority": ("planning_authority", "planning_entities"),
    }
    for name, result in snapshot["results"].items():
        topic, tool = topics[name]
        evidence.append(
            {
                "id": f"query-{len(evidence) + 1:03d}",
                "topic": topic,
                "tool": tool,
                "arguments": result["query"],
                "status": result["status"],
                "result": result,
            }
        )
    result = snapshot["followup_groundwater"]
    evidence.append(
        {
            "id": f"query-{len(evidence) + 1:03d}",
            "topic": "groundwater_readings",
            "tool": "hydrology_readings",
            "arguments": result["query"],
            "status": result["status"],
            "result": result,
        }
    )
    report = assemble_report(
        evidence,
        {
            "latitude": snapshot["site"]["latitude"],
            "longitude": snapshot["site"]["longitude"],
            "nation": "England",
            "radius_km": snapshot["site"]["radius_km"],
            "project_name": "Birmingham public demonstration",
            "development_type": "general",
            "works_description": "Dated public-data example; no defined construction site or proposed works.",
            "limit_per_source": 3,
        },
        omitted_queries=[
            "The original dated snapshot did not query the AGS index or fetch additional SOBI pages. "
            "Original logs and AGS files have not been downloaded or reviewed."
        ],
        generated_at=snapshot["generated_at_utc"],
    )
    report["demo"] = True
    report["demo_description"] = (
        "Public Birmingham evidence retrieved on 27 October 2026, repackaged for demonstration. "
        "Source dates and missing evidence are preserved; this example has not been refreshed."
    )
    target = root / "src" / "uk_data_mcp" / "demo_desk_study.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(target.relative_to(root)), "summary": report["summary"]}))


if __name__ == "__main__":
    main()
