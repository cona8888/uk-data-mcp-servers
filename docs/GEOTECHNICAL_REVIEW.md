# MCP validation and geotechnical project opportunities

Projects 1 and 2 were subsequently implemented in **v0.2.0** as
[Groundwork](GROUNDWORK.md), including the BGS pagination repair. See
[implementation validation](GROUNDWORK_VALIDATION.md) for the new checks;
the assessment below records the earlier reviewed commit.

Review date: **28 October 2026**. Reviewed repository: [cona8888/uk-data-mcp-servers](https://github.com/cona8888/uk-data-mcp-servers), branch `main`, commit `ab2e76a4de1fac9f94a03e23255e81062790510e`.

The MCP server is a working foundation for preliminary geotechnical evidence gathering. The strongest first application is an **England desk-study assistant combined with a historic investigation review and ground-investigation gap register**. Its software and protocol checks passed on Windows. Live data access was inconsistent: one request timed out in the provider smoke suite, and a separate live MCP site query retained four BGS connection failures alongside successful sources. Treat the service as a research MVP with visible data gaps.

## Validation performed in this review

These are fresh checks on the reviewed commit. The [27 October validation record](VALIDATION.md) describes a separate earlier run.

| Check | Result on 28 October |
|---|---|
| Environment | Windows, Python 3.12.14, MCP SDK 2.3.0, HTTPX 0.28.1 |
| Installation | Local package and pinned runtime requirements installed in an isolated virtual environment |
| Offline suite | **86 passed in 4.28 seconds**, including real subprocess stdio and loopback Streamable HTTP clients |
| Additional real stdio discovery | **15 tools, 2 resources, 1 prompt**; successful `list_sources` call; 36 registry entries, 11 implemented source entries |
| Lint and dependency consistency | `ruff check .` and `pip check` passed |
| Packaging | Source archive and wheel built; `uk_data_mcp/sources.json` verified inside the wheel |
| Public provider smoke suite | **17 of 18 checks completed without error**: 5 `ok`, 8 `partial`, 4 `empty`; 1 EA station discovery timeout; 19 recorded successful HTTP responses |
| EA station follow-up through MCP | Same 5 km, limit 2 query subsequently returned 2 records with `partial` status and HTTP 200; the original timeout is preserved |
| Live `site_context` through stdio MCP | Birmingham demonstration, 1 km, limit 3: overall `partial`; 4 BGS connection errors, 2 successful empty EA responses, 1 hydrology station, 1 planning authority |
| Docker | CLI installed; Docker daemon unavailable. Image build and container protocol operation remain unverified |

The live suite uses small sample requests, not exhaustive connector or geographic coverage. `partial` usually means a bounded page with further matches; `empty` is a successful search without returned records. Neither establishes absence of a hazard. The separate MCP site demonstration is incomplete and must not be presented as a complete desk study.

Evidence files:

- [Provider requests, timestamps, hashes, counts and failure](live-checks-2026-10-28.json)
- [MCP discovery and synthetic pagination reproduction](review-evidence-2026-10-28.json)
- [Offline test results](test-results-2026-10-28.xml)
- [Live Birmingham MCP bundle and EA follow-up](birmingham-mcp-review-2026-10-28.json)

The Birmingham coordinates are a public demonstration location, not a defined construction site. The fixed smoke-test bounding box and approximate 1 km site-query box differ. Counts from those queries should not be compared as if their areas were identical.

## Findings and practical limits

**Minor BGS pagination inconsistency, confirmed with a synthetic response.** In [the BGS adapter](../src/uk_data_mcp/adapters/bgs.py), `truncated=bool(has_more)` considers only later pages. For a request with `offset=2`, one returned record and three total matches, the final page reports `status=ok` and `truncated=false`, although two earlier matches are omitted. Other paginated adapters also consider a positive offset. The query retains its offset, so consumers can detect the subset, but a client relying only on status can mistake it for the full result set. Suggested repair: include `offset > 0` in the truncation flag and add a final-page regression test. Source code was left unchanged during this assessment.

**External reliability remains a material limit.** The EA timeout recovered in the follow-up. The four BGS failures during the separate MCP call had `code=network_error` and no HTTP status; BGS queries had succeeded in the earlier direct-service smoke suite. The available evidence does not establish whether the cause was transient connectivity, upstream availability or the client environment. Record provider failure prominently and retain successful components; do not substitute an empty search or reuse an older snapshot without its date.

**Geological detail limits the engineering conclusions.** The implemented BGS geology is 1:625,000 national overview mapping. It can establish regional context, while a site ground model needs more detailed mapping and investigation evidence. Borehole and AGS connectors currently retrieve index records and links, with original logs and test data requiring separate review. [BGS 625K](https://www.bgs.ac.uk/datasets/bgs-geology-625k/), [SOBI](https://www.bgs.ac.uk/datasets/boreholes-index/), [AGS service](https://www.bgs.ac.uk/technologies/geotechnical-data-services/ags-download-service/).

**Groundwater and spatial analysis need extensions.** The current readings tools request the latest available observations. Seasonal maxima, rainfall response and design groundwater levels require bounded historical-series retrieval and site-specific hydrogeological assessment. Planning queries intersect one point, and `site_context` requests the local planning authority only. The upstream services support richer historical and spatial queries than these adapters expose. [EA Hydrology reference](https://environment.data.gov.uk/hydrology/doc/reference), [Planning Data documentation](https://www.planning.data.gov.uk/docs).

England has the most complete combined workflow. The configured SOBI and landslide indexes cover Great Britain, while the EA and Planning Data workflow is scoped to England. The caller supplies the nation; the server does not independently check the boundary. OS tools discover products and download links without ingesting terrain or road geometry. DfT returns annual traffic estimates, with no design axle-load model.

The server already preserves source attribution, licence scope, request provenance, units, datum, observation metadata and unknown design parameters. HTTP host restrictions, response-size limits, rate spacing and bounded pagination support controlled discovery. Remaining deployment boundaries and source access restrictions are described in [deployment notes](DEPLOYMENT.md) and [the source guide](DATA_SOURCES.md).

## Ranked geotechnical projects

The ranking below is an application assessment based on the implemented tools and their limits. “Current connectors” means the data access exists; report, map and workflow interfaces still require implementation.

| Priority | Potential project | MCP tools and useful output | Readiness and added evidence |
|---|---|---|---|
| 1 | Preliminary desk study for housing, warehouses, solar farms or battery sites | `site_context`, `bgs_features`, hydrology tools and selected `planning_entities` queries; produce a cited evidence register, regional geology summary and investigation questions | **Current connectors.** Engineer reviews relevance and adds site history, detailed geology and investigations before design |
| 2 | Historic investigation reuse and GI gap planner | SOBI and AGS through `bgs_features`; paginate candidate records and review coordinates, precision, age, depth and log links where supplied | **Current connectors at index level.** Original logs, site boundaries and proposed works determine whether records can be reused and where new investigation is needed |
| 3 | Evidence comparison across candidate development sites | Repeated `site_context`, SOBI/AGS queries and source metadata; compare data availability, age, missing coverage and provider failures | **Current connectors for a small supplied site list.** Compare evidence adequacy; record counts cannot rank site safety or foundation cost. Exact site polygons need spatial processing |
| 4 | Groundwater evidence assessment for basements and excavations | `hydrology_stations`, `hydrology_readings`, `ea_stations`, `ea_readings`, geology; produce a series shortlist, date/unit/datum/quality table and monitoring gap register | **Current connectors for scoping.** Historical windows, site monitoring, permeability and aquifer interpretation are needed for seasonal groundwater and dewatering design |
| 5 | Recorded landslide reconnaissance around proposed works | Landslide index and regional geology through `bgs_features`; produce recorded-event references and walkover questions | **Current connectors for event discovery.** Terrain, detailed mapping, event extents and ground investigation are needed for susceptibility or slope-stability work. Inventory points do not describe complete slide extents |
| 6 | Road or utility corridor investigation reconnaissance | BGS queries along a supplied alignment, EA context in England, `dft_traffic` and OS discovery; produce a segment evidence register and investigation gaps | **Prototype with a supplied alignment.** Add corridor geometry, overlap/deduplication and local spatial indexing. Current OS discovery supplies no route geometry, and traffic estimates supply no design loading |
| 7 | Brownfield redevelopment investigation scoping | `planning_entities`, `data_gov_search`, BGS and EA tools; identify public records, missing contamination evidence and records to acquire | **Partial support.** Add historic maps, site activities, remediation files, mining searches and full-area queries before a contamination or ground-risk assessment |
| 8 | AGS-based conceptual ground model and test-data quality review | Use AGS/SOBI index discovery to locate investigation files; develop depth-aligned strata, test tables and sections | **Extension project.** Needs authorised AGS/PDF ingestion, units/CRS/depth checks, provenance and geological interpretation. The current server supplies discovery links only |

The [BGS landslide database](https://www.bgs.ac.uk/geology-projects/landslides/national-landslide-database/) supports recorded-event discovery. The [OS Downloads specification](https://docs.os.uk/os-apis/accessing-os-apis/os-downloads-api/technical-specification) describes product/download services, and [DfT's API documentation](https://roadtraffic.dft.gov.uk/api-documentation) describes annual traffic data. These provider capabilities bound projects 5 and 6.

## Recommended first implementation

Build **projects 1 and 2 together**, initially for a supplied England site point and explicitly stated search area. Deliver a source-linked evidence report, a candidate investigation register and a table of missing evidence. Show each provider's execution status, pagination, source date and coverage beside its findings. Retain strength, stiffness, permeability, bearing pressure and design groundwater as unknown until suitable investigation and interpretation establish them.

A useful acceptance demonstration would:

1. Query the supplied location with `site_context`, then explicitly query the AGS index and paginate relevant SOBI records within agreed limits.
2. Follow relevant groundwater measure identifiers and show observation date, units, datum and quality, with the latest-only limit visible.
3. Link every statement to source records and distinguish regional mapping, measured observations and catalogue pointers.
4. Preserve provider failures and incomplete pages, and require review of investigation relevance before producing the GI gap register.
5. Export the evidence and review decisions without assigning unmeasured design parameters or claiming complete utility clearance.

After that pilot, prioritise the BGS pagination repair, exact site polygons and CRS conversion, detailed geology under applicable terms, bounded historical groundwater windows, terrain sampling, and authorised AGS ingestion. Those additions would support corridor studies and richer conceptual ground models.

## Reproducing the principal checks

From the repository in an activated Python 3.11+ environment:

```text
python -m pip install -r requirements-runtime.txt ".[dev]"
python -m pytest -q
python -m ruff check .
python -m pip check
python -m build
python -m uk_data_mcp tools
python scripts/smoke_live.py --output new-live-checks.json
```

The last command contacts public providers and exits nonzero if a check returns an error. Preserve its result rather than overwriting a failed run. On Windows, `PYTHONUTF8=1` avoids console-encoding errors in build subprocess logs when paths contain non-ASCII characters. The test run emitted a non-failing pytest-asyncio warning about an unset future fixture loop-scope default.

This review validates software behaviour and sampled interfaces. Engineering use still depends on the relevance, completeness and quality of the underlying site evidence.
