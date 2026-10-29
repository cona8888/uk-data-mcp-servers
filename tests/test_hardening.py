"""Synthetic regression tests for report integrity and safe measurement selection."""

import copy
import json

import httpx
import pytest

from uk_data_mcp import results
from uk_data_mcp.deskstudy import _measures, build_desk_study
from uk_data_mcp.groundwater import groundwater_kind
from uk_data_mcp.json_safety import loads_json, validate_json_tree
from uk_data_mcp.reporting import prepare_report, render_html, validate_report
from uk_data_mcp.transport import HttpClient
from uk_data_mcp.webapp import create_app

PARAMETERS = (
    "effective_stress_friction_angle_deg", "undrained_shear_strength_kPa",
    "soil_stiffness_MPa", "permeability_m_per_s", "design_groundwater_level_mAOD",
    "allowable_bearing_pressure_kPa", "buried_utility_clearance_m",
)
SITE = {"latitude": 52.45, "longitude": -1.93, "nation": "England"}


def sample_report():
    return {
        "kind": "geotechnical_desk_study", "schema_version": "1.0", "status": "ok",
        "generated_at_utc": "2026-10-29T00:00:00Z",
        "project": {"project_name": "Synthetic study", "development_type": "general", "works_description": ""},
        "site": {**SITE, "radius_km": 1}, "summary": {},
        "evidence": [{
            "id": "query-001", "tool": "bgs_features", "topic": "regional_geology",
            "arguments": {}, "status": "empty",
            "result": {"status": "empty", "data": [], "pagination": {}, "provenance": [], "warnings": []},
        }],
        "investigations": [], "groundwater": [], "gaps": [],
        "warnings": ["Synthetic test only"], "omitted_queries": [],
        "design_parameters": {key: {"value": None, "reason": "Unknown"} for key in PARAMETERS},
    }


@pytest.mark.parametrize("raw", [
    b'{"x":1e400}', b'{"x":-1e400}', b'[0,{"x":1e309}]',
    b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'\xff',
    b'[' * 20_000 + b'0' + b']' * 20_000,
])
def test_unsafe_json_raises_value_error(raw):
    with pytest.raises(ValueError):
        loads_json(raw)


def test_quoted_brackets_escaped_quotes_and_finite_numbers_are_preserved():
    value = {"text": '["\\' * 1000, "number": 1e300, "zero": 0, "negative": -2.25}
    assert loads_json(json.dumps(value)) == value


def test_explicit_depth_and_node_budgets():
    assert loads_json('[[0]]', max_depth=2) == [[0]]
    with pytest.raises(ValueError):
        loads_json('[[[0]]]', max_depth=2)
    with pytest.raises(ValueError):
        loads_json('[0,1,2]', max_nodes=3)


def test_cyclic_python_workspace_is_a_validation_error_not_recursion_error():
    value = []
    value.append(value)
    with pytest.raises(ValueError):
        validate_json_tree(value)


@pytest.mark.parametrize("site", [
    {"latitude": True}, {"latitude": 999}, {"longitude": 405000},
    {"radius_km": 0}, {"radius_km": float("inf")}, {"nation": "UK"},
    {"crs": "EPSG:27700"}, {"bgs_bbox_crs84": [1, 2, 0, 3]},
])
def test_invalid_site_rejected(site):
    report = sample_report()
    report["site"].update(site)
    with pytest.raises(ValueError):
        validate_report(report)


def test_invalid_timestamp_and_blank_project_rejected():
    report = sample_report()
    report["generated_at_utc"] = "not-a-date"
    with pytest.raises(ValueError):
        validate_report(report)
    report = sample_report()
    report["project"]["project_name"] = " "
    with pytest.raises(ValueError):
        validate_report(report)


