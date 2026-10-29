"""Meaningful desk-study boundaries; all source records below are synthetic fixtures."""

import copy

import pytest

from uk_data_mcp.deskstudy import assemble_report, build_desk_study, validate_request
from uk_data_mcp.results import envelope, error_envelope
from uk_data_mcp.transport import DataAccessError, FetchResult

SITE = {"latitude": 52.45, "longitude": -1.93, "nation": "England"}
SOURCE = {
    "onshoreboreholeindex": "bgs_boreholes",
    "agsboreholeindex": "bgs_ags",
    "landslideindex": "bgs_landslides",
    "bgsgeology625kbedrock": "bgs_geology_625k",
    "bgsgeology625ksuperficial": "bgs_geology_625k",
}


def reply(tool, arguments, data=None, *, next_page=None, total=0, status=None, metadata=None):
    source = (
        SOURCE[arguments["collection"]]
        if tool == "bgs_features"
        else {
            "ea_stations": "ea_flood",
            "ea_floods": "ea_flood",
            "hydrology_stations": "ea_hydrology",
            "hydrology_readings": "ea_hydrology",
            "planning_entities": "planning_data",
        }[tool]
    )
    return envelope(
        source,
        data or [],
        query=arguments,
        total=total,
        next_page=next_page,
        truncated=bool(next_page),
        status=status,
        metadata=metadata,
        requests=[
            FetchResult(
                data={},
                url="https://ogcapi.bgs.ac.uk/collections/synthetic/items",
                retrieved_at="2026-01-01T10:00:00Z",
                sha256="a" * 64,
            )
        ],
    )


def feature(identifier, *, geometry=None, **properties):
    return {
        "type": "Feature",
        "id": identifier,
        "properties": {"reference": f"TEST-{identifier}", **properties},
        "geometry": geometry,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        {"latitude": True},
        {"latitude": 405150},
        {"longitude": float("nan")},
        {"nation": "UK"},
        {"nation": []},
        {"project_name": " "},
        {"project_name": "a" * 121},
        {"works_description": "a" * 2001},
        {"works_description": None},
        {"development_type": "foundation_design"},
        {"radius_km": 0},
        {"radius_km": True},
        {"limit_per_source": 21},
        {"limit_per_source": True},
        {"max_borehole_pages": 6},
        {"max_borehole_pages": False},
        {"max_groundwater_measures": -1},
        {"max_groundwater_measures": True},
    ],
)
async def test_invalid_requests_never_start_provider_calls(invalid):
    async def call(*args):
        pytest.fail("Invalid request contacted a provider")

    with pytest.raises(ValueError):
        await build_desk_study(call, **{**SITE, **invalid})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nation,expected_count", [("Northern Ireland", 2), ("Scotland", 5), ("Wales", 5)]
)
async def test_nation_coverage_omits_inapplicable_connectors(nation, expected_count):
    called = []

    async def call(tool, args):
        called.append((tool, args))
        return reply(tool, args)

    report = await build_desk_study(call, **{**SITE, "nation": nation})
    assert len(called) == expected_count
    assert all(tool == "bgs_features" for tool, args in called)
    if nation == "Northern Ireland":
        assert all("625k" in args["collection"] for tool, args in called)
    assert report["status"] == "partial"
    assert report["omitted_queries"]
    assert any(gap["id"] == "omitted-sources" for gap in report["gaps"])
    assert all(parameter["value"] is None for parameter in report["design_parameters"].values())


