# UK civil engineering data gateway

`uk-civil-data serve` exposes 27 tools: the existing 16 Groundwork and 7 public-data tools, plus `civil_coverage`, `area_census`, `road_collisions` and `civil_area_context`, in one read-only stdio MCP connection. The original CLI, GUI and narrower server profiles still work in the same repository. Install or update from the repository (`python -m pip install .`, Python 3.11+).

```json
{"mcpServers":{"uk-civil":{"command":"/absolute/path/.venv/bin/python","args":["-m","uk_data_mcp.civil_server","serve"]}}}
```

## Find the right source

`uk-civil-data tools` lists the callable tools. Run `uk-civil-data call civil_coverage` for the coverage matrix, or use `--json '{"query":"bridges"}'`. Each entry names the product, geography, access mode, official source, limitations and an example next call where meaningful. Modes: direct **query**, numerical data from a **prepared** official release, **metadata**, publisher/catalogue **discovery**, and **restricted**. A sector can span different modes. The catalogue is not exhaustive and metadata access is not permission to download an underlying asset record. Use national and ONS catalogue search for topics outside the reviewed matrix.

The register spans ground investigation; surveying and terrain; bridges, tunnels and structural assets; buildings; highways and road safety; public transport and rail; airports, ports and coasts; water, wastewater, hydrology and flood defences; energy, underground utilities and digital infrastructure; climate, pollution, waste, planning and heritage; construction materials, safety, costs and procurement; population, labour markets and housing. Maintenance or condition records are distinguished from assessed capacity and as-built drawings.

## Reproduce a comparison using only published files

```bash
uk-civil-data prepare ts001 stats19-2025 hpi-2025-01
uk-civil-data call civil_area_context --json '{"gss_code":"E08000025","collision_year":2025,"housing_month":"2024-01","housing_edition":"2025-01"}'
```

The result keeps three different things separate: the population recorded at the 2021 Census, a count of reported injury collisions in 2025, and a GBP average for January 2024 from **the January 2025 HPI release**. The latter is not the present price, a particular property sale, or necessarily the latest revision of the historical estimate. The [HMLR release](https://www.gov.uk/government/statistical-data-sets/uk-house-price-index-data-downloads-january-2025) contains an Average price CSV with geography codes. The importer joins by the actual recorded district code and month, not by place-name similarity. It can use districts in the file beyond the three mapped live API slugs. A missing figure is not a zero. A common code alone cannot establish identical historic boundaries. No collision risk rate or causal effect is calculated.

`housing_edition` defaults to `live`. For live prices the explicitly reviewed slug mappings are [Birmingham](https://www.ons.gov.uk/explore-local-statistics/areas/E08000025-birmingham), [Leeds](https://www.ons.gov.uk/explore-local-statistics/areas/E08000035-leeds) and [Cardiff](https://www.ons.gov.uk/explore-local-statistics/areas/W06000015-cardiff). A failed live response remains an error within a partial bundle; the service will not silently return an older publication. Omit `housing_month` to use only the census and collision sources. The standalone `house_prices` tool continues to accept HMLR provider slugs.

Other examples:

```bash
uk-civil-data prepare ts041 ts045 ts061 ts066 stats19-2024
uk-civil-data call area_census --json '{"gss_code":"W06000015","table":"ts061"}'
uk-civil-data call road_collisions --json '{"gss_code":"E08000035","year":2024}'
```

`prepare` downloads named [ONS/Nomis 2021 census archives](https://www.nomisweb.co.uk/census/2021/bulk), [DfT collision CSVs](https://www.gov.uk/government/statistical-data-sets/road-safety-open-data) or the HMLR file. It keeps compact district-level indexes, source hashes, attribution and dates; no household records or individual collisions are stored. The default cache is `~/.cache/uk-civil-data` (override `UK_CIVIL_CACHE`). Re-running `prepare` refreshes an edition, so retain a copy of the index to reproduce results from a previous file hash. MCP queries cannot trigger these downloads or write to disk. A missing local file returns `not_prepared` and the exact command to use.

Census scope is England/Wales LTLA on 21 March 2021: TS001 residents, TS041 households, TS045 household car/van availability, TS061 commuting, TS066 economic activity. Take care with overlapping category totals and pandemic-era commuting. Use [Scotland’s Census](https://www.scotlandscensus.gov.uk/) and [NISRA](https://www.nisra.gov.uk/statistics/people-and-communities/census) for their respective releases. Collision statistics count police-reported personal-injury **events** in Great Britain, not casualties, vehicles, all damage-only incidents or traffic exposure. Counts use raw reported severity, retain a national count of records without a usable district, and never treat an absent area as zero. [PSNI](https://www.psni.police.uk/about-us/our-publications-and-reports/official-statistics/road-traffic-collision-statistics) is separate. Company leakage, point boreholes and an area-wide house price are different spatial supports.

## Next connectors

1. ORR station usage and station geography. Keep station codes and reporting year; entries/exits are not passenger journeys or live departures.
2. Flood-defence and highway structures inventories. Separate geometry and inspection records from assessed structural capacity.
3. Terrain samples and corridor/polygon queries, retaining coordinate system, vertical datum, coverage and survey date.
4. Devolved parity: PSNI collisions, Scottish/NI census, SEPA/NRW/DfI water and flood datasets. Add matching national sources, not substitutes from England.

Acceptance for numerical adapters: reviewed official source and terms, bounded access, tests for missing vs zero and schema change, units/geography checks, and a dated real-source example. Licensed standards, sensitive utilities and project-specific inspections need appropriate authorised access. The gateway is not a design, regulatory approval or safe-to-dig service.
