"""Export tests use synthetic records, never invented field investigations."""

import copy
import csv
import io

import pytest

from uk_data_mcp.reporting import export_csv, render_html, render_markdown, validate_report


@pytest.fixture
def report():
    parameters = (
        "effective_stress_friction_angle_deg", "undrained_shear_strength_kPa",
        "soil_stiffness_MPa", "permeability_m_per_s", "design_groundwater_level_mAOD",
        "allowable_bearing_pressure_kPa", "buried_utility_clearance_m",
    )
    return {
        "schema_version": "1.0", "kind": "geotechnical_desk_study", "status": "partial",
        "generated_at_utc": "2026-10-28T12:00:00Z",
        "project": {
            "project_name": "Synthetic test project", "development_type": "basement",
            "works_description": "Example scope only",
        },
        "site": {
            "latitude": 52.45, "longitude": -1.93, "nation": "England", "radius_km": 1,
            "bgs_bbox_crs84": [-1.94, 52.44, -1.92, 52.46],
        },
        "summary": {"investigation_count": 1, "query_count": 1},
        "evidence": [{
            "id": "query-001", "topic": "Synthetic index", "tool": "bgs_features",
            "arguments": {"collection": "onshoreboreholeindex"}, "status": "partial",
            "result": {
                "status": "partial", "retrieved_at_utc": "2026-10-28T11:59:00Z",
                "source": {
                    "name": "Synthetic source", "provider": "Test provider", "coverage": ["GB"],
                    "licence": {"name": "Test terms", "url": "https://example.test/terms", "scope": "Test scope"},
                    "attribution": "Synthetic attribution", "documentation_url": "https://example.test/docs",
                },
                "data": [{"properties": {"date_updated": "2001-01-01", "reference": "TEST-1"}}],
                "query": {"offset": 0},
                "pagination": {"returned": 1, "truncated": True, "next_page": {"offset": 1}},
                "metadata": {"observation_type": "index_records"},
                "provenance": [{
                    "url": "https://example.test/query?limit=1&offset=0",
                    "retrieved_at_utc": "2026-10-28T11:59:00Z",
                    "response_sha256": "abc123", "http_status": 200,
                }],
                "warnings": ["Synthetic source warning"],
            },
        }],
        "investigations": [{
            "id": "sobi:1", "collection": "onshoreboreholeindex", "reference": "TEST-1",
            "name": "Synthetic index candidate", "depth_m": None, "year": None,
            "updated_at": "2001-01-01", "position_precision": "Unknown",
            "latitude": None, "longitude": -1.93, "distance_m": None, "within_radius": None,
            "links": [{"label": "Original record", "url": "https://example.test/log/1"}],
            "evidence_ids": ["query-001"], "review": {"status": "needs_review", "notes": "Obtain original log"},
            "provider_properties": {"easting": 400000, "northing": 280000},
        }],
        "groundwater": [{
            "station_name": "Synthetic monitoring station", "measure_id": "TEST-mAOD",
            "evidence_id": "query-001", "status": "ok",
            "measure": {"unitName": "mAOD", "datum": "Ordnance Datum"},
            "readings": [{"dateTime": "2020-01-01T09:00:00Z", "value": 115.2, "quality": "Unchecked"}],
            "warnings": ["Observation is older than retrieval time"],
        }],
        "gaps": [{
            "id": "gap-1", "priority": "high", "topic": "investigation_relevance",
            "title": "Review historic evidence", "reason": "Original log not reviewed",
            "actions": ["Obtain and review the original log"], "evidence_ids": ["query-001"],
            "status": "in_progress", "notes": "Requested from archive",
        }],
        "design_parameters": {key: {"value": None, "reason": "Not established by source queries"} for key in parameters},
        "warnings": ["Bounding box candidates require relevance review"],
        "omitted_queries": ["Historic site activities require separate records"],
    }


def test_html_retains_source_dates_units_quality_and_human_decisions(report):
    original = copy.deepcopy(report)
    output = render_html(report)
    for text in (
        "2026-10-28T12:00:00Z", "2001-01-01", "2020-01-01T09:00:00Z", "mAOD",
        "Unchecked", "needs_review", "Obtain original log", "in_progress",
        "Requested from archive", "Synthetic attribution", "Test scope", "abc123",
        "query-001", "Not established by source queries", "Unknown",
    ):
        assert text in output
    assert '<a href="#source-1">query-001</a>' in output
    assert "not confirmed site strata" in output
    assert "not site safety or suitability" in output
    assert "<script" not in output.lower()
    assert report == original


