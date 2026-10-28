"""Escaped, standalone exports of a desk study and its human review decisions."""

from __future__ import annotations

import csv
import io
import json
import math
from html import escape
from typing import Any
from urllib.parse import quote, urlsplit

_DESIGN_PARAMETERS = {
    "effective_stress_friction_angle_deg": "Effective stress friction angle (degrees)",
    "undrained_shear_strength_kPa": "Undrained shear strength (kPa)",
    "soil_stiffness_MPa": "Soil stiffness (MPa)",
    "permeability_m_per_s": "Permeability (m/s)",
    "design_groundwater_level_mAOD": "Design groundwater level (mAOD)",
    "allowable_bearing_pressure_kPa": "Allowable bearing pressure (kPa)",
    "buried_utility_clearance_m": "Buried utility clearance (m)",
}
_MAX_REPORT_BYTES = 10_000_000


def _mapping(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object.")
    return value


def _records(value: Any, path: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must be an array of objects.")
    if len(value) > 10_000:
        raise ValueError(f"{path} contains too many records.")
    return value


def _strings(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{path} must be an array of strings.")
    return value


def validate_report(report: Any) -> dict:
    """Validate imported/exported report structure without filling in missing evidence.

    Review statuses and notes are user decisions. They do not allow this exporter
    to establish any design parameter, even if a saved JSON file was hand-edited.
    The returned object is the original, unmodified report.
    """
    _mapping(report, "Report")
    if report.get("kind") != "geotechnical_desk_study" or report.get("schema_version") != "1.0":
        raise ValueError("Expected a geotechnical_desk_study report with schema_version 1.0.")
    if report.get("status") not in ("ok", "partial", "error"):
        raise ValueError("Report status must be ok, partial or error.")
    if not isinstance(report.get("generated_at_utc"), str):
        raise ValueError("Report generated_at_utc must be a string.")
    project = _mapping(report.get("project"), "project")
    if not isinstance(project.get("project_name"), str):
        raise ValueError("project.project_name must be a string.")
    _mapping(report.get("site"), "site")
    _mapping(report.get("summary"), "summary")
    _strings(report.get("warnings"), "warnings")
    _strings(report.get("omitted_queries"), "omitted_queries")
    seen_evidence_ids = set()
    for index, evidence in enumerate(_records(report.get("evidence"), "evidence")):
        path = f"evidence[{index}]"
        if not isinstance(evidence.get("id"), str):
            raise ValueError(f"{path}.id must be a string.")
        if evidence["id"] in seen_evidence_ids:
            raise ValueError("Evidence IDs must be unique for unambiguous source references.")
        seen_evidence_ids.add(evidence["id"])
        result = _mapping(evidence.get("result"), f"{path}.result")
        _mapping(evidence.get("arguments", {}), f"{path}.arguments")
        for key in ("source", "query", "pagination", "metadata", "error"):
            if result.get(key) is not None:
                _mapping(result[key], f"{path}.result.{key}")
        source = result.get("source") or {}
        if source.get("licence") is not None:
            _mapping(source["licence"], f"{path}.result.source.licence")
        _records(result.get("provenance", []), f"{path}.result.provenance")
        _strings(result.get("warnings", []), f"{path}.result.warnings")
        if not isinstance(result.get("data", []), (list, dict)):
            raise ValueError(f"{path}.result.data must be an array or object.")
    for index, investigation in enumerate(
        _records(report.get("investigations"), "investigations")
    ):
        path = f"investigations[{index}]"
        if investigation.get("review") is not None:
            review = _mapping(investigation["review"], f"{path}.review")
            if review.get("status", "unreviewed") not in (
                "unreviewed", "relevant", "not_relevant", "needs_review"
            ):
                raise ValueError(f"{path}.review.status is not a supported human review status.")
            if not isinstance(review.get("notes", ""), str):
                raise ValueError(f"{path}.review.notes must be a string.")
        _records(investigation.get("links", []), f"{path}.links")
        _strings(investigation.get("evidence_ids", []), f"{path}.evidence_ids")
    for index, gap in enumerate(_records(report.get("gaps"), "gaps")):
        path = f"gaps[{index}]"
        if gap.get("status", "open") not in ("open", "in_progress", "closed"):
            raise ValueError(f"{path}.status is not a supported review task status.")
        if not isinstance(gap.get("notes", ""), str):
            raise ValueError(f"{path}.notes must be a string.")
        _strings(gap.get("actions", []), f"{path}.actions")
        _strings(gap.get("evidence_ids", []), f"{path}.evidence_ids")
    for index, groundwater in enumerate(_records(report.get("groundwater"), "groundwater")):
        path = f"groundwater[{index}]"
        if groundwater.get("measure") is not None:
            _mapping(groundwater["measure"], f"{path}.measure")
        if groundwater.get("evidence_id") is not None and not isinstance(
            groundwater["evidence_id"], str
        ):
            raise ValueError(f"{path}.evidence_id must be a string or null.")
        _records(groundwater.get("readings", []), f"{path}.readings")
        _strings(groundwater.get("warnings", []), f"{path}.warnings")
    parameters = _mapping(report.get("design_parameters"), "design_parameters")
    if set(_DESIGN_PARAMETERS) - set(parameters):
        raise ValueError("design_parameters must retain all seven unknown design parameters.")
    for key, parameter in parameters.items():
        _mapping(parameter, f"design_parameters.{key}")
        if parameter.get("value") is not None:
            raise ValueError("Design parameters must remain unknown in this preliminary report.")
    try:
        encoded = json.dumps(report, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ValueError("Report must contain finite, serializable JSON data.") from exc
    if len(encoded) > _MAX_REPORT_BYTES:
        raise ValueError("Report exceeds the 10 MB export limit.")
    return report


def _text(value: Any, unknown: str = "Unknown") -> str:
    if value is None or value == "":
        return unknown
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _html(value: Any, unknown: str = "Unknown") -> str:
    return escape(_text(value, unknown), quote=True)


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)


def _safe_url(value: Any) -> str | None:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        parsed.port
    except ValueError:
        return None
    return value


def _link(url: Any, label: Any = None) -> str:
    safe = _safe_url(url)
    label = _html(label if label is not None else url)
    if not safe:
        return label
    return f'<a href="{escape(safe, quote=True)}" rel="noopener noreferrer">{label}</a>'


def _list_html(items: list, *, empty: str = "None recorded.") -> str:
    if not items:
        return f"<p>{escape(empty)}</p>"
    return "<ul>" + "".join(f"<li>{_html(item)}</li>" for item in items) + "</ul>"


def _refs(ids: list, anchors: dict[str, str]) -> str:
    return ", ".join(
        f'<a href="#{anchors[identifier]}">{_html(identifier)}</a>'
        if isinstance(identifier, str) and identifier in anchors else _html(identifier)
        for identifier in ids
    ) or "No linked evidence"


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f"<p>{escape(empty)}</p>"
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + "".join(f'<th scope="col">{escape(header)}</th>' for header in headers)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        + "</tbody></table></div>"
    )


def _badge(value: Any) -> str:
    return f'<span class="badge">{_html(value)}</span>'


def _date_fields(record: dict) -> dict:
    return {
        key: value for key, value in record.items()
        if any(word in key.lower() for word in ("date", "year", "time"))
    }


_STYLE = """
:root{color-scheme:light;font:15px/1.55 system-ui,sans-serif;color:#193c36;background:#e9eeeb}
*{box-sizing:border-box}body{margin:0}main{max-width:1160px;margin:32px auto;background:#fff;
padding:46px 54px;box-shadow:0 4px 30px #12352a12}header{border-bottom:3px solid #214d43;
padding-bottom:26px;margin-bottom:30px}.eyebrow{font-size:12px;text-transform:uppercase;
letter-spacing:.14em;color:#5c756c}h1{font-size:32px;line-height:1.2;margin:12px 0}
h2{margin-top:36px;font-size:22px}h3{font-size:17px;margin-bottom:8px}p{margin:8px 0}
a{color:#12645b;text-decoration-thickness:1px;text-underline-offset:3px;overflow-wrap:anywhere}
.muted{color:#63746e}.notice{background:#fff5df;border-left:4px solid #b98627;padding:14px 18px}
.badge{display:inline-block;border:1px solid #b6c8bf;border-radius:4px;padding:1px 7px;
font-size:12px;white-space:nowrap}.table-wrap{overflow-x:auto}table{border-collapse:collapse;
width:100%;margin:14px 0;font-size:13px}th{text-align:left;background:#edf3ef;font-weight:650}
td,th{padding:10px 11px;border-bottom:1px solid #dce4df;vertical-align:top}td{overflow-wrap:anywhere}
dl{display:grid;grid-template-columns:minmax(130px,200px) 1fr;gap:7px 16px}dt{font-weight:650}
dd{margin:0;overflow-wrap:anywhere}.source,.gap{border:1px solid #dce4df;border-radius:6px;
padding:18px 22px;margin:14px 0;break-inside:avoid}pre{font-size:11px;line-height:1.45;
white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f3;padding:12px;border-radius:4px}
summary{cursor:pointer;font-weight:650}details{margin:12px 0}.notes{white-space:pre-wrap}
footer{border-top:1px solid #dce4df;margin-top:32px;padding-top:18px;font-size:12px}
@media(max-width:700px){main{margin:0;padding:24px 18px}h1{font-size:27px}dl{display:block}
dd{margin-bottom:10px}.source,.gap{padding:12px}}
@media print{body{background:white}main{max-width:none;margin:0;padding:0;box-shadow:none}
a{color:inherit}.table-wrap{overflow:visible}thead{display:table-header-group}
tr{break-inside:avoid}h2,h3{break-after:avoid}.raw{display:none}.source{break-inside:auto}
@page{margin:18mm}}
"""


def render_html(report: dict) -> str:
    """Return a printable HTML document with no scripts or remote assets."""
    validate_report(report)
    project, site = report["project"], report["site"]
    anchors = {item["id"]: f"source-{index + 1}" for index, item in enumerate(report["evidence"])}
    parts = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_html(project['project_name'])} — Geotechnical desk study</title>",
        f"<style>{_STYLE}</style></head><body><main><header>",
        '<p class="eyebrow">Geotechnical desk study and GI gap planner</p>',
        f"<h1>{_html(project['project_name'])}</h1>",
        f"<p>Report generated: {_html(report['generated_at_utc'])}</p>",
        f"<p>Query execution: {_badge(report['status'])}</p></header>",
        '<p class="notice">Preliminary evidence and human review decisions. Query status describes '
        "retrieval and completeness, not site safety or suitability. Empty searches do not establish "
        "absence of hazards. Closed GI tasks record a review decision, not engineering clearance.</p>",
        "<h2>Project scope</h2><dl>",
    ]
    for label, value in (
        ("Development", project.get("development_type")),
        ("Proposed works", project.get("works_description")),
        ("Latitude / longitude", f"{_text(site.get('latitude'))}, {_text(site.get('longitude'))}"),
        ("Nation", site.get("nation")),
        ("Search radius (km)", site.get("radius_km")),
        ("BGS query rectangle (CRS84)", site.get("bgs_bbox_crs84")),
    ):
        parts.append(f"<dt>{escape(label)}</dt><dd>{_html(value)}</dd>")
    parts.extend([
        "</dl><p class=\"muted\">The nation is caller supplied. BGS records are bounding-box "
        "candidates; the rectangle can include records outside the nominated radius. A nearby "
        "record requires investigation relevance and location-precision review.</p>",
        "<h2>Evidence coverage and query outcomes</h2>",
        _table(
            ["Evidence", "Topic / tool", "Execution status", "Records", "Failure"],
            [[
                _refs([entry["id"]], anchors),
                _html(entry.get("topic")) + "<br>" + _html(entry.get("tool")),
                _badge(entry.get("status", entry["result"].get("status"))),
                _html((entry["result"].get("pagination") or {}).get("returned")),
                _html((entry["result"].get("error") or {}).get("message"), "—"),
            ] for entry in report["evidence"]],
            "No provider evidence was recorded.",
        ),
        "<h3>Omitted queries</h3>",
        _list_html(report["omitted_queries"]),
        "<h3>Warnings</h3>", _list_html(report["warnings"]),
        "<h2>Regional geological observations</h2>",
        "<p>These are mapped regional interpretations at 1:625,000, not confirmed site strata, "
        "founding depths or measured engineering properties.</p>",
    ])
    geological = []
    for entry in report["evidence"]:
        collection = entry.get("arguments", {}).get("collection", "")
        if not isinstance(collection, str) or not collection.startswith("bgsgeology625k"):
            continue
        data = entry["result"].get("data", [])
        for record in data if isinstance(data, list) else []:
            if not isinstance(record, dict):
                continue
            props = record.get("properties")
            if not isinstance(props, dict):
                continue
            geological.append([
                _html(collection), _html(props.get("lex_d") or props.get("name")),
                _html(props.get("rcs_d") or props.get("description")),
                _html(_date_fields(props), "Unknown"), _refs([entry["id"]], anchors),
            ])
    parts.append(_table(
        ["Mapped collection", "Source formation label", "Source lithology", "Record dates", "Evidence"],
        geological, "No regional geological records were returned. See query outcomes and gaps.",
    ))
    candidate_rows = []
    for item in report["investigations"]:
        review = item.get("review") or {}
        links = "<br>".join(_link(link.get("url"), link.get("label")) for link in item.get("links", []))
        location = (
            f"{_html(item.get('latitude'))}, {_html(item.get('longitude'))}<br>"
            f"Position precision: {_html(item.get('position_precision'))}<br>"
            f"Approx. distance (m): {_html(item.get('distance_m'))}<br>"
            f"Within nominated radius: {_html(item.get('within_radius'))}"
        )
        candidate_rows.append([
            _html(item.get("reference")) + "<br>" + _html(item.get("name")) + "<br>" + links,
            _html(item.get("collection")), _html(item.get("depth_m")),
            "Year: " + _html(item.get("year")) + "<br>Updated: " + _html(item.get("updated_at")),
            location,
            _badge(review.get("status", "unreviewed"))
            + f'<p class="notes">{_html(review.get("notes"), "No review notes.")}</p>',
            _refs(item.get("evidence_ids", []), anchors),
        ])
    parts.extend([
        "<h2>Historic investigation candidates</h2>",
        "<p>Index entries identify records for review. Reported depth is the source's record "
        "length; it does not establish suitable founding depth. Relevance labels and notes "
        "are human review decisions. Original logs and release terms require separate review.</p>",
        _table(
            ["Record / links", "Index", "Recorded depth (m)", "Source dates", "Location", "Human review", "Evidence"],
            candidate_rows, "No investigation candidates are available in this evidence bundle.",
        ),
        "<h2>Groundwater observations</h2>",
        "<p>These are latest available observations, which can predate retrieval. Preserve the "
        "measure metadata and each reading's quality flag. mAOD is elevation relative to "
        "Ordnance Datum, not depth below ground. A nearby station can monitor a different aquifer.</p>",
    ])
    if not report["groundwater"]:
        parts.append("<p>No groundwater reading follow-up is included. See coverage and GI gaps.</p>")
    for item in report["groundwater"]:
        measure = item.get("measure") or {}
        unit = measure.get("unitName") or measure.get("unit")
        readings = item.get("readings", [])
        rows = [[
            _html(reading.get("dateTime") or reading.get("date")),
            _html(reading.get("value")), _html(reading.get("unitName") or unit),
            _html(reading.get("quality")),
        ] for reading in readings]
        parts.extend([
            f"<h3>{_html(item.get('station_name'))}</h3>",
            f"<p>Measure: {_html(item.get('measure_id'))}; query status: {_badge(item.get('status'))}; "
            f"evidence: {_refs([item.get('evidence_id')], anchors)}</p>",
            _table(["Observation time", "Recorded value", "Source unit", "Reading quality"], rows,
                   "No readings returned for this measure."),
            _list_html(item.get("warnings", [])),
            '<details class="raw"><summary>Measure metadata and original readings</summary><pre>'
            + escape(_json({"measure": measure, "readings": readings})) + "</pre></details>",
        ])
    parts.extend([
        "<h2>Ground investigation gap register</h2>",
        "<p>Priorities organise evidence acquisition. Actions are investigation questions and "
        "review tasks; they do not specify a certified sampling layout, test frequency or design.</p>",
    ])
    if not report["gaps"]:
        parts.append("<p>No gap entries recorded. This does not establish evidence completeness.</p>")
    for gap in report["gaps"]:
        parts.extend([
            '<article class="gap">',
            f"<h3>{_html(gap.get('id'))}: {_html(gap.get('title'))}</h3>",
            f"<p>Priority: {_badge(gap.get('priority'))} · Review task: {_badge(gap.get('status', 'open'))}</p>",
            f"<p>{_html(gap.get('reason'))}</p>", _list_html(gap.get("actions", [])),
            f"<p>Linked evidence: {_refs(gap.get('evidence_ids', []), anchors)}</p>",
            f'<p class="notes">Review notes: {_html(gap.get("notes"), "None recorded.")}</p>',
            "</article>",
        ])
    parts.extend([
        "<h2>Unknown design parameters</h2>",
        _table(["Parameter", "Value", "Basis"], [[
            _html(_DESIGN_PARAMETERS.get(key, key)), "Unknown",
            _html(value.get("reason"), "Not established by these data queries."),
        ] for key, value in report["design_parameters"].items()], "No design parameters recorded."),
        "<h2>Source register and audit trail</h2>",
        "<p>Report generation and retrieval times describe access, not observation or survey "
        "dates. Source records and metadata retain their original dates below. Provider data "
        "licences and attribution remain independent of the application code licence.</p>",
    ])
    for entry in report["evidence"]:
        result = entry["result"]
        source = result.get("source") or {}
        licence = source.get("licence") or {}
        parts.extend([
            f'<article class="source" id="{anchors[entry["id"]]}">',
            f"<h3>{_html(entry['id'])}: {_html(source.get('name') or entry.get('topic'))}</h3>",
            "<dl>",
            f"<dt>Provider</dt><dd>{_html(source.get('provider'))}</dd>",
            f"<dt>Query status</dt><dd>{_badge(entry.get('status', result.get('status')))}</dd>",
            f"<dt>Retrieved at UTC</dt><dd>{_html(result.get('retrieved_at_utc'))}</dd>",
            f"<dt>Coverage</dt><dd>{_html(source.get('coverage'))}</dd>",
            f"<dt>Licence</dt><dd>{_link(licence.get('url'), licence.get('name'))}</dd>",
            f"<dt>Licence scope</dt><dd>{_html(licence.get('scope'))}</dd>",
            f"<dt>Attribution</dt><dd>{_html(source.get('attribution'))}</dd>",
            f"<dt>Documentation</dt><dd>{_link(source.get('documentation_url'))}</dd>",
            "</dl><h4>Provenance</h4>",
        ])
        for provenance in result.get("provenance", []):
            parts.append(
                f"<p>{_link(provenance.get('url'))}<br>"
                f"Retrieved: {_html(provenance.get('retrieved_at_utc'))}<br>"
                f"HTTP status: {_html(provenance.get('http_status'))}<br>"
                f"Response SHA-256: {_html(provenance.get('response_sha256'))}</p>"
            )
        if result.get("error"):
            parts.append('<p class="notice">Query failure: ' + _html(result["error"]) + "</p>")
        parts.extend([
            "<h4>Query and pagination</h4><pre>" + escape(_json({
                "tool": entry.get("tool"), "arguments": entry.get("arguments", {}),
                "query": result.get("query", {}), "pagination": result.get("pagination", {}),
            })) + "</pre>",
            _list_html(result.get("warnings", [])),
            '<details class="raw"><summary>Complete source records and metadata</summary><pre>'
            + escape(_json(result)) + "</pre></details></article>",
        ])
    parts.append(
        "<footer>Preliminary desk study and GI planning evidence. Original records, location "
        "precision, source terms and engineering relevance require review. Complete source "
        "payloads remain in the HTML appendix; the raw appendix is omitted from print layout. "
        "No safe-to-dig, foundation design or regulatory compliance finding is established.</footer>"
        "</main></body></html>"
    )
    return "\n".join(parts)


