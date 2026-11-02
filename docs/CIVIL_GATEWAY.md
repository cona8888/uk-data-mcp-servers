# UK civil engineering data gateway

`uk-civil-data serve` exposes the existing Groundwork and public-data tools alongside civil coverage, census, road safety and area comparison in one stdio MCP connection. No move to a new repository; the original CLI, GUI and narrower server profiles still work. Install or update from the repository (`python -m pip install .`, Python 3.11+). Start an MCP client using an absolute path to that environment's `uk-civil-data` executable with `serve` as the argument, or use the Python interpreter and `-m uk_data_mcp.civil_server serve`.

```json
{"mcpServers":{"uk-civil":{"command":"/absolute/path/.venv/bin/python","args":["-m","uk_data_mcp.civil_server","serve"]}}}
```

## Explore the whole remit, without confusing discovery with retrieval

`uk-civil-data tools` lists the callable tools. Call `civil_coverage` with no arguments for the full machine-readable coverage matrix; `{"query":"rail"}` or `{"query":"bridges"}` narrows it. Each result names the specific product, geography, access mode, an official link, limitations and an example follow-up call where meaningful. Modes are **query**, **prepared**, **metadata**, **discovery** and **restricted**. A sector can span several modes. A link to a publisher does not turn its records into an implemented connector, and public visibility is not a blanket licence. Numeric record coverage is incomplete in all four nations. Use national and ONS catalogue search for topics outside the reviewed matrix.

The register spans ground investigation; surveying and terrain; bridges, tunnels and structural assets; buildings; highways and road safety; public transport and rail; airports, ports and coasts; water, wastewater, hydrology and flood defences; energy, underground utilities and digital infrastructure; climate, pollution, waste, planning and heritage; construction materials, safety, costs and procurement; population, labour markets and housing. Maintenance and condition information is distinguished from physical capacity and as-built drawings.

## Reproduce an area comparison

```bash
uk-civil-data prepare ts001 stats19-2025
uk-civil-data call civil_area_context --json '{"gss_code":"E08000025","collision_year":2025,"housing_month":"2024-01"}'
uk-civil-data prepare ts041 ts045 ts061 ts066 stats19-2024
uk-civil-data call area_census --json '{"gss_code":"W06000015","table":"ts061"}'
uk-civil-data call road_collisions --json '{"gss_code":"E08000035","year":2024}'
```

The first command downloads the [official ONS/Nomis Census 2021 archive](https://www.nomisweb.co.uk/census/2021/bulk) and the named [DfT collision CSV](https://www.gov.uk/government/statistical-data-sets/road-safety-open-data). Only the lower-tier local-authority census table is read; only area totals are retained from the collision file. No household or collision-level database is stored. The command writes one atomic JSON index per edition under `~/.cache/uk-civil-data` (override with `UK_CIVIL_CACHE`). Repeating `prepare` refreshes that edition, so keep a copy of the index to reproduce results against a previous source hash. Ordinary MCP queries cannot write or trigger these bulk downloads. They return `not_prepared` and the exact operator command when needed.

Census tables: TS001 people by residence type, TS041 households, TS045 household car/van availability, TS061 travel to work, TS066 economic activity. The total column overlaps the categories. The March 2021 England/Wales census is not a current population estimate. Use [Scotland’s Census](https://www.scotlandscensus.gov.uk/) or [NISRA](https://www.nisra.gov.uk/statistics/people-and-communities/census) elsewhere. For road safety the result is the **number of collisions**, not people killed, vehicles or traffic exposure. Counts use reported rather than retrospectively adjusted severity. Rows not assigned to a usable district remain counted in the source metadata. An absent area is not reported as zero. [PSNI](https://www.psni.police.uk/about-us/our-publications-and-reports/official-statistics/road-traffic-collision-statistics) is separate.

`civil_area_context` joins using the area's GSS code, not a coordinate or name search. The optional HPI crosswalk is intentionally limited to [Birmingham](https://www.ons.gov.uk/explore-local-statistics/areas/E08000025-birmingham), [Leeds](https://www.ons.gov.uk/explore-local-statistics/areas/E08000035-leeds) and [Cardiff](https://www.ons.gov.uk/explore-local-statistics/areas/W06000015-cardiff). Standalone `house_prices` continues to support other provider region slugs. A common code does not certify identical historic boundaries; no automatic harmonisation or risk-rate calculation is performed. Company leakage, point boreholes and a district-wide house price cannot be treated as observations from a single site.

## Next connector priorities

1. Rail station usage and station geography (ORR); date the reporting year, retain station codes, distinguish entries/exits from journeys.
2. Flood-defence assets and highway structures; separate geometry, inspections and condition from assessed capacity. Connect the national/devolved sources explicitly.
3. Terrain samples, corridor/polygon selection and cross-boundary geography lookup, retaining CRS, vertical datum, coverage and survey date.
4. Devolved parity: PSNI collision counts, Scotland/NI census, SEPA/NRW/DfI water and flood data. Add matching sources, not synthetic substitutes.

Acceptance for each new numerical adapter: a reviewed official product/licence, bounded access, tests for invalid input and changed schemas, missing vs zero, units and geography, and a dated real-source example. Sensitive utility locations, licensed standards and project-specific inspections need their own authorised access; this gateway does not establish compliance, design parameters or clearance to excavate.
