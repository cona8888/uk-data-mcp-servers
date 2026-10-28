# Birmingham geotechnical desk study

DRAFT D01 | 28 October 2026 | Public demonstration area | For project scoping and review

Confirm the actual site and proposed works, then review original investigation records and develop a site-specific conceptual ground model before specifying intrusive ground investigation (GI). The retrieved evidence identifies useful records and regional geological context, but leaves the ground conditions and design inputs at the proposed works unresolved.

### Key findings

- Regional BGS mapping returned two Triassic bedrock descriptions and two superficial-deposit descriptions. The 1:625,000 data describe the enclosing search area; no exact-point geological assignment or vertical sequence has been established. [query-001/002; G1]

- Six SOBI borehole index candidates were retrieved, with recorded depths of 4.00 to 18.29 m and approximate distances of 395.5 to 693.5 m from the query point. Original logs and test data have not been interpreted. [query-003/004]

- The provider reported 423 SOBI index matches in the approximate search box. The two retrieved pages contain only six of those matches. Their provider order is not established as distance or relevance order. [query-003/004]

- One nearby EA station returned a groundwater observation of 129.14 mAOD on 16 June 2026, marked Unchecked. It predates the retrieval by 134 calendar days and does not establish site groundwater depth or a design water level. [query-009/011]

- No records were returned by the AGS, landslide, flood-monitoring-station or current-warning searches. Those successful empty queries do not establish absence of investigations, hazards or long-term flood risk. [query-005/008]

### Study basis and review status

The review covers the Groundwork workspace assembled at 19:30:45 UTC on 28 October 2026 for latitude 52.45, longitude -1.93, England, with a nominal 1 km search radius. BGS used an approximate enclosing rectangle. No construction-site boundary, surveyed levels, layout, loads or excavation depths have been supplied.

The run contains 11 query results and 13 HTTP 200 responses: five query results were ok, two were partial and four were empty. Overall status remains partial, with one unresolved index-coverage entry and ten open GI tasks. Query success measures retrieval, not site suitability. All six candidates remain unreviewed; all seven design parameters remain unknown.


<!-- pagebreak -->

## Geological and groundwater findings

### Regional mapped interpretation

| Theme | Returned description | Engineering question |
| --- | --- | --- |
| Bedrock | Triassic rocks undifferentiated: sandstone and conglomerate, interbedded | Where do these materials occur, and what are their weathering, thickness and engineering behaviour? |
| Bedrock | Triassic rocks undifferentiated: mudstone, siltstone and sandstone | How does the material sequence vary across the actual works and relevant depth range? |
| Superficial | Glacial sand and gravel: sand and gravel | Are granular deposits present at the site, and are continuity, density and groundwater conditions relevant? |
| Superficial | Till: diamicton | Are heterogeneous glacial deposits present, and what sampling and testing would characterise them? |

Both geological queries returned two of two reported matches. Geometry was omitted. The data therefore do not demonstrate which unit occupies the query point, the site footprint, a contact depth or a confirmed stratigraphic sequence. Formation-equivalent fields were blank. Source release strings are bedrock '11- 2-2008', version 5.17, and superficial '30- 4-2003', version 1.10; they are release metadata, not confirmed survey dates. [query-001/002]

A working model should test the presence and variability of superficial materials, any made ground identified through site history or walkover, and the weathering and depth of bedrock. None of those components is confirmed at the proposed works by this bundle. Obtain suitably detailed mapping under its applicable terms and reconcile it with original logs and site observations. [G1/G2]

### Groundwater observation and limitations

The Birmingham University station is approximately 200 m from the query point, calculated from the supplied WGS84 coordinates. The latest returned observation is 129.14 mAOD at 09:28:28 on 16 June 2026, with per-reading quality Unchecked. A Qualified series label and 'qualified' identifier do not override that observation flag. The observation is 134 calendar days older than the retrieval. [query-009/011; G3]

mAOD is an elevation relative to Ordnance Datum. The station metadata value datum=135.23 is not established as the site's surveyed ground elevation and must not be used to calculate groundwater depth at the site. Aquifer relevance, local hydraulic conditions, pore pressures and seasonal maxima remain unresolved. Review historical series and determine the need for site monitoring from the proposed works. [query-011]


<!-- pagebreak -->

## Historic investigation records and coverage