def _md(value: Any, unknown: str = "Unknown") -> str:
    value = _text(value, unknown).replace("\\", "\\\\")
    for character in "`*_{}[]|":
        value = value.replace(character, "\\" + character)
    return value.replace("<", "&lt;").replace(">", "&gt;").replace("\r", " ").replace("\n", " ")


def render_markdown(report: dict) -> str:
    """Return a Markdown report with an escaped JSON evidence appendix."""
    validate_report(report)
    lines = [
        f"# {_md(report['project']['project_name'])}", "",
        "Geotechnical desk study and GI gap planner", "",
        f"Generated: {_md(report['generated_at_utc'])}. Query execution: {_md(report['status'])}.", "",
        "Query status describes retrieval, not site safety. Empty searches do not establish "
        "absence of hazards. Closed GI tasks are human review decisions.", "",
        "## Project scope", "",
        _md(report["project"]), "", _md(report["site"]), "",
        "## Coverage and warnings", "",
    ]
    for entry in report["evidence"]:
        result = entry["result"]
        lines.append(
            f"- {_md(entry['id'])}: {_md(entry.get('topic'))}; status "
            f"{_md(entry.get('status', result.get('status')))}; "
            f"returned {_md((result.get('pagination') or {}).get('returned'))}; "
            f"failure {_md((result.get('error') or {}).get('message'), 'none recorded')}."
        )
    for text in report["warnings"] + report["omitted_queries"]:
        lines.append(f"- {_md(text)}")
    lines.extend([
        "", "## Historic investigation candidates", "",
        "Index records require original-log and relevance review. Source length is not founding depth.", "",
        "| Reference | Index | Recorded depth m | Source year | Human review | Notes | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    for item in report["investigations"]:
        review = item.get("review") or {}
        cells = [item.get("reference"), item.get("collection"), item.get("depth_m"), item.get("year"),
                 review.get("status", "unreviewed"), review.get("notes"), item.get("evidence_ids")]
        lines.append("| " + " | ".join(_md(cell) for cell in cells) + " |")
    lines.extend([
        "", "## Groundwater observations", "",
        "Latest observations may be stale. mAOD is elevation, not depth below ground. "
        "Source units, datum and per-reading quality are retained in the evidence appendix.", "",
        _md(report["groundwater"]), "", "## GI gap register", "",
    ])
    for gap in report["gaps"]:
        lines.extend([
            f"### {_md(gap.get('id'))}: {_md(gap.get('title'))}", "",
            f"Priority: {_md(gap.get('priority'))}. Review task: {_md(gap.get('status', 'open'))}.", "",
            _md(gap.get("reason")), "",
        ])
        lines.extend(f"- {_md(action)}" for action in gap.get("actions", []))
        lines.extend([
            "", f"Evidence: {_md(gap.get('evidence_ids'))}", "",
            f"Review notes: {_md(gap.get('notes'), 'None recorded.')}", "",
        ])
    lines.extend(["## Unknown design parameters", ""])
    for key, value in report["design_parameters"].items():
        lines.append(f"- {_md(_DESIGN_PARAMETERS.get(key, key))}: Unknown. {_md(value.get('reason'))}")
    lines.extend([
        "", "## Source register and complete evidence", "",
        "Mapped 1:625,000 geology supplies regional context, not confirmed site strata. "
        "Retrieval timestamps are not observation or survey dates. Original records, dates, "
        "source attribution, licences, queries, pagination, quality and provenance follow.", "",
    ])
    for entry in report["evidence"]:
        result = entry["result"]
        source = result.get("source") or {}
        lines.extend([f"### {_md(entry['id'])}: {_md(source.get('name') or entry.get('topic'))}", ""])
        for provenance in result.get("provenance", []):
            url = _safe_url(provenance.get("url"))
            if url:
                lines.append(f"[Provider request]({quote(url, safe=':/?=&%#-_.~+@')})")
        raw = _json(entry).replace("`", "\\u0060")
        lines.extend(["", "```json", raw, "```", ""])
    return "\n".join(lines)


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("CSV values must be finite.")
        return value
    text = _text(value, "")
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_csv(report: dict, kind: str = "investigations") -> str:
    """Export reviewable registers, guarding strings against spreadsheet formulas."""
    validate_report(report)
    if kind not in {"investigations", "gaps"}:
        raise ValueError("CSV kind must be investigations or gaps.")
    if kind == "investigations":
        headers = [
            "id", "collection", "reference", "name", "depth_m", "year", "updated_at",
            "position_precision", "latitude", "longitude", "distance_m", "within_radius",
            "review_status", "review_notes", "evidence_ids", "source_links",
        ]
        rows = []
        for item in report["investigations"]:
            review = item.get("review") or {}
            rows.append([
                *(item.get(key) for key in headers[:12]),
                review.get("status", "unreviewed"), review.get("notes", ""),
                "; ".join(item.get("evidence_ids", [])),
                "; ".join(url for link in item.get("links", []) if (url := _safe_url(link.get("url")))),
            ])
    else:
        headers = ["id", "priority", "topic", "title", "reason", "actions", "status", "notes", "evidence_ids"]
        rows = [[
            gap.get("id"), gap.get("priority"), gap.get("topic"), gap.get("title"), gap.get("reason"),
            "; ".join(gap.get("actions", [])), gap.get("status", "open"), gap.get("notes", ""),
            "; ".join(gap.get("evidence_ids", [])),
        ] for gap in report["gaps"]]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows([_csv_cell(value) for value in row] for row in rows)
    return output.getvalue()
