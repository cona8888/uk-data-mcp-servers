# UK infrastructure and ground-data sources

Reviewed **27 October 2026**. The machine-readable registry in `src/uk_data_mcp/sources.json` contains **36 source entries**, of which **11 have a bounded adapter in this release**. A source entry may correspond to several tools or to one narrow part of a provider's service. Catalogue-only, planned and restricted entries do not have functioning data connectors merely because they appear in this list.

The UK approach needs a common interface over several publishers. Data.gov.uk is a discovery directory; it does not host or confer rights to all UK datasets. The [government API catalogue](https://www.api.gov.uk/) explicitly warns that an API's inclusion does not mean it is publicly accessible. MCP supplies a calling interface; it does not change the source's access permissions or data licence.

## Available in this release

| Source entry | Implemented scope | Geographic scope | Access, licence and practical limit |
|---|---|---|---|
| `bgs_ogc` | Discover BGS OGC collections | Collection-specific | Public beta catalogue. Check each collection's licence, extent and documentation. The catalogue is not permission to reuse every BGS product. [Service](https://ogcapi.bgs.ac.uk/collections?f=html) |
| `bgs_boreholes` | Find borehole index records | Great Britain | Public index under OGL; linked reports/scans and third-party data may have separate rights. Index records do not supply validated SPT/CPT or laboratory parameters. [BGS index](https://www.bgs.ac.uk/datasets/boreholes-index/) |
| `bgs_geology_625k` | Query the 1:625,000 geology collection | United Kingdom | Open overview geology. This mapping scale cannot resolve the stratigraphy or founding depth at a building site. It is a different product from detailed licensed geology. [Product and licence](https://www.bgs.ac.uk/datasets/bgs-geology-625k/) |
| `bgs_landslides` | Discover recorded landslide inventory points | Great Britain | Recorded events, with incompleteness and reporting bias; points do not represent full landslide footprints. The BGS guide states that the data must not be used for insurance purposes. [BGS guide](https://www.bgs.ac.uk/geology-projects/landslides/national-landslide-database/a-guide-to-the-national-landslide-database-on-the-geoindex/) |
| `bgs_ags` | Discover available AGS investigation index records and links | Record-dependent | Donor consent and per-record rights determine availability. This connector does not download, parse or certify all AGS test results. [BGS service](https://www.bgs.ac.uk/technologies/geotechnical-data-services/ags-download-service/) |
| `ea_flood` | Flood-monitoring records and observations exposed by the tools | England service; some water-level records may be from Wales | No key; OGL. A current-warning search or nearby gauge is not a site flood-risk assessment. Observation time can lag retrieval time. [API reference](https://environment.data.gov.uk/flood-monitoring/doc/reference) |
| `ea_hydrology` | Hydrometric station/series discovery and bounded reading queries | EA monitoring service, primarily England | No key; OGL metadata. Preserve units, quality status and datum; surface-water levels do not establish site groundwater depth. [API reference](https://environment.data.gov.uk/hydrology/doc/reference) |
| `planning_data` | Bounded queries of published Planning Data entities | England | Public API. Licence and attribution are dataset-specific; incomplete coverage and duplicate records are possible. [API](https://www.planning.data.gov.uk/docs), [terms](https://www.planning.data.gov.uk/terms-and-conditions) |
| `data_gov_uk` | Dataset catalogue search and metadata | UK publishers; dataset extent varies | No key. The directory describes open and restricted products, and licence metadata may be absent. It does not download arbitrary referenced resources. [API guidance](https://guidance.data.gov.uk/get_data/api_documentation/) |
| `os_open_downloads` | Product inventory, product details and bounded download-link metadata | Product-specific; many OS OpenData products cover GB | No key for OpenData discovery. The inventory can include third-party BGS products, so inspect provider and product terms instead of assigning one OS licence to everything. This does not query local road/building features or ingest national archives. [Specification](https://docs.os.uk/os-apis/accessing-os-apis/os-downloads-api/technical-specification) |
| `dft_traffic` | Annual average daily flow statistics by supported filters | Great Britain | No-auth traffic API. Annual flows include estimates; they are not live counts, axle-load histories or geotechnical design loads. [API documentation](https://roadtraffic.dft.gov.uk/api-documentation), [downloads](https://roadtraffic.dft.gov.uk/downloads) |

All implemented tools perform bounded retrieval or discovery. No source entry means that the entire provider has been integrated. See `README.md` for the exact tool list and `VALIDATION.md` for what was exercised during testing.

## Priority expansion matrix

**Priority 1** means high value for a ground/infrastructure desk study. **Priority 2** adds network, weather or planning context. **Priority 3** requires a specific entitlement or a separate licence agreement. Priorities describe the development sequence, not an assessment of data quality.

| Priority | Source and status | Scope / available interface | Access and constraints |
|---|---|---|---|
| 1 | [NRFA — planned](https://nrfaapps.ceh.ac.uk/nrfa/nrfa-api.html) | UK river-flow stations, catchments and time series; public API | NRFA-specific data terms, attribution and quality metadata. The documentation describes a test service that may change. Daily flow cannot replace sub-hourly design data. |
| 1 | [EA LiDAR — planned](https://environment.data.gov.uk/dataset/13787b9a-26a4-4775-8523-806d13af58fc) | England DTM/DSM tiles, survey metadata, WMS/WCS/WMTS | OGL product; preserve survey date, height datum, CRS and processing history. DTM and DSM differ; pixel size is not accuracy. |
| 1 | [SEPA hydrometry — planned](https://timeseriesdoc.sepa.org.uk/api-documentation/) | Scotland time-series HTTP API | Ordinary access can be used without a key; larger volumes may require one. [SEPA data page](https://www.sepa.org.uk/environment/environmental-data) specifies OGL for hydrometry. |
| 1 | [NRW — planned](https://api-portal.naturalresources.wales/) | Wales river, rainfall, sea-level, flood-warning and forecast APIs | Free registration and API key. Keep forecasts, warnings and observations separate; follow each product's terms. |
| 1 | [DataMapWales — planned](https://datamap.gov.wales/info/what-we-do) | Wales public catalogue, downloads, WMS/WFS | OGL where stated; some data are restricted. Read layer metadata and publisher attribution. |
| 1 | [GSNI / OpenDataNI — planned](https://www.bgs.ac.uk/geology-projects/gsni/) | Northern Ireland geology, Tellus geochemistry, borehole/site records and mineral data | Access, scale and rights differ by product. Some downloadable products are OGL; this is not a blanket licence for every GSNI record. |
| 1 | [ONS geography — planned](https://www.ons.gov.uk/methodology/geography/geographicalproducts/opengeography) | UK and national/subnational boundaries; ArcGIS REST and downloads | OGL plus applicable third-party rights. Boundary vintage and generalisation must match the application. [Licence guidance](https://www.ons.gov.uk/methodology/geography/licences) |
| 1 | [Mining Remediation Authority — discovery only](https://www.gov.uk/guidance/access-coal-mining-information-and-data) | GB coalfield information; selected maps, mine-plan catalogue and licensed records | Free viewing of selected records differs from licensed or charged copies, data and detailed searches. No comprehensive mine-workings connector is included. |
| 2 | [National Highways — planned](https://developer.data.nationalhighways.co.uk/faq) | England strategic roads: closures, signs, speed-managed areas, limits/features and diversion APIs | Registration, subscription and key; current documented limit is 10 calls per key per minute. Not every local road or structural inspection record. |
| 2 | [TfL — planned](https://api.tfl.gov.uk/) | London operational transport API | Obtain an `app_key`; follow TfL terms and [third-party source requirements](https://tfl.gov.uk/corporate/data-sources). |
| 2 | [Network Rail / Rail Data Marketplace — planned](https://www.networkrail.co.uk/who-we-are/transparency-and-ethics/transparency/open-data-feeds/) | GB rail feeds and product-specific infrastructure datasets | Registration and feed terms; [the marketplace](https://www.nationalrail.co.uk/developers/) contains both open and commercial products. Operational feeds do not disclose all earthwork or bridge inspections. |
| 2 | [Street Manager — planned](https://department-for-transport-streetmanager.github.io/street-manager-docs/open-data/) | England open street-work events | Registration plus an HTTPS POST receiver for AWS SNS notifications. Needs persistent ingestion before querying historic/local work records. Operational permit-management access is separate. |
| 2 | [Met Office Weather DataHub — planned](https://datahub.metoffice.gov.uk/docs/getting-started) | UK/global model products depending on subscription | Credentials; free and paid plans with quotas and specific terms. Required attribution is stated in the [service FAQ](https://datahub.metoffice.gov.uk/support/faqs). |
| 2 | [NESO — planned](https://www.neso.energy/data-portal/api-guidance) | Primarily GB electricity-system data; CKAN/datastore APIs | The [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence) applies only where explicitly assigned. Recommended rates differ for metadata and datastore queries. Not a source of every buried distribution cable. |
| 2 | [Spatial Hub Scotland — planned](https://data.spatialhub.scot/faq) | Standardised Scottish local-authority data; WMS/WFS/downloads | Free account/authkey for national open data. Premium and bespoke datasets have separate entitlements; academic access does not automatically allow public redistribution. |
| 2 | [data.gov.scot — planned](https://data.gov.scot/help/technical-support/how-to-access-data-using-the-api) | Scottish catalogue/query/metadata APIs | Inspect each dataset's access and licence. |
| 2 | [SEPA flood mapping — planned](https://www.sepa.org.uk/environment/environmental-data) | Scotland flood layers and Floodline | Some spatial layers are OGL; Floodline API needs an access request. Historic extents, modelled flood zones and alerts are different products. |
| 2 | [ONS statistics — planned](https://developer.ons.gov.uk/) | UK and national/subnational statistics via no-key Beta API | Dataset geography and release/edition matter. Not detailed infrastructure condition data. |
| 2 | [HM Land Registry open products — planned](https://www.gov.uk/government/publications/hm-land-registry-data/public-data) | Mostly England and Wales; Price Paid, INSPIRE and other products | Specified products OGL, with dataset/OS attribution. [INSPIRE](https://use-land-property-data.service.gov.uk/datasets/inspire) polygons are indicative and are not legally definitive boundaries. |
| 2 | Local-authority records — discovery only | Authority-specific drainage, roads, planning and asset information | Many publishers and interfaces, with varying completeness and rights. Search the [national directory](https://guidance.data.gov.uk/get_data/api_documentation/) then confirm at the publisher. |
| 3 | [OS Premium — discovery only](https://docs.os.uk/os-apis/accessing-os-apis/os-downloads-api/technical-specification/data-packages) | Entitled data packages and licensed APIs | Key/OAuth plus appropriate account/product rights; public OpenData access does not grant these rights. |
| 3 | [HMLR licensed API — discovery only](https://use-land-property-data.service.gov.uk/api-documentation) | England and Wales licence-specific property datasets | Account, key, explicit licence acceptance; some products are paid and some include address-use restrictions. |
| 3 | [NUAR — restricted](https://www.nuar.uk/faqs) | England, Wales, Northern Ireland | Authorised eligible users and approved purposes only; no public connector is included. |
| 3 | Scottish Vault — restricted | Scotland's apparatus register | Separate authorised service, [identified by NUAR's official FAQ](https://www.nuar.uk/faqs). No public API entitlement is claimed. |

## Underground utilities: the current boundary

The [current NUAR FAQ](https://www.nuar.uk/faqs) describes an **operational service covering England, Wales and Northern Ireland**. Access remains by invitation to participating asset owners and authorised contractors working for those owners. Data access agreements and protective monitoring apply. The FAQ also describes testing for expanded access, including a sandbox phase that began in August 2026. A test programme or possible future expansion does not grant public access today.

The FAQ lists approved safe-dig/statutory uses and exclusions, including buying or selling land, business-case development and determining network expansion locations. A future authorised connector would need to enforce the user's agreement and permitted purpose. A university affiliation alone is not sufficient evidence of entitlement. Scotland uses its own Vault arrangement.

Consequently, this release can help discover public context around a utility investigation. It cannot provide a complete map of buried fibre, pipes or cables or certify a clear excavation. Public roadworks, network diagrams and historic records are evidence about particular records; they do not establish exact asset position, depth or absence.

## Using these sources in a geotechnical desk study

For a Birmingham site, combine the actual borehole/AGS index, regional geology, recorded ground hazards, relevant hydrometric observations and planning entities while keeping the source of each fact visible. Identify which results are observations, which are mapped interpretations and which are catalogue pointers. An unanswered query must remain a documented data gap.

The most useful next processing additions are bounded CRS transforms and spatial intersections, terrain derivatives with physical units, observation time windows, and extraction from user-supplied, licensed investigation files. Any derivation of soil strength, stiffness or permeability needs its own documented model, calibration basis and uncertainty. A geology label or nearest borehole is insufficient evidence for a characteristic design value.

Across all four nations, retain the dataset licence and attribution, geographic extent, units and CRS, observation/publication dates, query parameters, pagination state and quality flags. A fresh retrieval timestamp does not make the underlying survey recent. A successful API response does not establish completeness or fitness for a design decision.

## Adding a source safely and honestly

1. Resolve its official documentation, actual resource endpoint, geography and product licence.
2. Run a low-volume sample query and record the returned schema, source date, units, pagination and failure behaviour.
3. Implement a named adapter with an explicit source ID, validated parameters and bounded retrieval. Do not expose arbitrary remote URLs or unbounded SQL.
4. Add source-specific attribution and caveats to the response envelope. Preserve unknown or missing licence fields as unknown.
5. Test representative responses, provider failures, limits and the relevant geospatial/time-series edge cases.
6. Mark the source `implemented` only for the scope actually provided; retain other products as planned, discovery-only or restricted.

This registry is a starting catalogue with a maintenance date, not an exhaustive or permanently valid list of every UK dataset. New providers can be added without changing the distinction between discovery, authorised retrieval, processing and engineering interpretation.