@pytest.mark.asyncio
async def test_pages_are_bounded_and_duplicates_remain_distinct_between_indexes():
    calls = []
    centre = {"type": "Point", "coordinates": [-1.93, 52.45]}
    outside = {"type": "Point", "coordinates": [-1.915, 52.459]}

    async def call(tool, args):
        calls.append((tool, copy.deepcopy(args)))
        if args.get("collection") == "onshoreboreholeindex":
            if args["offset"] == 0:
                return reply(
                    tool,
                    args,
                    [
                        feature(
                            1.0,
                            geometry=centre,
                            year_known=1999,
                            length=12,
                            scan_url="https://api.bgs.ac.uk/log/1",
                        ),
                        feature(2, geometry=outside, length=8),
                    ],
                    next_page={"offset": 2, "collection": "do-not-use", "bbox": [0, 0, 1, 1]},
                    total=4,
                )
            return reply(
                tool,
                args,
                [
                    feature(2, geometry=outside),
                    feature(3, easting=405150, northing=282960, precision="± 10 METRES"),
                ],
                total=4,
                status="partial",
            )
        if args.get("collection") == "agsboreholeindex":
            return reply(tool, args, [feature(1, geometry=centre, length=14)], total=1)
        return reply(tool, args)

    report = await build_desk_study(call, **SITE, limit_per_source=2, max_borehole_pages=2)
    records = report["investigations"]
    assert len(records) == 4
    sobi = [record for record in records if record["collection"] == "onshoreboreholeindex"]
    assert sobi[1]["duplicate_records"] == 1
    assert len(sobi[1]["evidence_ids"]) == 2
    assert sobi[0]["distance_m"] == 0
    assert sobi[0]["depth_m"] == 12
    assert sobi[0]["year"] == "1999"
    assert sobi[1]["within_radius"] is False
    assert sobi[2]["latitude"] is None and sobi[2]["distance_m"] is None
    assert sobi[2]["provider_properties"]["easting"] == 405150
    assert sobi[2]["position_precision"] == "± 10 METRES"
    assert report["summary"]["incomplete_query_count"] == 0
    assert all(record["review"] == {"status": "unreviewed", "notes": ""} for record in records)
    index_calls = [args for tool, args in calls if args.get("collection") == "onshoreboreholeindex"]
    assert [args["offset"] for args in index_calls] == [0, 2]
    assert index_calls[1]["collection"] == "onshoreboreholeindex"
    assert index_calls[1]["bbox"] == index_calls[0]["bbox"]


@pytest.mark.asyncio
async def test_page_budget_is_visible_as_unresolved_coverage():
    offsets = []

    async def call(tool, args):
        if args.get("collection") == "onshoreboreholeindex":
            offsets.append(args["offset"])
            return reply(tool, args, [feature(1)], next_page={"offset": 1}, total=5)
        return reply(tool, args)

    report = await build_desk_study(call, **SITE, max_borehole_pages=1)
    assert offsets == [0]
    assert report["summary"]["incomplete_query_count"] == 1
    gap = next(g for g in report["gaps"] if g["id"].startswith("coverage-"))
    assert "limit" in gap["reason"]
    assert report["status"] == "partial"


@pytest.mark.asyncio
async def test_stalled_continuation_and_empty_partial_do_not_become_complete():
    async def call(tool, args):
        if args.get("collection") == "onshoreboreholeindex":
            return reply(tool, args, [feature(1)], next_page={"offset": 0}, total=10)
        if args.get("collection") == "agsboreholeindex":
            return reply(tool, args, [], total=3, status="partial")
        return reply(tool, args)

    report = await build_desk_study(call, **SITE)
    assert report["summary"]["incomplete_query_count"] == 2
    assert len([g for g in report["gaps"] if g["id"].startswith("coverage-")]) == 2
    assert report["status"] == "partial"


@pytest.mark.asyncio
async def test_provider_failure_retains_success_and_has_an_explicit_gap():
    async def call(tool, args):
        if args.get("collection") == "bgsgeology625kbedrock":
            raise DataAccessError("Synthetic provider outage", code="network_error")
        if args.get("collection") == "onshoreboreholeindex":
            return reply(tool, args, [feature(99)], total=1)
        return reply(tool, args)

    report = await build_desk_study(call, **SITE)
    assert report["status"] == "partial"
    assert report["summary"]["failed_query_count"] == 1
    assert report["summary"]["investigation_count"] == 1
    failed = next(e for e in report["evidence"] if e["status"] == "error")
    assert failed["result"]["error"]["code"] == "network_error"
    assert any(failed["id"] in gap["evidence_ids"] for gap in report["gaps"])
    assert report["investigations"][0]["reference"] == "TEST-99"