| Reference | Index name | Depth m | Year | Distance m | Position precision |
| --- | --- | --- | --- | --- | --- |
| [SP08SE14](https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/305147) | Bechenhurst No 1 Birmingham | 4.00 | Unknown | 670.5 | plus/minus 10 m |
| [SP08SE16](https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/305149) | Bournbrook A Birmingham | 15.00 | Unknown | 487.5 | plus/minus 10 m |
| [SP08SE49](https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/305182) | Bristol Road A Birmingham | 18.29 | Unknown | 395.5 | plus/minus 10 m |
| [SP08SE50](https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/305183) | Bristol Road B Birmingham | 15.24 | Unknown | 439.0 | plus/minus 10 m |
| [SP08SE122](https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/305255) | Edgbaston Park Road 1 | 8.10 | 1989 | 693.5 | plus/minus 10 m |
| [SP08SE123](https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/305256) | Edgbaston Park Road 2 | 8.10 | 1989 | 662.4 | plus/minus 10 m |

Sources: query-003/004. Distances are approximate straight-line distances from the query point using source WGS84 points; they do not include positional uncertainty. All six are inside the nominal radius. Recorded total depth is not evidence of a particular stratum or suitable founding level.

### Record quality and interpretation status

All six have a source position-precision label of plus/minus 10 m and remain unreviewed index candidates. Two Edgbaston Park Road records state investigation year 1989; four records have no known investigation year. The January 2013 update timestamps are index-update dates, not drilling dates. The original scans, investigation methods, recovery, strata, testing and recorded water observations have not been assessed.

Retrieve the original records through their BGS scan links, preserving record identity and underlying-file terms. Use the site boundary, geological setting, purpose, depth coverage and data quality to decide relevance. Bristol Road A/B and Bournbrook A are initial acquisition candidates because they are relatively close and have deeper recorded index lengths; this is an acquisition sequence, not a judgement that they represent the site. Review the northern Edgbaston records for spatial and historical context as well.

### The principal coverage gap

BGS reported 423 matching index features in the enclosing box; offsets 0 and 3 returned six records, with continuation at offset 6. The six are a small provider-order sample and have not been established as the nearest six. The 423 matches are not an exact-circle count, a count of distinct physical investigations or a guarantee of complete archive coverage. [query-003/004]

After defining the site, extend the record search using agreed bounded requests or suitable publisher/GIS tools, target the actual footprint and relevant surrounding ground, and record what remains unsearched. Do not prescribe new borehole locations from the apparent distribution of this six-record sample. The empty AGS query does not remove the need to search for usable investigation files. [query-005; G2]


<!-- pagebreak -->

## Data gaps and review priorities

The table consolidates the ten open Groundwork tasks into work packages. Priorities describe sequence and prerequisites, not assessed hazard likelihood. Closure requires the stated evidence and a recorded reviewer decision.

| Priority | Gap or unresolved question | Evidence required before closure |
| --- | --- | --- |
| P0 | Site scope and proposed works | Confirmed boundary, surveyed levels, layouts, loads, excavation geometry, movement criteria, drainage and investigation objectives. |
| P0 gate | Utilities and investigation access | Current asset-owner information, suitable service locating/survey, permissions, access and an agreed safe method before intrusive work. [G4] |
| P1 | Record coverage and original logs | Relevant additional index coverage from 423 reported matches; original logs/AGS files; documented location, date, purpose, depth and quality review. [query-003/005] |
| P1 | Detailed ground model | Detailed mapping, walkover and reliable logs reconciled into a site-specific model with explicit strata, contacts, variability and remaining questions. |
| P1 | Site history and ground hazards | Historic land use, former structures, remediation and relevant mining/ground-hazard information; contamination questions reviewed through a competent-person preliminary assessment. [G5] |
| P1 | Terrain drainage and neighbouring assets | Topographic information, walkover findings, drainage and adjacent-asset constraints; long-term flood information where relevant. [G6] |
| P1 to P2 | Groundwater conditions | Relevant station/aquifer history and site monitoring where needed, with survey datum, response zones, observation quality and temporal variability justified. |
| P2 to P3 | Engineering parameters and interpretation | Quality-controlled field and laboratory data appropriate to the actual works, plus interpretation of applicability, uncertainty and design values. |

### Constraints absent from the current bundle

The landslide inventory query returned no records; it does not establish stable ground. The current flood-warning query returned no records at retrieval, and the separate flood-monitoring-station query was empty. Neither replaces long-term flood mapping, drainage information or a flood-risk assessment. The Hydrology service returning a groundwater station is compatible with the separate flood-monitoring service returning no stations. [query-006/009; G6]

Planning Data identified Birmingham LPA, entity 626130, reference E60000130. The returned representative point is not a site boundary. This authority query did not assess all planning constraints. Made ground, contamination, mining effects, shrink-swell behaviour, faults, shallow rock and buried utilities have not been established as present or absent by this run. Treat them as questions to resolve where relevant, not as reported site conditions. [query-010; G7]


<!-- pagebreak -->

## Investigation plan before intrusive work

### P0 Define the engineering decisions

