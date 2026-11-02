# UK Public Data profile

`uk-public-data` is supplied in the same Python distribution as Groundwork. It needs Python 3.11+ and no provider key. It does not replace `launch.py`, `uk-data-mcp`, the Groundwork browser UI or its saved workspaces. No new repository, public server, credentials, hosted database or scheduled data collection is required.

## Run it

From the repository root, with the project virtual environment active:

```bash
python -m pip install .
uk-public-data tools
uk-public-data call public_sources --json '{"query":"water"}'
uk-public-data call house_prices --json '{"region":"birmingham","month":"2024-01"}'
uk-public-data call find_public_data --json '{"query":"household income","limit":3}'
uk-public-data call ons_series --json '{"uri":"/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms","year":2024,"frequency":"years"}'
uk-public-data call company_leakage --json '{"company":"Severn Trent Water"}'
uk-public-data call dataset_record --json '{"dataset_id":"meter_yorkshire"}'
uk-public-data call nista_publications --json '{"query":"pipeline","limit":3}'
```

For an MCP client use a separate entry pointing to the **same environment**. Use an absolute path; substitute `.venv/Scripts/python.exe` on Windows. Only the new profile's seven tools are loaded in this entry. To use both profiles, keep your existing Groundwork entry beside it.

```json
{"mcpServers":{"uk-public-data":{"command":"/absolute/path/.venv/bin/python","args":["-m","uk_data_mcp.public_server","serve"]}}}
```

## What each tool means

