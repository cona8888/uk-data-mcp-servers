# BGS connector

This connector queries the official [BGS OGC API Service BETA](https://ogcapi.bgs.ac.uk/collections?f=html). Seven collections are enabled; other collections can be discovered but require a separate licence and interface review before being enabled.

| Collection ID | Result | Coverage and interpretation |
| --- | --- | --- |
| `onshoreboreholeindex` | Borehole index metadata and source-provided scan/AGS links | Great Britain; preserves dates, unknown values and location precision |
| `agsboreholeindex` | Index of released digital AGS boreholes and links | Donor-dependent coverage; does not retrieve or interpret test results |
| `bgsgeology625kbedrock` | Generalised bedrock units | 1:625,000; regional/national context |
| `bgsgeology625ksuperficial` | Generalised superficial deposits | 1:625,000; regional/national context |
| `bgsgeology625kfaults` | Generalised fault features | 1:625,000; regional/national context |
| `bgsgeology625kdykes` | Generalised dyke features | 1:625,000; regional/national context |
| `landslideindex` | Recorded landslide survey locations | Great Britain; incomplete historical inventory, points are not extents |

## Example

```json
{
  "collection": "onshoreboreholeindex",
  "bbox": [-1.94, 52.44, -1.92, 52.46],
  "limit": 20,
  "offset": 0,
  "include_geometry": true
}
```

The bounding box is `[west, south, east, north]` in longitude/latitude degrees (OGC CRS84). It selects features intersecting a box. It does not establish the ground conditions at a particular foundation or location within that box. Each side is limited to two degrees and each page to 100 records. The returned next-page arguments retain the original query and advance `offset`; provider-supplied URLs are never followed automatically.

Default output omits geometry to keep polygon responses manageable. Ask for `include_geometry=true` to retain original GeoJSON geometry. This does not increase the resolution of the source mapping. The server preserves source properties, including survey dates and position uncertainty, and supplies retrieval time separately.

## What was verified

On 27 October 2026, the completed adapter successfully queried the live collection catalogue and all seven supported feature collections. The catalogue contained 45 collections. The Birmingham box above returned 299 SOBI matches, two bedrock units, two superficial-deposit units, one fault feature and no dyke records at the time of retrieval. Its AGS index query returned no matches; a separate Nottinghamshire box `[-1.0, 53.3, -0.9, 53.4]` returned 12 AGS records. Two-page SOBI tests confirmed `offset=2` advances to distinct records. `skipGeometry=true` was verified and reduced one test bedrock response from approximately 60 kB to 4 kB. These are endpoint verification results, not a ground-investigation assessment, and counts can change.

The upstream service sometimes advertises a next-page link even when its reported total equals the page size. The adapter treats that pagination signal conservatively and may mark a complete-looking page partial. The API labels itself BETA, so upstream availability and schemas can change.

## Access and reuse distinctions

The [SOBI index](https://www.bgs.ac.uk/datasets/boreholes-index/) and [625K geology](https://www.bgs.ac.uk/datasets/bgs-geology-625k/) are available under the Open Government Licence. Their index or mapping licence should not be extended automatically to every third-party report or scan linked from them. This version returns the links without downloading or interpreting their contents. The [AGS service](https://www.bgs.ac.uk/technologies/geotechnical-data-services/ags-download-service/) only releases donated data with the relevant donor consent, and its generated files can contain different identifiers from the originals.

Use the required BGS acknowledgement with reproduced materials: **Contains British Geological Survey materials © UKRI [year]**, using the applicable year. Keep source-specific notices and the original data's licence alongside exported results.

The [National Landslide Database guide](https://www.bgs.ac.uk/geology-projects/landslides/national-landslide-database/a-guide-to-the-national-landslide-database-on-the-geoindex/) explains positional uncertainty, duplicate surveys of one event, incomplete historical coverage and reporting changes. It excludes Northern Ireland, the Isle of Man and the Channel Islands. Its stated restrictions include that the data must not be used for insurance purposes. Absence of a record does not demonstrate absence of a hazard.

## Detailed geology and ground hazards

[BGS 50K WMS](https://www.bgs.ac.uk/technologies/web-map-services-wms/web-map-services-geology-50k/) can be viewed free and its service page states OGL terms for the delivered output. The underlying [50K GIS dataset](https://www.bgs.ac.uk/datasets/bgs-geology-50k/) has separate open/premium access options. This release does not implement 50K WMS feature queries, licensed vector downloads or premium GeoSure. [GeoIndex WMS services](https://www.bgs.ac.uk/technologies/web-map-services-wms/geoindex-wms-services/) provide further borehole, hydrogeology and hazard layers for future adapters.

Mapped geology and nearby borehole records do not directly establish strength, stiffness, permeability, groundwater design levels or other geotechnical design parameters. Those require an appropriate investigation and interpretation workflow.
