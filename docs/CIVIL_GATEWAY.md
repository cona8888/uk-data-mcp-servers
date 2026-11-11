# UK civil engineering data gateway

`uk-civil-data serve` exposes 29 tools in one read-only stdio MCP connection: the original Groundwork and public-data tools plus civil coverage, local-authority census, collision counts, area comparison and corridor screening. The original CLI, GUI and narrower profiles still work. Install from this repository (`python -m pip install .`, Python 3.11+).

```json
{"mcpServers":{"uk-civil":{"command":"/absolute/path/.venv/bin/python","args":["-m","uk_data_mcp.civil_server","serve"]}}}
```

## Screen a proposed route

[Corridor guide, five data layers and verified Digbeth example](CORRIDOR.md). Supply a LineString alignment instead of a single coordinate. The tool returns distance along the alignment and offset from it, distinguishes crossings from nearby sites, and reports source-specific coverage and gaps. There is no need to prepare bulk releases for the corridor tool.

```bash
uk-civil-data call corridor_screen --json-file examples/corridor_birmingham.json > report.json
python scripts/corridor_view.py report.json map.html
```

## Find the right source

`uk-civil-data tools` lists the callable tools. Run `uk-civil-data call civil_coverage` for the coverage matrix, or use `--json '{"query":"bridges"}'`. Each entry names the product, geography, access mode, official source, limitations and an example next call where meaningful. Modes: direct **query**, numerical data from a **prepared** official release, **metadata**, publisher/catalogue **discovery**, and **restricted**. A sector can span different modes. The catalogue is not exhaustive and metadata access is not permission to download an underlying asset record. Use national and ONS catalogue search for topics outside the reviewed matrix.

The register spans ground investigation; surveying and terrain; bridges, tunnels and structural assets; buildings; highways and road safety; public transport and rail; airports, ports and coasts; water, wastewater, hydrology and flood defences; energy, underground utilities and digital infrastructure; climate, pollution, waste, planning and heritage; construction materials, safety, costs and procurement; population, labour markets and housing. Maintenance or condition records are distinguished from assessed capacity and as-built drawings.

## Reproduce a comparison using only published files

```bash
uk-civil-data prepare ts001 stats19-2025 hpi-2025-01
uk-civil-data call civil_area_context --json '{"gss_code":"E08000025","collision_year":2025,"housing_month":"2024-01","housing_edition":"2025-01"}'
```

The result keeps three things separate: population at the 2021 Census, a count of reported injury collisions in 2025 and a GBP average for January 2024 from **the January 2025 HPI release**. The latter is not the present price, a particular sale or necessarily the latest revision. The [HMLR release](https://www.gov.uk/government/statistical-data-sets/uk-house-price-index-data-downloads-january-2025) contains an Average price CSV with geography codes. The importer joins by recorded district code and month, not place-name similarity. It can use districts in that file beyond the three mapped live API slugs. A missing figure is not zero; a common code alone does not establish identical historic boundaries. No collision risk rate or causal effect is calculated.

`housing_edition` defaults to `live`. The reviewed live mappings are [Birmingham](https://www.ons.gov.uk/explore-local-statistics/areas/E08000025-birmingham), [Leeds](https://www.ons.gov.uk/explore-local-statistics/areas/E08000035-leeds) and [Cardiff](https://www.ons.gov.uk/explore-local-statistics/areas/W06000015-cardiff). A failed live response remains an error within a partial bundle; the service will not silently substitute an older publication. Omit `housing_month` for just the census and collision sources. `house_prices` still accepts HMLR region slugs.

```bash
uk-civil-data prepare ts041 ts045 ts061 ts066 stats19-2024
uk-civil-data call area_census --json '{"gss_code":"W06000015","table":"ts061"}'
uk-civil-data call road_collisions --json '{"gss_code":"E08000035","year":2024}'
```

`prepare` downloads named [ONS/Nomis Census 2021 archives](https://www.nomisweb.co.uk/census/2021/bulk), [DfT collision CSVs](https://www.gov.uk/government/statistical-data-sets/road-safety-open-data) or the HMLR file. It keeps compact district indexes, hashes, attribution and dates; it does not store household records or individual collisions. The default cache is `~/.cache/uk-civil-data` (override with `UK_CIVIL_CACHE`). Re-running `prepare` refreshes an edition; retain the index to reproduce a previous hash. MCP queries cannot trigger bulk downloads or write to disk. A missing local file returns `not_prepared` and the required operator command.

Census scope is England/Wales lower-tier local authorities on 21 March 2021: TS001 residents, TS041 households, TS045 household car/van availability, TS061 commuting, TS066 economic activity. Take care with overlapping category totals and pandemic-era commuting. See [Scotland’s Census](https://www.scotlandscensus.gov.uk/) and [NISRA](https://www.nisra.gov.uk/statistics/people-and-communities/census) elsewhere. Collision statistics count police-reported personal-injury **events** in Great Britain, not casualties, vehicles, damage-only incidents or traffic exposure. District totals use raw reported severity and retain a national count of records without a usable district; an absent area is not zero. [PSNI](https://www.psni.police.uk/about-us/our-publications-and-reports/official-statistics/road-traffic-collision-statistics) is separate. Company leakage, borehole points and area-wide prices are not observations from a single site.

## Next connectors

1. Broader bridge inventories: National Highways, local roads and rail structures; distinguish footprints/centreline crossings from reference points and from load ratings.
2. ORR station usage and station geography. Retain codes and reporting year; entries/exits are not journeys or live departures.
3. Terrain sampling and devolved parity: PSNI collisions, Scotland/NI census, SEPA/NRW/DfI water and flood datasets. Do not substitute English records for other nations.

Acceptance for numerical adapters: reviewed official sources and terms, bounded access, tests for missing versus zero and schema changes, units/geography checks and a dated real-source example. Licensed standards, sensitive utilities and project-specific inspections need appropriate authorised access. The gateway is not a design, approval or safe-to-dig service.

See [evidence integrity](EVIDENCE_INTEGRITY.md) before using saved caches, utility handoffs or near-boundary corridor results.
