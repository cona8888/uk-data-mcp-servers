# Environment and planning adapters

Checked against official documentation and small live HTTPS requests on 27 October 2026.

## What the adapters retrieve

| Adapter | Data | Coverage and interpretation |
|---|---|---|
| `ea_stations` | Bounded page of monitoring station metadata and measure units | Environment Agency service for England; radius filtering may be approximated upstream by a bounding box |
| `ea_floods` | Active operational alerts/warnings (severity 1–3) near a coordinate | Current feed; absence of a warning is not absence of flood risk |
| `ea_readings` | Most recent available readings for a station's measures | Preserves timestamps, units and datum metadata; latest is not necessarily recent |
| `hydrology_stations` | Nearby EA hydrology stations; defaults to groundwater | A nearby groundwater station can monitor a different aquifer |
| `hydrology_readings` | Latest reading for a specified series plus measure metadata | Keeps per-reading quality even where the measure name says `qualified` |
| `planning_entities` | Selected fields from one planning dataset whose geometries intersect a point | England; not a radius or site-boundary search; incomplete/variable coverage |
| `data_gov_search` | Dataset metadata, licence declarations, resource links and access restrictions | UK catalogue discovery; linked resources are never fetched automatically |

## Public API access and licences

EA endpoints are available without an API key under the Open Government Licence. Flood monitoring requests preserve upstream `meta.licence`; hydrology uses `meta.license`. Include the EA flood API attribution specified by the provider: “this uses Environment Agency flood and river level data from the real-time data API (Beta)”.

Planning Data's dataset-specific JSON metadata supplies the licence and attribution. The adapter retrieves it alongside the point query. Most Planning Data content is OGL, but the service explicitly permits exceptions; the code does not apply a blanket licence. If metadata retrieval fails, the result is `partial` and reuse remains unverified.

The public data.gov.uk catalogue includes restricted datasets. An entry with `isopen=false` or missing licence information does not become open because its metadata is searchable. Retain and review the access constraints, resource licences and publisher terms. `metadata_modified` is the catalogue record's update date, not the observation date.

## Small live checks and their meaning

The EA hydrology service returned a station labelled **Birmingham University**, at latitude 52.449027 and longitude −1.932486, with identifier `0957e811-a4b7-45c1-8b50-2896a1598fe6`. Its dipped-groundwater series is `0957e811-a4b7-45c1-8b50-2896a1598fe6-gw-dipped-i-mAOD-qualified`.

On 27 October 2026, the latest returned observation for that series was **129.14 mAOD on 16 June 2026**, with per-reading quality **Unchecked**. This illustrates why a system must show observation date and quality separately from retrieval time and the measure's `qualified` suffix. It is not a current site groundwater assessment, and mAOD is not depth below ground.

Sources for this recorded check:

- [Station query](https://environment.data.gov.uk/hydrology/id/stations.json?lat=52.45&long=-1.93&dist=20&observedProperty=groundwaterLevel&_limit=1)
- [Measure metadata](https://environment.data.gov.uk/hydrology/id/measures/0957e811-a4b7-45c1-8b50-2896a1598fe6-gw-dipped-i-mAOD-qualified.json)
- [Latest reading](https://environment.data.gov.uk/hydrology/id/measures/0957e811-a4b7-45c1-8b50-2896a1598fe6-gw-dipped-i-mAOD-qualified/readings.json?latest&_limit=2)

The Planning Data query for `local-planning-authority` at latitude 52.45 and longitude −1.93 returned **Birmingham LPA**. A conservation-area point query at the same coordinate returned no entities. That does not determine all constraints on a surrounding site.

These live observations are examples recorded at a point in time; rerun the tools for new queries. Automated tests use synthetic fixtures, not live measurements as permanent expectations.

## Bounded requests

Adapters cap pages at 100 records and searches at 50 km. Full upstream pages are marked potentially partial even if no total count is published. Follow returned `next_page` arguments explicitly to continue; there is no autonomous nationwide crawl. Provider result links and catalogue resource links are treated as data and are not followed.

Planning output omits large polygon geometry and returns a small set of metadata fields. Dataset metadata preserves the source's caveats and attribution. Catalogue notes are capped at 3000 characters and resource lists at 20 per dataset, with explicit truncation flags.

The underlying HTTP layer handles request deadlines, byte limits and request pacing. EA hydrology calls for a measure and its latest reading are sequential, consistent with the provider's fair-use advice.

## Official documentation

- [EA flood-monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference)
- [EA hydrology API](https://environment.data.gov.uk/hydrology/doc/reference)
- [Planning Data API](https://www.planning.data.gov.uk/docs)
- [Planning Data terms](https://www.planning.data.gov.uk/terms-and-conditions)
- [Conservation-area dataset metadata and attribution](https://www.planning.data.gov.uk/dataset/conservation-area)
- [data.gov.uk directory API](https://guidance.data.gov.uk/get_data/api_documentation/)
