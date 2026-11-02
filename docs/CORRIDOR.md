# Civil corridor screening

Submit a proposed road or rail centreline to `corridor_screen` in the existing `uk-civil-data` MCP connection. No keys, new repository, bulk preparation or Git storage of source data are required. The tool queries live services: their servers receive the padded search bounds, not an uploaded project file. Do not use sensitive alignments without permission to disclose that search area.

## Run the Digbeth example

With the project's virtual environment active, run these commands from the repo root:

```bash
git pull --ff-only
python -m pip install .
uk-civil-data call corridor_screen --json-file examples/corridor_birmingham.json > report.json
python scripts/corridor_view.py report.json map.html
```

The last command generates a standalone, offline HTML map with selectable layers and a feature register. Open `map.html` in a browser. For MCP clients, start `uk-civil-data serve` as usual. Example prompt: *Screen this alignment within 250 metres. List the boreholes and mapped bridges, identify intersecting defences, show 2025 injury collision locations, and distinguish the wards crossed from those only inside the buffer. Show gaps before drawing conclusions.*

Copy the example JSON and edit `alignment.coordinates`. Supply 2–256 ordered vertices, max 20 km. Use `[longitude, latitude]` with `input_crs: OGC:CRS84`, or `[easting, northing]` in metres with `EPSG:27700`. The default radius of 250 m applies on **each** side, including circular end caps. Enter `England`, `Wales` or `Scotland`; split cross-border routes. NI needs other national sources and a different spatial implementation. `layers` can select any subset of `boreholes`, `bridges`, `flood_defences`, `collisions`, `communities`.

## What was tested

The hypothetical 873.225 m Birmingham alignment is not a proposed development or a surveyed route. In the [dated live run](https://github.com/cona8888/uk-data-mcp-servers/actions/runs/41370497594) on 2 November 2026 all five candidate scans completed. Published inventories can change. These figures are not golden test expectations.

| Source | Candidates in padded rectangle | Within 250 m | Meaning |
|---|---:|---:|---|
| [BGS SOBI](https://www.bgs.ac.uk/datasets/boreholes-index/) | 130 | 40 | Index records, not 40 independently verified boreholes. The nearest was SP08NE46 at ~14 m, with published ±10 m position precision. |
| [Canal & River Trust](https://www.data.gov.uk/dataset/3bad9280-3167-4a8f-ad12-4fa93297bf51/bridges) | 14 | 5 | Bridge reference points interacting with the Trust network; not all road and rail bridges. |
| [EA AIMS](https://www.data.gov.uk/dataset/cc76738e-fc17-49f9-a216-977c61858dda/aims-spatial-flood-defences-inc-standardised-attributes) | 15 | 14 | Mapped defence records, two touching or crossing the centreline in plan. Not residual flood risk, bank height or structural performance. |
| [DfT STATS19](https://www.gov.uk/government/statistical-data-sets/road-safety-open-data) | 37 | 22 | Geolocated, police-reported injury events in 2025. Not casualty counts or a rate; events on adjoining roads can qualify. |
| [ONS wards, December 2024](https://www.data.gov.uk/dataset/e8493e3d-619e-4362-aa3a-0a3538177da8/wards-december-2024-boundaries-uk-bgc) | 4 | 2 | Bordesley & Highgate contains the example centreline. Nechells enters the buffer only (~229 m away); this is not proof of service to either community. |

## Metric and audit trail

Candidate selection uses a padded bounding rectangle. Inclusion uses the unrounded minimum Euclidean **British National Grid distance** between the complete piecewise-linear alignment and source geometry. Vertices or centroids alone are not used. For SOBI the original published easting/northing is preferred. Other geometries undergo a longitude/latitude to grid transformation. Coordinate operation, scale, generalisation and original survey precision limit positional accuracy, particularly near the threshold. This is a 2-D screening search, not a 3-D clearance or ownership check.

`offset_m` is shortest plan distance. `chainage_m` measures along the ordered alignment to **one** nearest point; where a feature overlaps or intersects multiple times this is not a list of crossings. For wards, `centreline_length_in_area_m` distinguishes a crossed ward from a nearby one. A positive intersection length is not a ridership or economic-benefit measure. Whole-district counts must not be allocated to the corridor on that basis.

`matched_examined` counts matched, uniquely identified located records actually screened, not inventory totals. `limit` caps displayed rows, independently of `candidate_budget` (default 500, max 1,000 per source). Inspect `candidate_scan_complete`, `more_matches_than_shown`, `issues` and each source's status. Upstream errors, duplicate or unlocatable features, or page limits never silently become a fully verified zero. `not_applicable` records out-of-scope sources. Returned records carry source IDs, attribution, provider request URLs, retrieval timestamps, response hashes, and selected published attributes. Maintain the JSON beside any CSV, map or GIS export.

The live workflow retains `report.json`, `features.csv`, `locators.geojson`, and `map.html`. CSV/GeoJSON contain locators, not full footprints. To regenerate the pack: `python scripts/check_corridor.py` then `python scripts/corridor_view.py corridor-evidence/report.json corridor-evidence/map.html`.
