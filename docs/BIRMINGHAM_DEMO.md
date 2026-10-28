# Birmingham demonstration: actual retrieved evidence

This example was retrieved on **27 October 2026**, around **11:46 UTC**, for
latitude **52.45**, longitude **−1.93**, with caller-supplied nation **England**.
The coordinate is a demonstration near the University of Birmingham, not a
surveyed construction site. The reproducible response is
[`examples/birmingham_evidence.json`](../examples/birmingham_evidence.json).

## Query and results

The combined request used `radius_km=1` and `limit_per_source=3`. BGS uses an
approximate enclosing rectangle, not a circular search:

```json
[-1.944916492670114, 52.440909090909095, -1.915083507329886, 52.45909090909091]
```

Order is west, south, east, north; all coordinates are longitude/latitude
decimal degrees in CRS84. EA uses its own location filter. Planning Data tests
the specified coordinate only. These are different spatial operations.

| Query | Actual result | Correct interpretation |
|---|---|---|
| BGS SOBI | 423 matching index records reported; first 3 returned | A partial page of candidate records. The first three are not ranked by site relevance or distance. |
| BGS 625K bedrock | 2 mapped units intersect the rectangle | Regional context includes Triassic sandstone/conglomerate and mudstone/siltstone/sandstone units; this does not identify the formation or depth below a foundation. |
| BGS 625K superficial | 2 mapped units intersect the rectangle | Glacial sand/gravel and till are mapped at national scale in the rectangle; small deposits and made ground may be unresolved. |
| BGS landslide index | No returned records | Not evidence of slope safety or a complete negative landslide search. |
| EA flood monitoring stations | No returned stations for this 1 km query | Monitoring coverage is not a groundwater/flood-risk conclusion. A separate 5 km test did return stations. |
| EA current flood alerts/warnings | No returned alerts/warnings | Does not establish a low probability of flooding. |
| EA groundwater stations | Birmingham University station returned | A possible evidence source to examine; its screened interval/aquifer and record history need review. |
| Planning local planning authority | Birmingham LPA, entity 626130 | Identifies the planning authority only. Other constraints were not checked in the combined tool. |

The bundle's overall `status` is `partial`, because the borehole page is
truncated. The individual `empty` responses are explicit. All source URLs,
response hashes, access timestamps, licences and attributions are in the JSON.

The separate smoke-test bbox `[-1.94,52.44,-1.92,52.46]` is smaller and reported
299 borehole records. Those counts are not interchangeable: they refer to
different rectangles.

## A concrete freshness and quality example

A follow-up request for the groundwater measure associated with Birmingham
University returned:

| Field | Source value |
|---|---|
| Station | Birmingham University |
| Latitude / longitude | 52.449027 / −1.932486 |
| Most recent returned reading | 129.14 mAOD |
| Observation date and time | `2026-06-16T09:28:28` (provider did not include a timezone suffix) |
| Per-reading quality | `Unchecked` |
| Retrieval date | 27 October 2026 |

This is an **older recorded groundwater elevation**, not the water level on
27 October 2026 and not a depth below the current ground surface. The measure
ID contains `qualified`, but the reading explicitly says `Unchecked`; the
per-reading flag is retained and highlighted. No conversion to depth below
ground or extrapolation to the demonstration site is performed.

The measure ID is
`0957e811-a4b7-45c1-8b50-2896a1598fe6-gw-dipped-i-mAOD-qualified`.
Its source endpoint is recorded in `followup_groundwater.provenance` in the
example JSON. The source documentation describes units and per-reading quality:
[EA Hydrology API](https://environment.data.gov.uk/hydrology/doc/reference).

## Remaining engineering work

The example does not establish effective-stress friction angle, undrained
strength, stiffness, permeability, design groundwater level, bearing pressure
or utility clearance. These outputs remain explicitly unknown. Relevant logs
would need to be acquired and checked, test results tied to strata and depth,
and the conceptual ground model and investigation plan reviewed by an engineer.

For interpretation and permitted use, consult [BGS 625K](https://www.bgs.ac.uk/datasets/bgs-geology-625k/),
[BGS SOBI](https://www.bgs.ac.uk/datasets/boreholes-index/),
[EA flood-monitoring documentation](https://environment.data.gov.uk/flood-monitoring/doc/reference),
and [Planning Data documentation](https://www.planning.data.gov.uk/docs).
Contains British Geological Survey materials © UKRI 2026. Uses Environment
Agency flood/river-level and hydrology data; full publisher attributions and
dataset-specific planning terms are retained in the JSON.
