# Groundwork implementation validation

Date: **28 October 2026**. Version: **0.2.0**. These checks cover the combined
desk-study assistant and GI gap planner implemented after the earlier
[repository assessment](GEOTECHNICAL_REVIEW.md).

## Software checks

| Check | Result |
|---|---|
| Runtime | Windows, Python 3.12.14, MCP SDK 2.3.0, HTTPX 0.28.1 |
| Full offline suite | **158 passed in 4.03 seconds** |
| MCP integration | New `desk_study` tool discovered and called through the official SDK with controlled provider responses; actual subprocess stdio and loopback HTTP handshakes pass |
| Workflow coverage | Bounds, page limits, contiguous pagination, duplicate identities, provider failures, nation omissions, groundwater follow-ups and unknown design parameters |
| Browser API | Input/body limits, local host and same-origin checks, one-study concurrency, error responses and reviewed report export |
| Rendering and import | Escaped source text, safe link schemes, CSV formula prefixes, malformed nested JSON, preserved human notes and null design parameters |
| BGS regression | Final pages with a positive offset retain partial status; a complete collected sequence is distinguished from an unresolved page budget |
| Lint | `ruff check .` passed |
| Browser source | JavaScript syntax check passed; no external browser assets or automatic live request on page load |

The tests use synthetic records for deterministic behaviour. They are distinct
from the public live evidence described below. The packaged dated Birmingham
demo remains based on its original 27 October retrievals.

## Live MCP and browser checks

A fresh study was run from the local browser interface through the official MCP
client to the new `desk_study` tool. Inputs were latitude 52.45, longitude -1.93,
England, 1 km, 2 records per page, at most 2 pages per investigation index, and
1 groundwater measure. The selected development type was basement/excavation;
the description explicitly identified a public demonstration without a defined
construction site or design loads.

The run produced:

- **11 tool-query results**, with no provider errors: 3 `ok`, 4 `partial`, 4 `empty`.
- **13 successful HTTP responses**, including Planning Data and groundwater
  measure metadata lookups.
- **4 retained SOBI candidates**, spanning two pages. AGS and landslide queries
  were successfully empty in this particular search area.
- **3 unresolved coverage entries** after accounting for followed pages, and
  **13 open GI review tasks**.
- All seven geotechnical design parameters explicitly unknown.

The report correctly remains `partial`. Regional mapping and borehole pages
have more matches than the chosen budget retrieves. The raw partial-page count
differs from unresolved coverage because the first SOBI page was followed.
The groundwater display retained the source observation date of 16 June 2026,
its mAOD unit and its Unchecked quality flag, rather than presenting retrieval
time as measurement time.

The full public output, including query arguments, source attribution, licences,
request URLs, timestamps, hashes and pagination, is retained in
[the fresh Birmingham study](../examples/birmingham_desk_study.json). This is a
demonstration location, not a site assessment.

One additional public AGS index query returned a non-empty record around central
London. It verified `bgs_loca_id`, `loca_id`, `proj_name`, `loca_fdep`, geometry,
log links and accession links. Final-depth units were checked against the
[official AGS 4.1.1 dictionary](https://www.ags.org.uk/content/uploads/2022/02/AGS4-v-4.1.1-2022.pdf).
Regression fixtures use synthetic values with those real field names; the live
sample containing third-party contact fields is not committed.

Browser checks verified:

1. Loading the dated demo without refreshing provider data.
2. Opening an investigation, changing relevance status and recording notes.
3. Saving a JSON workspace, then reading back the saved review decision and notes.
4. Editing a GI task's workflow status and opening its notes control.
5. Restoring a saved workspace and retaining its review state and source evidence.
6. Running a fresh bounded study, with visible progress and provider outcomes.
7. Inspecting licence scope, exact requests, hashes, observation metadata and warnings.
8. Downloading the printable HTML report; CLI export also produced JSON,
   Markdown and both CSV registers from the same live output.
9. Rejecting a malformed workspace with a null provenance entry while retaining
   the already open study.

The interface was inspected in the app's narrow browser panel. No explicit
large-screen viewport override or native mobile device test was performed.

## Packaging and remaining boundaries

Source and wheel packages built successfully. The wheel includes the HTML,
CSS, JavaScript and dated demo. A local wheel installation was checked for
version 0.2.0, dependency consistency, health and demo routes.

Docker execution, remote hosting and external MCP client-account installation
were not exercised in this implementation run. The app binds locally and does
not persist projects on the server. Public GitHub source contains the code,
synthetic tests, guides and public examples; local reports and private workspaces
are excluded from the save.

The assistant produces an evidence register and questions for investigation.
Original log review, detailed ground modelling, site history, relevant hazard
records, site monitoring and geotechnical interpretation remain necessary for
engineering decisions. A closed task or successful query does not establish a
design value or site clearance.
