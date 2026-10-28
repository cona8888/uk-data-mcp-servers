# Groundwork desk study and GI planner

Groundwork combines preliminary desk-study evidence gathering with a historic
investigation review and ground-investigation gap register. It uses this
repository's MCP tools to retain the link between each record, the provider
request, source terms and the questions that still need investigation.

The local browser application, `desk_study` MCP tool and `desk-study` CLI share
one workflow. The application calls the MCP tool through the official SDK's
in-memory protocol transport. No AI model, provider API key, hosted account or
external JavaScript service is required.

## Start the application

Install the repository following the README, then run:

```text
uk-data-mcp app
```

Open `http://127.0.0.1:8765`. Use `--port 8766` if another application occupies
the default port. The app binds to the loopback interface. It is a local
workspace; public hosting and multi-user authentication are outside this release.

On Windows PowerShell with the repository virtual environment:

```powershell
.\.venv\Scripts\python.exe -m uk_data_mcp app
```

Load the **public Birmingham example** to explore the interface without live
provider requests. Its evidence was retrieved on **27 October 2026**, and the
display preserves that date. It contains bounded SOBI results and a groundwater
follow-up; the original snapshot did not query the AGS index. Missing queries
remain explicit. The example is not a defined construction project.

A [draft desk-study report](desk-studies/birmingham-draft-geotechnical-desk-study.pdf)
and its [editable Markdown source](desk-studies/birmingham-draft-geotechnical-desk-study.md)
review the fresh 28 October Birmingham run. Revision **D02** includes visual
review of all twelve pages of the six original BGS PDFs, with recorded strata,
historic water/test notes, depth/date discrepancies and a revised prioritised GI
plan. The [factual log-review audit record](../examples/birmingham_original_log_review_2026-10-28.json)
retains source URLs, hashes, page references, conversions and uncertainties;
original scans are not redistributed. The 423 provider-reported index matches
remain incompletely searched, and the demonstration's site boundary and works
remain undefined. The frozen app export is unchanged; D02 is a subsequent review.

For a fresh study, enter the project name, location, nation, search radius,
development type and proposed works. Review the advanced request limits before
running it. The point and nation are supplied by the user; they are not a
surveyed boundary or an independently geocoded nation.

## Evidence and record review

The workflow queries regional bedrock and superficial geology, SOBI and AGS
investigation indexes, and recorded landslides where configured. In England it
also queries EA monitoring stations, current flood warnings, groundwater
stations and the local planning authority, then follows a bounded selection of
groundwater measures. Original logs, PDFs and AGS files are linked for review;
the server does not download or interpret them.

Each evidence entry keeps its query arguments, result status, raw provider data,
source attribution and licence scope, request URL, retrieval time, response hash,
pagination, warnings and available observation metadata. The Sources view and
the exported report expose this register. An empty result and a failed request
remain different outcomes.

Historic investigation records have four human review states:

| State | Meaning |
|---|---|
| Unreviewed | No relevance decision has been recorded |
| Relevant | The reviewer considers the record relevant; record the basis in notes |
| Not relevant | The reviewer has excluded it; retain the reason and source |
| Needs review | More information or specialist review is needed |

Review location precision, investigation purpose, age, depth, sampling,
stratigraphy and test quality in the original files before deciding relevance.
The app does not automatically infer that a nearby record applies to the site.
Coordinates in WGS84 can support an approximate straight-line distance; BNG
coordinates remain in the raw properties without automatic conversion. A missing
distance stays unknown. A record's update date is not its investigation date.