def test_summary_and_aggregate_status_are_recomputed_without_mutating_evidence():
    report = sample_report()
    entry = report["evidence"][0]
    entry["status"] = entry["result"]["status"] = "error"
    entry["result"]["error"] = {"code": "synthetic", "message": "Unavailable"}
    report["summary"] = {"query_count": 900, "failed_query_count": 0, "open_gap_count": 900}
    report["gaps"] = [{"id": "gap", "status": "closed", "notes": "Human note", "evidence_ids": ["query-001"]}]
    original = copy.deepcopy(report)
    prepared = prepare_report(report)
    assert prepared["status"] == "error"
    assert prepared["summary"]["query_count"] == 1
    assert prepared["summary"]["failed_query_count"] == 1
    assert prepared["summary"]["open_gap_count"] == 0
    assert prepared["evidence"] == original["evidence"]
    assert prepared["gaps"] == original["gaps"]
    assert report == original
    assert "Unavailable" in render_html(report)


def test_a_claimed_followed_page_without_its_response_is_still_incomplete():
    report = sample_report()
    entry = report["evidence"][0]
    entry.update(status="partial", pagination_followed=True)
    entry["result"].update(status="partial", data=[{}], pagination={"next_page": {"offset": 1}})
    prepared = prepare_report(report)
    assert prepared["status"] == "partial"
    assert prepared["summary"]["incomplete_query_count"] == 1


def test_complete_contiguous_pages_are_not_reported_as_unresolved_coverage():
    report = sample_report()
    first = report["evidence"][0]
    first.update(status="partial", pagination_followed=True,
                 arguments={"collection": "onshoreboreholeindex", "offset": 0, "limit": 1})
    first["result"].update(status="partial", data=[{"id": 1}],
                           pagination={"next_page": {"offset": 1}, "total_reported_by_provider": 2})
    final = copy.deepcopy(first)
    final.update(id="query-002", pagination_followed=False)
    final["arguments"]["offset"] = 1
    final["result"].update(data=[{"id": 2}], pagination={"next_page": None, "total_reported_by_provider": 2})
    report["evidence"].append(final)
    prepared = prepare_report(report)
    assert prepared["summary"]["incomplete_query_count"] == 0
    assert prepared["status"] == "ok"


@pytest.mark.parametrize("measure,expected", [
    ({"parameterName": "GroundwaterLevel"}, "confirmed"),
    ({"observedProperty": "groundwaterLevel"}, "confirmed"),
    ({"observedProperty": {"@id": "http://environment.data.gov.uk/def/hydrology/groundwaterLevel", "label": "Groundwater Level"}}, "confirmed"),
    ({"observedProperty": "rainfall", "parameterName": "GroundwaterLevel"}, "conflicting"),
    ({"observedProperty": "rainfall"}, "other"),
    ({"parameterName": "Flow"}, "other"),
    ({"notation": "groundwater-qualified-mAOD", "unitName": "mAOD"}, "unknown"),
    ({"label": "Groundwater series"}, "unknown"),
    ({}, "unknown"),
])
def test_series_type_is_explicit_not_guessed_from_identifier_or_unit(measure, expected):
    assert groundwater_kind(measure) == expected


def test_unknown_and_other_series_do_not_consume_confirmed_groundwater_budget():
    stations = [{"measures": [
        {"notation": "unknown"},
        {"notation": "rain", "parameterName": "Rainfall"},
        {"notation": "ground", "observedProperty": "groundwaterLevel"},
        {"notation": "ground", "parameterName": "GroundwaterLevel"},
    ]}]
    original = copy.deepcopy(stations)
    assert [identifier for identifier, _ in _measures(stations)][:1] == ["ground"]
    assert stations == original


def mock_catalogue(monkeypatch):
    # Only catalogue metadata is synthetic; workflow, adapters and envelopes are real.
    monkeypatch.setattr(results, "get_source", lambda source_id: {"id": source_id, "limitations": []})


