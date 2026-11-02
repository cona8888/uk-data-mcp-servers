# Civil corridor screening

Submit a proposed road or rail centreline to `corridor_screen` in the existing `uk-civil-data` MCP connection. No keys, new repository, bulk preparation or Git storage of source data are required. The tool queries live services: their servers receive the padded search bounds, not an uploaded project file. Do not use sensitive alignments without permission to disclose that search area.

## Run the Digbeth example

With the project's virtual environment active, run these commands from the repo root:

```bash
git pull --ff-only
python -m pip install .
uk-civil-data call corridor_screen --json-file examples/corridor_birmingham.json > report.json
python scripts/corridor_view.py report.json map.html
python -m uk_data_mcp.corridor_schedule report.json chainages.csv
```

Open `map.html` in a browser for a standalone, offline map with selectable layers and a feature register. Open `chainages.csv` for the review schedule. For MCP clients, start `uk-civil-data serve` as usual. Example prompt: *Screen this alignment within 250 metres. List the boreholes and mapped bridges, identify where the route meets flood defences, show 2025 injury collision locations, and distinguish the wards crossed from those only inside the buffer. Show gaps before drawing conclusions.*

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

## Reading the chainage schedule

Chainage is cumulative grid distance from the first alignment vertex. `offset_m` remains the minimum plan distance; `chainage_m` remains one representative nearest location for backwards compatibility. The new `centreline_contacts` block describes **actual contact with the mapped feature**, not the length over which it lies within 250 m. A feature 249 m away has no centreline event.

Each event has a kind and start/end chainages. `point_contact` may be a crossing, tangency or endpoint touch. `line_overlap` is a common segment. `area_interior` and `area_boundary` separate passage through a ward from following its edge. A corner-only touch has no length. Count shared-boundary lengths separately; the same edge can belong to both adjacent wards. Isolated boundary points at the ends of runs are not additional events.

The calculation intersects each directed route segment separately, then merges contiguous intervals of the same kind in chainage space. A later pass through the same physical location is retained. For example, traversing 60 m inside a ward and retracing it gives **120 route-metres**, not a 120 m unique footprint. `centreline_length_in_area_m` now uses traversal length, including boundary runs. Event count and lengths are calculated before the per-feature display cap of 32 events. `truncated` flags omissions; displayed precision is not survey accuracy.

The CSV starts with one `layer_summary` row per requested layer, including failures and empty results. Subsequent rows are ordered by chainage. A `nearest_only` row shows the nearest locator, **not** a crossing. Keep the source JSON alongside the CSV: the CSV contains returned features only, and layer retrieval, display and event limits are independent. Older reports without contact geometry cannot be retrofitted from their nearest points: rerun the query to generate a schedule.

## Metric and audit trail

Candidate selection uses a padded bounding rectangle. Inclusion uses the unrounded minimum Euclidean **British National Grid distance** between the complete piecewise-linear alignment and source geometry. Vertices or centroids alone are not used. For SOBI the original published easting/northing is preferred. Other geometries undergo a longitude/latitude to grid transformation. Coordinate operation, scale, generalisation and original survey precision limit positional accuracy, particularly near the threshold. This is a 2-D screening search, not a 3-D clearance or ownership check.

`matched_examined` counts matched, uniquely identified located records actually screened, not inventory totals. `limit` caps displayed rows, independently of `candidate_budget` (default 500, max 1,000 per source). Inspect `candidate_scan_complete`, `more_matches_than_shown`, `issues` and each source's status. Upstream errors, duplicate or unlocatable features, or page limits never silently become a fully verified zero. `not_applicable` records out-of-scope sources. Returned records carry source IDs, attribution, provider request URLs, retrieval timestamps, response hashes, and selected published attributes. Ward proximity or traversal is not a ridership, accessibility or economic-benefit estimate; do not allocate whole-district counts to the corridor.

The live workflow retains `report.json`, `features.csv`, `locators.geojson`, `map.html`, `chainages.csv` and `chainage-summary.json`. Map points are locators, not full footprints. To regenerate the evidence pack: run `python scripts/check_corridor.py`, `python scripts/check_corridor_chainage.py`, then `python scripts/corridor_view.py corridor-evidence/report.json corridor-evidence/map.html`.