| Tool | Meaning and limit |
|---|---|
| `public_sources` | Offline reviewed routing directory. Includes capabilities, provider, geographic scope, limitations and licence notes. A manual portal or listed file is **not** a tested observations connector. |
| `find_public_data` | Live metadata searches of the [National Data Library CKAN directory](https://guidance.data.gov.uk/get_data/api_documentation/) and [ONS Search](https://developer.ons.gov.uk/search/search/), plus suggested local cards. Any subject; distinct hit totals and statuses. `catalogue` selects `both`, `national_directory` or `ons`. `limit` 1–25 per catalogue. Use `offset` for later pages. One provider can fail without hiding the other. Curated data.gov.uk collections and non-indexed services are not a complete national inventory. |
| `dataset_record` | Public CKAN UUID/slug → dataset metadata, licence and a bounded page of resource links. Alias shortcuts: `ea_telemetry`, `meter_yorkshire`, `ea_annual_returns`, `uk_hpi`. The response hash is for the catalogue response **not** the linked files. No resource is downloaded. |
| `house_prices` | Monthly-reference HMLR UK HPI record: average price (GBP), house-price index, percent changes and sales volume when present. Checks the region/month identity. Use HMLR's region slug, not a postcode; NI measurements are not independent monthly estimates. This is not an individual sale price. [Provider data](https://landregistry.data.gov.uk/data/ukhpi) · [attribution](https://www.data.gov.uk/dataset/3bff64e9-0691-4569-bf12-323d4e60220e/uk-house-price-index). Actual England/Wales transactions are separately discoverable in [Price Paid Data](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads); transaction ingestion is not provided. |
| `ons_series` | Values for one ONS time-series URI, calendar year and frequency. Use the `uri` from an ONS time-series search result. Retains original value strings, suppression, release information and units where supplied. Use the source publication for denominator, seasonal adjustment and geography. Not every ONS publication is a time series; census cube and survey microdata extraction are not implemented. [ONS data endpoint guide](https://developer.ons.gov.uk/retirement/v0api/). |
| `nista_publications` | [GOV.UK search](https://docs.publishing.service.gov.uk/repos/search-api/using-the-search-api.html) filtered by NISTA's organisation, not just a keyword search. Publications only; for project-level pipeline access follow the publisher's [pipeline](https://pipeline.nista.grid.civilservice.gov.uk/) and its terms. |
| `company_leakage` | Explicit historical edition: EA's [England 2024/25 annual water resources performance report](https://www.gov.uk/government/publications/water-resources-2024-2025-analysis-of-the-water-industrys-annual-water-resources-performance/water-resources-2024-to-2025-analysis-of-the-water-industrys-annual-water-resources-performance), Figure 8. Reads the publisher's table through the GOV.UK Content API; returns **percentage of distribution input**, not Ml/day, a leak count, or a current reading. It rejects missing or ambiguous tables. Omit `company` to get published labels including the national average. For other editions/metrics use `dataset_record ea_annual_returns` or the Ofwat publisher link. |

### Six requested web connections

| Supplied source | Access in this profile |
|---|---|
| [Ofwat sector hub](https://www.ofwat.gov.uk/regulated-companies/open-data-in-the-water-industry/#sector) | `public_sources` → `ofwat`, `stream`, `ofwat_leakage`; links to sector datasets and company reporting. Industry registries and company-specific terms are distinct. The numerical leakage tool uses the named EA publication, not the Ofwat hub. |
| [Defra real-time water quality](https://environment.data.gov.uk/dataset/365df16f-1b80-4e0e-9ed9-1450e0238aef) | `dataset_record ea_telemetry` uses the [harvested record](https://www.data.gov.uk/dataset/dccd6c78-5a29-48d7-8d91-bd6a152742a5/national-real-time-water-quality-data). The Defra UUID is not the CKAN UUID. The publisher links to a telemetry viewer; this tool does not report live sensor measurements or substitute the separate sampled-water archive. |
| [ONS water leakage search](https://www.ons.gov.uk/search?q=water+leakage) | `find_public_data` with `catalogue=ons`, `query=water leakage`. Search finds publications, not leakage estimates. For a company number use a publication with an explicit metric and period. |
| [Waterwise](https://database.waterwise.org.uk/) | Independent reference library, not a government sensor service. Canonical landing page only: no expiring challenge URLs, tokens, scraping or CAPTCHA bypass. |
| [NISTA](https://www.gov.uk/government/organisations/national-infrastructure-and-service-transformation-authority) | `nista_publications`; official organisation-filtered publication search as above. |
| [Customer Meter Data](https://www.data.gov.uk/dataset/6900f4b9-5fa9-4938-bd6b-977920d2d7f3/customer-meter-data) | `dataset_record meter_yorkshire` returns resource links. Publisher: Calderdale Metropolitan Borough Council; coverage: Yorkshire Water service area, 2010/11–2014/15. Not contemporary national meters, public leak locations or household demographics. See local analysis below. |

### Historical meter CSVs: aggregate locally

Choose one original CSV after checking its terms and guidance. In a local directory outside Git:

```bash
python -m uk_data_mcp.meter_summary readings.csv > town-consumption.json
```

This is deliberately a local CLI, not an MCP tool with filesystem access. It reads the publisher's columns, retains reading source, groups by postal town and interval **end** year, and suppresses groups with fewer than ten distinct meters. It outputs summed volume (m³), recorded meter-days and the ratio of those sums in L/recorded meter-day. Check the excluded-row count. It does not output meter IDs, addresses or billpayer ages. It does not match households to sales, audit duplicate intervals, estimate network leakage, or infer annual population consumption. The minimum group size is a disclosure precaution, not a guarantee of anonymity. `--encoding cp1252` is available for legacy source files.

### Example research question

For a Birmingham house-price observation, ask for the named HPI region and month. For socioeconomic context, search for local income, earnings or tenure and verify the geography code, year, denominator, release and disclosure rules. For water leakage, use the **company service area** and reporting year. Without a compatible geography crosswalk, return separate results: do not attribute a Severn Trent company average or Yorkshire historical meter data to a Birmingham property. An unsuccessful query means unavailable, not zero.

## Validation

`python -m pytest -q -m 'not live'` runs deterministic tests alongside the existing suites. The [public-provider smoke workflow](https://github.com/cona8888/uk-data-mcp-servers/actions/workflows/public-data-smoke.yml) runs when its own workflow file is first added or changed on `main`, or by manual dispatch. It is not a recurring crawler and does not contact private sources. To repeat locally: `python scripts/smoke_public_profile.py`. It records exact requests, timestamps, response digests and positive-result checks in `public-smoke.json`. Keep live evidence separate from synthetic fixtures; tests are not certification of the underlying records.