def workflow_call(station_measures, returned_measure, calls):
    async def call(tool, arguments):
        calls.append((tool, arguments))
        data = []
        metadata = {}
        if tool == "hydrology_stations":
            data = [{"label": "Synthetic station", "measures": station_measures}]
        if tool == "hydrology_readings":
            data = [{"dateTime": "2020-01-01T00:00:00Z", "value": 12.3, "quality": "Unchecked"}]
            metadata = {"measure": returned_measure}
        return results.envelope("synthetic", data, metadata=metadata, query=arguments)
    return call


@pytest.mark.asyncio
async def test_followup_filters_before_budget_and_preserves_quality(monkeypatch):
    mock_catalogue(monkeypatch)
    calls = []
    series = [{"notation": "rain", "parameterName": "Rainfall"},
              {"notation": "unknown"},
              {"notation": "gw", "parameterName": "GroundwaterLevel"}]
    measure = {"notation": "gw", "parameterName": "GroundwaterLevel", "unitName": "mAOD"}
    report = await build_desk_study(workflow_call(series, measure, calls), **SITE, max_groundwater_measures=1)
    follows = [args["measure_id"] for tool, args in calls if tool == "hydrology_readings"]
    assert follows == ["gw"]
    assert report["groundwater"][0]["readings"][0]["quality"] == "Unchecked"
    assert any("Skipped 1" in text for text in report["omitted_queries"])
    assert report["design_parameters"]["design_groundwater_level_mAOD"]["value"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("returned", [
    {"parameterName": "Rainfall"}, {},
    {"parameterName": "GroundwaterLevel", "notation": "wrong-id"},
])
async def test_unconfirmed_returned_metadata_is_retained_but_not_presented_as_groundwater(monkeypatch, returned):
    mock_catalogue(monkeypatch)
    calls = []
    series = [{"notation": "gw", "parameterName": "GroundwaterLevel"}]
    report = await build_desk_study(workflow_call(series, returned, calls), **SITE)
    assert not report["groundwater"]
    entry = next(entry for entry in report["evidence"] if entry["tool"] == "hydrology_readings")
    assert entry["result"]["data"][0]["value"] == 12.3
    assert entry["result"]["metadata"]["measure"] == returned
    assert entry["groundwater_validation"]["status"] == "rejected"
    assert entry["status"] == entry["result"]["status"] == "ok"
    assert report["status"] == "partial" and report["omitted_queries"]


@pytest.mark.asyncio
async def test_invalid_provider_json_is_one_failed_query_not_a_lost_study(monkeypatch):
    mock_catalogue(monkeypatch)
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=b'{"value":1e400}', headers={"Content-Type": "application/json"})
    )) as upstream:
        transport = HttpClient(client=upstream, rate_interval=0)

        async def call(tool, args):
            if args.get("collection") == "bgsgeology625kbedrock":
                await transport.get_json("https://ogcapi.bgs.ac.uk/collections")
            return results.envelope("synthetic", [], query=args)

        report = await build_desk_study(call, **SITE)
    assert report["status"] == "partial"
    assert report["summary"]["failed_query_count"] == 1
    assert report["summary"]["query_count"] > 1
    assert report["evidence"][0]["result"]["error"]["code"] == "invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["latitude", "reference", "status", "overflow"])