@pytest.mark.asyncio
async def test_all_provider_failures_report_error_without_inventing_records():
    async def call(tool, args):
        return error_envelope("bgs_geology_625k", DataAccessError("Synthetic failure"), args)

    report = await build_desk_study(call, **SITE)
    assert report["status"] == "error"
    assert report["summary"]["failed_query_count"] == report["summary"]["query_count"]
    assert not report["investigations"]
    assert all(parameter["value"] is None for parameter in report["design_parameters"].values())


@pytest.mark.asyncio
async def test_groundwater_only_follows_discovered_safe_ids_and_preserves_observation_quality():
    called = []
    readings = [
        {"dateTime": "2020-01-01T09:00:00Z", "value": 12.3, "quality": {"label": "Unchecked"}}
    ]
    measure = {"unitName": "mAOD", "label": "Synthetic groundwater elevation", "parameterName": "GroundwaterLevel"}
    stations = [
        {
            "label": "Synthetic station",
            "measures": [
                {"@id": "https://environment.data.gov.uk/hydrology/id/measures/test-gw"},
                {"@id": "http://environment.data.gov.uk/hydrology/id/measures/test-gw"},
                {"@id": "https://environment.data.gov.uk/hydrology/id/measures/second-gw"},
                {"@id": "https://evil.example/hydrology/id/measures/ignore-me"},
                {"@id": "https://environment.data.gov.uk:invalid/hydrology/id/measures/ignore-me"},
                {"@id": "https://environment.data.gov.uk/hydrology/id/measures/../private"},
            ],
        }
    ]

    for station in stations:
        for series in station["measures"]:
            series["parameterName"] = "GroundwaterLevel"

    async def call(tool, args):
        called.append((tool, args))
        if tool == "hydrology_stations":
            return reply(tool, args, stations, total=1)
        if tool == "hydrology_readings":
            return reply(tool, args, readings, total=1, metadata={"measure": measure})
        return reply(tool, args)

    report = await build_desk_study(call, **SITE, max_groundwater_measures=1)
    follows = [args for tool, args in called if tool == "hydrology_readings"]
    assert follows == [{"measure_id": "test-gw", "limit": 10}]
    assert report["groundwater"][0]["station_name"] == "Synthetic station"
    assert report["groundwater"][0]["readings"] == readings
    assert report["groundwater"][0]["measure"] == measure
    assert any("1 of 2" in omission for omission in report["omitted_queries"])
    reading_evidence = next(e for e in report["evidence"] if e["tool"] == "hydrology_readings")
    assert reading_evidence["result"]["provenance"][0]["response_sha256"] == "a" * 64
    assert report["design_parameters"]["design_groundwater_level_mAOD"]["value"] is None


@pytest.mark.asyncio
async def test_zero_groundwater_budget_is_an_explicit_omission():
    async def call(tool, args):
        assert tool != "hydrology_readings"
        if tool == "hydrology_stations":
            return reply(tool, args, [{"measures": {"notation": "safe-gw", "parameterName": "GroundwaterLevel"}}])
        return reply(tool, args)

    report = await build_desk_study(call, **SITE, max_groundwater_measures=0)
    assert any("0 of 1" in omission for omission in report["omitted_queries"])


def test_dated_snapshot_preserves_source_time_and_copies_mutable_evidence():
    args = {"collection": "onshoreboreholeindex", "offset": 0}
    evidence = [
        {
            "id": "query-001",
            "topic": "historic_investigations",
            "tool": "bgs_features",
            "arguments": args,
            "status": "ok",
            "result": reply("bgs_features", args, [feature(1)], total=1),
        }
    ]
    report = assemble_report(
        evidence, {**SITE, "development_type": "basement"}, generated_at="2026-02-01T00:00:00Z"
    )
    assert report["generated_at_utc"] == "2026-02-01T00:00:00Z"
    assert report["evidence"][0]["result"]["retrieved_at_utc"] == "2026-01-01T10:00:00Z"
    assert any(gap["id"] == "excavation-scope" for gap in report["gaps"])
    report["evidence"][0]["result"]["data"].clear()
    assert evidence[0]["result"]["data"]