The AGS index uses its location identifier and project name for the candidate
reference and name. Its `loca_fdep` field maps to recorded final depth in metres,
following the [official AGS 4.1.1 dictionary](https://www.ags.org.uk/content/uploads/2022/02/AGS4-v-4.1.1-2022.pdf).
The source properties and BGS identity remain alongside those display fields.

Repeated records with the same stable identity within one collection are
deduplicated, with their evidence references retained. SOBI and AGS records are
kept separate because similar names or locations do not establish that they are
the same physical investigation. Candidate counts are counts of retained index
identities, not necessarily distinct physical boreholes.

## GI gap planning

The register proposes evidence questions for the selected development type. It
covers the site and proposed works, original investigation review, detailed
ground model, groundwater, material properties, site history, relevant mining
and ground hazards, utilities and access, and terrain/walkover evidence. Failed,
omitted and incomplete queries create additional source-coverage tasks.

The proposed priorities support review of evidence acquisition. They are not
hazard probabilities, measured site conditions or a prescribed drilling schedule.
The planner does not set investigation locations, quantities, depths or test
frequencies. Agree those with the geotechnical engineer after reviewing the
proposed works and conceptual ground model.

Gap tasks can be **open**, **in progress** or **closed**, with notes. Closing a
task records a workflow decision; it does not certify that the underlying
engineering issue is resolved. Strength, stiffness, permeability, design water
level, allowable bearing pressure and utility clearance remain unknown in the
report even after tasks are closed.

## Save and export

Review edits remain in browser memory. Download the JSON workspace to save the
evidence and decisions, then use Open saved JSON to restore it. Refreshing or
closing the tab before saving loses unsaved edits. The server does not store
project names, notes or completed workspaces.

Available exports are:

- An editable JSON workspace containing the evidence and review states.
- CSV investigation and GI gap registers, with spreadsheet formula prefixes
  escaped for safer opening in spreadsheet software.
- A standalone printable HTML report with review decisions and source evidence.
  Use the browser's print function to print or save a PDF.

The CLI also exports Markdown. Source and project text is escaped in rendered
reports, and executable URL schemes are not made into links. Imported workspaces
must match the report schema and remain below 10 MB. The current schema preserves
unknown design parameters rather than accepting user-supplied design values.

Use a private location for actual project workspaces. The repository's `reports/`
directory is ignored by Git; downloaded client files are not uploaded to GitHub
by the app. Public examples supplied with this package contain public provider
evidence only.

## CLI and MCP use

Generate a small fresh study and export five artifacts:

```text
uk-data-mcp desk-study --latitude 52.45 --longitude -1.93 --nation England --project-name "Birmingham example" --development-type general --radius-km 1 --limit 3 --max-borehole-pages 2 --max-groundwater-measures 1 --output-dir reports/birmingham
```

The directory receives `desk-study.json`, `desk-study.html`, `desk-study.md`,
`investigations.csv` and `gi-gaps.csv`. Without `--output-dir`, the command prints
the JSON report. A report with all provider requests failed is still retained
and the command exits with an error status. Partial results are preserved.

Re-export a saved workspace after review:

```text
uk-data-mcp report --input reports/birmingham/desk-study.json --output-dir reports/reviewed
```

An MCP client can call `desk_study` with:

```json
{
  "latitude": 52.45,
  "longitude": -1.93,
  "nation": "England",
  "project_name": "Birmingham example",
  "development_type": "general",
  "radius_km": 1,
  "limit_per_source": 3,
  "max_borehole_pages": 2,
  "max_groundwater_measures": 1
}
```

## Search budgets and interpretation

| Input | Allowed values | Default |
|---|---|---|
| Radius | 0.1 to 20 km | 1 km |
| Records per source page | 1 to 20 | 10 |
| Pages per investigation index | 1 to 5, including the first page | 3 |
| Groundwater measures followed | 0 to 5 | 3 |
| Project name | 1 to 120 characters | Untitled project |
| Proposed works description | Up to 2000 characters | Empty |

At the maximum budget, at most 100 records per investigation index are requested
before deduplication. The workflow follows validated advancing offsets and stops
at its page limit; it never crawls arbitrary provider URLs. Other source results
are bounded pages. The register flags unresolved pagination instead of presenting
the bundle as an exhaustive search. Requests are sequential within the workflow;
the HTTP layer also preserves its provider rate spacing and bounded timeouts.
The browser permits one live study at a time and limits the full operation to
ten minutes.

BGS queries select an approximate enclosing rectangle, not an exact circle or
site polygon. A candidate outside the stated radius remains visible and marked
when its coordinates permit that check. Inventory completeness, coordinate
precision and mapping scale still limit what a retrieved record can establish.

The 1:625,000 geology supports regional context. Groundwater queries return the
latest available observations, which may be old or unchecked; mAOD is elevation,
not depth below ground. Current flood warnings do not establish long-term flood
risk. Planning authority discovery does not assess every planning constraint.
See [source scope and terms](DATA_SOURCES.md).

Outside England, the workflow omits its EA and Planning Data operations. For
Northern Ireland it also omits the configured historic investigation and
landslide indexes and directs review toward national sources. These omissions
remain in the report. The combined workflow has the most complete implemented
coverage in England.

## Application structure

`deskstudy.py` composes the existing provider tools through `DataService.call`.
`server.py` exposes the read-only `desk_study` MCP tool. `webapp.py` invokes that
tool through the official MCP client and serves the local buildless interface.
`reporting.py` validates workspaces and renders the exports; both the CLI and
browser use it. The packaged demo is rebuilt by `scripts/build_demo.py` from the
dated public snapshot without network requests.

The app has no server-side project database, remote file ingestion, automatic
log interpretation or statistical parameter estimation. These are explicit
extension boundaries rather than hidden steps in the current workflow.