The project client and geotechnical designer should confirm the site polygon, proposed development, surveyed levels, layout, loading and serviceability requirements, earthworks, drainage and any excavations or retained structures. Agree the decisions that investigation must support and the consequences of residual uncertainty.

Required output: a controlled site and proposed-works plan, a brief of investigation objectives and an initial constraints register. Do not set exploratory-hole locations, quantities, depths, a foundation solution or a GI cost from the demonstration point alone.

### P1 Complete the desk study and walkover

- Acquire and review the six original logs and expand the relevant archive search within an agreed budget. Compare records against the real site footprint and expected engineering influence area; retain excluded records and reasons.

- Obtain suitably detailed geological mapping and available ground-hazard, historic land-use, mining, remediation, planning, drainage and long-term flood information appropriate to the location and works. Confirm source terms, scales and dates.

- Undertake a walkover to review terrain, surface drainage, vegetation, former structures, obstructions, adjacent assets, access and indications requiring further investigation. Arrange suitable topographic information.

- Coordinate any contamination preliminary risk assessment with a competent person using site history, walkover and potential source-pathway-receptor linkages. Chemical or ground-gas investigation should follow evidenced questions. [G5]

Required output: an updated conceptual ground model, a record-relevance register, unresolved geotechnical and environmental questions, and a preliminary investigation scope. The regional mapping must not be presented as a confirmed vertical site profile.

### Hold point before intrusive investigation

Obtain current service information and suitable utility locating/survey work; confirm landowner permissions, working areas, access, plant constraints and health/environmental controls. Agree a safe method for intrusive work. HSE HSG47 identifies planning, locating and identifying buried services, and safe excavation as core elements of a safe system. Public index data provide no clearance. [G4]

Release criterion: the geotechnical designer has a defined scope and reviewed ground-model questions, and the responsible parties have agreed how access, services and other unresolved constraints will be managed. Record the decision before fieldwork is commissioned.


<!-- pagebreak -->

## Targeted GI monitoring and interpretation

### P2 Design the targeted field investigation

Select methods against the reviewed conceptual ground model and proposed works. The following are conditional options for the GI designer, not a fixed specification:

- Shallow trial pits or suitable sampling methods where safe access and ground conditions permit, to investigate near-surface variability, any fill or obstructions, and samples needed for classification.

- Appropriate boreholes and sampling to investigate deeper strata and the engineering influence zone; consider rock investigation where the verified ground model or works require it.

- Suitable in-situ testing, such as penetration testing, where the materials, access and interpretation basis support it. Confirm sampling quality and the information needed for the actual design decisions.

- Target unresolved changes in strata, proposed structures, excavations and earthworks once their locations are defined. Do not derive a grid, termination depth or investigation spacing from this report.

### P2 Coordinate laboratory work and groundwater monitoring

Schedule classification testing and, where relevant to the actual materials and works, strength, stiffness/compressibility, permeability and chemical testing. Define sample types, stress conditions, quality criteria and the intended interpretation. Coordinate contamination or ground-gas work where the preliminary assessment justifies it; no contamination condition is inferred from the current queries.

Review groundwater station and aquifer relevance and obtain appropriate historical series. Where site information is needed, consider standpipes/piezometers with response zones selected from the verified strata and properly surveyed elevations. The monitoring programme must address the variability relevant to the engineering decision. A duration, installation depth, seasonal maximum or dewatering rate cannot be prescribed from the single nearby observation.

### P3 Interpret evidence and close the remaining questions

Review the factual logs, locations, levels, samples, test results and monitoring quality. Update the conceptual ground model, identify unresolved variability and commission supplementary work where necessary. Record the basis, applicability and uncertainty of any derived design input before it is used.

Release criterion for design: the geotechnical interpretation addresses the proposed works and its critical uncertainties. Friction angle, undrained strength, stiffness, permeability, design groundwater level, allowable bearing pressure and utility clearance remain unknown in this draft. Closing an app task is a workflow record and does not establish one of those values.


<!-- pagebreak -->

## Source register and audit basis

Evidence basis: the frozen workspace generated 28 October 2026 at 19:30:45 UTC. The accompanying evidence JSON retains all query arguments, response timestamps, hashes of decompressed response bytes, source records, metadata, pagination, source terms and warnings. Each query identifier below links to its first recorded provider request; additional metadata requests remain in that JSON.