def test_no_evidence_means_visible_gap_and_unknown_values():
    report = assemble_report([], SITE)
    assert report["status"] == "partial"
    assert any(gap["id"] == "omitted-sources" for gap in report["gaps"])
    assert "No source evidence" in report["omitted_queries"][0]
    assert report["summary"]["open_gap_count"] == len(report["gaps"])


def test_request_defaults_are_normalized_for_all_entry_points():
    request = validate_request(**SITE, project_name="  Test project  ")
    assert request["project_name"] == "Test project"
    assert request["max_borehole_pages"] == 3
    assert len(request["bgs_bbox_crs84"]) == 4


@pytest.mark.parametrize("feature_has_id", [True, False])
def test_bgs_ags_field_names_map_to_candidates_without_reinterpreting_bng(feature_has_id):
    # The property names match the BGS layer; every fixture value is synthetic.
    properties = {
        "bgs_loca_id": "SYNTHETIC-BGS-LOCATION-1",
        "id": "SYNTHETIC-BGS-LOCATION-1",
        "loca_id": "SYN-BH01",
        "proj_name": "Synthetic AGS project",
        "x": 405150.0,
        "y": 282960.0,
        "loca_fdep": 6.5,
        "ags_log_url": "https://webservices.bgs.ac.uk/GWBV/viewborehole?loca_id=SYNTHETIC",
        "dad_item_url": "http://www.bgs.ac.uk/services/ngdc/accessions/index.html#itemSYNTHETIC",
    }
    record = {"type": "Feature", "properties": properties, "geometry": None}
    if feature_has_id:
        record["id"] = "SYNTHETIC-BGS-LOCATION-1"
    args = {"collection": "agsboreholeindex", "offset": 0}
    evidence = [
        {
            "id": "query-001",
            "topic": "historic_investigations",
            "tool": "bgs_features",
            "arguments": args,
            "status": "ok",
            "result": reply("bgs_features", args, [record], total=1),
        }
    ]
    candidate = assemble_report(evidence, SITE)["investigations"][0]
    assert candidate["provider_id"] == "SYNTHETIC-BGS-LOCATION-1"
    assert candidate["reference"] == "SYN-BH01"
    assert candidate["name"] == "Synthetic AGS project"
    assert candidate["depth_m"] == 6.5
    assert candidate["latitude"] is None and candidate["distance_m"] is None
    assert candidate["provider_properties"] == properties
    assert candidate["year"] is None and candidate["position_precision"] is None
    assert {link["label"] for link in candidate["links"]} == {"AGS log", "BGS accession"}


def test_ags_final_depth_alias_is_not_assigned_to_other_collections():
    args = {"collection": "onshoreboreholeindex", "offset": 0}
    evidence = [
        {
            "id": "query-001",
            "topic": "historic_investigations",
            "tool": "bgs_features",
            "arguments": args,
            "status": "ok",
            "result": reply("bgs_features", args, [feature(1, loca_fdep=9.0)], total=1),
        }
    ]
    assert assemble_report(evidence, SITE)["investigations"][0]["depth_m"] is None


def test_explicit_depth_precedes_ags_alias_when_length_is_null():
    args = {"collection": "agsboreholeindex", "offset": 0}
    evidence = [
        {
            "id": "query-001",
            "topic": "historic_investigations",
            "tool": "bgs_features",
            "arguments": args,
            "status": "ok",
            "result": reply(
                "bgs_features", args, [feature(1, length=None, depth=7.0, loca_fdep=9.0)], total=1
            ),
        }
    ]
    assert assemble_report(evidence, SITE)["investigations"][0]["depth_m"] == 7.0