def test_html_escapes_untrusted_fields_and_rejects_executable_links(report):
    payload = '<img src=x onerror="alert(1)"><script>alert(1)</script>'
    report["project"]["project_name"] = payload
    report["investigations"][0]["review"]["notes"] = payload
    report["investigations"][0]["links"] = [
        {"label": payload, "url": "javascript:alert(1)"},
        {"label": "unsafe data", "url": "data:text/html,<script>bad</script>"},
        {"label": "credential URL", "url": "https://user:secret@example.test/private"},
    ]
    report["evidence"][0]["result"]["source"]["licence"]["url"] = "javascript:alert(1)"
    output = render_html(report)
    assert "<img src=x" not in output
    assert "<script>" not in output
    assert "&lt;img" in output
    assert 'href="javascript:' not in output
    assert 'href="data:' not in output
    assert 'href="https://user:secret' not in output
    assert 'href="https://example.test/query?limit=1&amp;offset=0"' in output


def test_export_preserves_failed_query_and_does_not_invent_depth_or_parameters(report):
    entry = report["evidence"][0]
    entry["status"] = entry["result"]["status"] = "error"
    entry["result"]["error"] = {"code": "network_error", "message": "Connection failed"}
    entry["result"]["data"] = []
    output = render_html(report)
    assert "Connection failed" in output
    assert "network_error" in output
    assert "effective_stress_friction_angle_deg" not in output  # human-readable label
    assert "Effective stress friction angle (degrees)" in output
    rows = list(csv.DictReader(io.StringIO(export_csv(report))))
    assert rows[0]["depth_m"] == ""
    assert rows[0]["year"] == ""
    assert rows[0]["latitude"] == ""
    assert rows[0]["longitude"] == "-1.93"


@pytest.mark.parametrize("payload", ["=1+1", "+SUM(A1)", "-1+2", "@SUM(A1)", "\t=1", "\r=1", "  =1"])
def test_csv_guards_formula_strings_and_quotes_embedded_newlines(report, payload):
    report["investigations"][0]["reference"] = payload
    report["investigations"][0]["review"]["notes"] = 'Line one, "quoted"\nLine two'
    rows = list(csv.DictReader(io.StringIO(export_csv(report))))
    assert rows[0]["reference"] == "'" + payload
    assert rows[0]["review_notes"] == 'Line one, "quoted"\nLine two'
    report["gaps"][0]["notes"] = payload
    assert list(csv.DictReader(io.StringIO(export_csv(report, "gaps"))))[0]["notes"] == "'" + payload


def test_markdown_retains_audit_data_and_escapes_markup(report):
    report["project"]["project_name"] = "[fake](javascript:alert(1)) <script>bad</script>"
    report["evidence"][0]["result"]["data"][0]["note"] = "```\n<script>bad</script>"
    output = render_markdown(report)
    assert "\\[fake\\]" in output
    assert "&lt;script&gt;" in output
    assert "\\u0060\\u0060\\u0060" in output
    assert "2001-01-01" in output
    assert "source_sha256" not in output
    assert "response_sha256" in output
    assert "needs\\_review" in output


@pytest.mark.parametrize("change", [
    lambda report: report.update(kind="arbitrary_json"),
    lambda report: report.update(status={"bad": True}),
    lambda report: report.update(evidence=["not-an-object"]),
    lambda report: report["evidence"][0]["result"].update(source=[]),
    lambda report: report["investigations"][0].update(review="not-an-object"),
    lambda report: report["investigations"][0]["review"].update(status=[]),
    lambda report: report["gaps"][0].update(actions="not-an-array"),
    lambda report: report["groundwater"][0].update(readings=["not-an-object"]),
    lambda report: report["groundwater"][0].update(evidence_id={"bad": True}),
    lambda report: report["site"].update(latitude=float("nan")),
    lambda report: report["design_parameters"].pop("soil_stiffness_MPa"),
    lambda report: report["design_parameters"]["soil_stiffness_MPa"].update(value=20),
    lambda report: report["evidence"].append(copy.deepcopy(report["evidence"][0])),
])
def test_malformed_or_design_altering_reports_raise_clear_value_errors(report, change):
    change(report)
    with pytest.raises(ValueError):
        validate_report(report)


def test_optional_null_fields_render_as_unknown_and_invalid_csv_kind_is_clear(report):
    report["investigations"][0]["review"] = None
    report["groundwater"][0]["measure"] = None
    report["evidence"][0]["result"]["source"] = None
    assert "Unknown" in render_html(report)
    with pytest.raises(ValueError, match="kind"):
        export_csv(report, "anything")


def test_oversized_import_is_rejected(report):
    report["project"]["works_description"] = "x" * 10_000_000
    with pytest.raises(ValueError, match="10 MB"):
        validate_report(report)