| Query | Evidence | Status | Returned | Provider request |
| --- | --- | --- | --- | --- |
| query-001 | Regional geology | ok | 2 | [Request](https://ogcapi.bgs.ac.uk/collections/bgsgeology625kbedrock/items?f=json&bbox=-1.944916492670114%2C52.440909090909095%2C-1.915083507329886%2C52.45909090909091&limit=3&offset=0&skipGeometry=true) |
| query-002 | Regional geology | ok | 2 | [Request](https://ogcapi.bgs.ac.uk/collections/bgsgeology625ksuperficial/items?f=json&bbox=-1.944916492670114%2C52.440909090909095%2C-1.915083507329886%2C52.45909090909091&limit=3&offset=0&skipGeometry=true) |
| query-003 | Historic index | partial | 3 | [Request](https://ogcapi.bgs.ac.uk/collections/onshoreboreholeindex/items?f=json&bbox=-1.944916492670114%2C52.440909090909095%2C-1.915083507329886%2C52.45909090909091&limit=3&offset=0&skipGeometry=false) |
| query-004 | Historic index | partial | 3 | [Request](https://ogcapi.bgs.ac.uk/collections/onshoreboreholeindex/items?f=json&bbox=-1.944916492670114%2C52.440909090909095%2C-1.915083507329886%2C52.45909090909091&limit=3&offset=3&skipGeometry=false) |
| query-005 | Historic index | empty | 0 | [Request](https://ogcapi.bgs.ac.uk/collections/agsboreholeindex/items?f=json&bbox=-1.944916492670114%2C52.440909090909095%2C-1.915083507329886%2C52.45909090909091&limit=3&offset=0&skipGeometry=false) |
| query-006 | Landslide index | empty | 0 | [Request](https://ogcapi.bgs.ac.uk/collections/landslideindex/items?f=json&bbox=-1.944916492670114%2C52.440909090909095%2C-1.915083507329886%2C52.45909090909091&limit=3&offset=0&skipGeometry=false) |
| query-007 | EA stations | empty | 0 | [Request](https://environment.data.gov.uk/flood-monitoring/id/stations.json?lat=52.45&long=-1.93&dist=1.0&_limit=3&_offset=0) |
| query-008 | Current warnings | empty | 0 | [Request](https://environment.data.gov.uk/flood-monitoring/id/floods.json?lat=52.45&long=-1.93&dist=1.0&_limit=3&_offset=0&min-severity=3) |
| query-009 | Groundwater stations | ok | 1 | [Request](https://environment.data.gov.uk/hydrology/id/stations.json?lat=52.45&long=-1.93&dist=1.0&_limit=3&_offset=0&observedProperty=groundwaterLevel) |
| query-010 | Planning authority | ok | 1 | [Request](https://www.planning.data.gov.uk/entity.json?dataset=local-planning-authority&latitude=52.45&longitude=-1.93&limit=3&offset=0&field=entity&field=name&field=dataset&field=reference&field=entry-date&field=start-date&field=end-date&field=point) |
| query-011 | Groundwater reading | ok | 1 | [Request](https://environment.data.gov.uk/hydrology/id/measures/0957e811-a4b7-45c1-8b50-2896a1598fe6-gw-dipped-i-mAOD-qualified.json) |

### Attribution and source terms

Contains British Geological Survey materials (c) UKRI 2026. The 625K mapping and open SOBI index have their stated OGL scope; linked scans/reports and donated AGS data can have separate rights. The landslide inventory carries collection-specific terms and an insurance-use restriction. Contains Environment Agency information licensed under the Open Government Licence v3.0.

Planning dataset attribution: Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data (c) Crown copyright and database right 2026. The selected dataset metadata declares ogl3; this does not assign that licence to every Planning Data product. Preserve the complete source-specific notices in the accompanying JSON when reusing data.

### Guidance and supporting references

[G1] [BGS Geology 625K](https://www.bgs.ac.uk/datasets/bgs-geology-625k/). Accessed 28 October 2026.

[G2] [BGS Single Onshore Borehole Index](https://www.bgs.ac.uk/datasets/boreholes-index/). Accessed 28 October 2026.

[G3] [EA Hydrology API reference](https://environment.data.gov.uk/hydrology/doc/reference). Accessed 28 October 2026.

[G4] [HSE HSG47 Avoiding danger from underground services](https://www.hse.gov.uk/pubns/books/hsg47.htm). Accessed 28 October 2026.

[G5] [EA Land Contamination Risk Management Stage 1](https://www.gov.uk/government/publications/land-contamination-risk-management-lcrm/lcrm-stage-1-risk-assessment). Accessed 28 October 2026.

[G6] [GOV UK long term flood risk service](https://www.gov.uk/check-long-term-flood-risk). Accessed 28 October 2026.

[G7] [Planning Data API documentation](https://www.planning.data.gov.uk/docs). Accessed 28 October 2026.

Frozen evidence file: examples/birmingham_report_evidence_2026-10-28.json. SHA-256: a8ccd4e9dd99e1e7d5c32c5b895cef50448f1be28273df6102aa45719f39f2b6. Draft D01 requires project-specific completion and technical review before issue for engineering use.