async def test_browser_validation_rejects_invalid_imports_without_provider_calls(damage):
    async def do_not_run(arguments):
        pytest.fail("Workspace validation must never contact a provider")

    report = sample_report()
    if damage == "latitude":
        report["site"]["latitude"] = 999
    elif damage == "reference":
        report["gaps"] = [{"id": "gap", "evidence_ids": ["missing"]}]
    elif damage == "status":
        report["evidence"][0]["status"] = "error"
    body = json.dumps(report).encode()
    if damage == "overflow":
        body = body.replace(b'52.45', b'1e400')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(do_not_run)), base_url="http://127.0.0.1") as client:
        response = await client.post("/api/validate-report", content=body, headers={"content-type": "application/json"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_browser_normalization_matches_export_normalization():
    report = sample_report()
    report["summary"]["query_count"] = 999
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://127.0.0.1") as client:
        response = await client.post("/api/validate-report", json=report)
        assert response.status_code == 200
        assert response.json() == prepare_report(report)
        assert response.headers["cache-control"] == "no-store"
        rejected = await client.post("/api/validate-report", json=report, headers={"Origin": "https://other.example"})
        assert rejected.status_code == 403


@pytest.mark.parametrize("change", [
    lambda entry: entry["result"]["pagination"].update(next_page=[]),
    lambda entry: entry["result"]["pagination"].update(next_page={"offset": "1"}),
    lambda entry: entry["result"]["pagination"].update(returned=True),
    lambda entry: entry["arguments"].update(offset="0"),
    lambda entry: entry.update(pagination_followed="true"),
])
def test_malformed_pagination_is_a_validation_error(change):
    report = sample_report()
    change(report["evidence"][0])
    with pytest.raises(ValueError):
        prepare_report(report)


@pytest.mark.asyncio
async def test_compact_station_series_are_resolved_before_reading_budget(monkeypatch):
    mock_catalogue(monkeypatch)
    calls = []

    async def call(tool, arguments):
        calls.append((tool, arguments))
        if tool == "hydrology_stations":
            return results.envelope("synthetic", [{"label": "Compact station", "measures": [
                {"notation": "rain"}, {"notation": "gw"},
            ]}])
        if tool == "hydrology_readings":
            identifier = arguments["measure_id"]
            measure = {"notation": identifier, "parameterName": "Rainfall" if identifier == "rain" else "GroundwaterLevel"}
            data = [measure] if arguments.get("metadata_only") else [{"value": 12.3, "quality": "Unchecked"}]
            return results.envelope("synthetic", data, metadata={"measure": measure})
        return results.envelope("synthetic", [])

    report = await build_desk_study(call, **SITE, max_groundwater_measures=1)
    metadata = [args["measure_id"] for tool, args in calls if args.get("metadata_only")]
    readings = [args["measure_id"] for tool, args in calls if tool == "hydrology_readings" and not args.get("metadata_only")]
    assert metadata == ["rain", "gw"]
    assert readings == ["gw"]
    assert len(report["groundwater"]) == 1
    assert report["groundwater"][0]["station_name"] == "Compact station"
    assert report["groundwater"][0]["readings"][0]["quality"] == "Unchecked"
    assert report["request_limits"]["max_groundwater_metadata_queries"] == 2


@pytest.mark.asyncio
async def test_unknown_metadata_resolution_is_bounded_and_visible(monkeypatch):
    mock_catalogue(monkeypatch)
    calls = []
    series = [{"notation": f"unknown-{i}"} for i in range(20)]
    report = await build_desk_study(workflow_call(series, {}, calls), **SITE, max_groundwater_measures=1)
    assert len([args for _, args in calls if args.get("metadata_only")]) == 2
    assert not [args for tool, args in calls if tool == "hydrology_readings" and not args.get("metadata_only")]
    assert not report["groundwater"]
    assert any("Skipped 20" in text for text in report["omitted_queries"])


@pytest.mark.asyncio
async def test_metadata_only_adapter_never_fetches_readings(monkeypatch):
    from uk_data_mcp.adapters.environment import hydrology_readings

    mock_catalogue(monkeypatch)
    requested = []
    description = {"notation": "gw", "parameterName": "GroundwaterLevel", "unitName": "mAOD"}

    def handler(request):
        requested.append(str(request.url))
        assert request.url.path == "/hydrology/id/measures/gw.json"
        return httpx.Response(200, json={"items": [description]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        value = await hydrology_readings(HttpClient(client=upstream, rate_interval=0), "gw", metadata_only=True)
    assert len(requested) == 1
    assert value["data"] == [description]
    assert value["metadata"]["observation_type"] == "measure_metadata"
    assert len(value["provenance"]) == 1
