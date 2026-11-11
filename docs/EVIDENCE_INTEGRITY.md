# Civil evidence integrity milestone

Implementation date: 11 November 2026. Baseline reviewed: `c7debb9`.
This milestone improves the trustworthiness of the existing gateway; it does not
add a utility-location service, network-capacity model or excavation approval.

## What is different

### Coverage must be established before asset queries

The gateway submits only the existing padded search envelope, in British
National Grid metres, to the [ONS December 2024 country polygon service](https://www.data.gov.uk/dataset/c0ebe11c-0c81-4eed-81b3-a0394d4116a9/countries-december-2024-boundaries-uk-bgc1).
ArcGIS `esriSpatialRelWithin` asks which country polygon contains the **whole**
query envelope, not its centroid or vertices. The response must identify exactly
one recognised country and agree with the declared nation. Unknown/failed,
conflicting, coastal and cross-border coverage stops asset searches and returns
an error with `results: {}`, not a completed zero.

This is deliberately conservative: the envelope includes radius plus 25 m and
may straddle a boundary although the route itself does not. Narrow or split the
search, or use the appropriate authoritative national workflow. ONS BGC is
20 m generalised and clipped to mean high water; it is not a legal boundary or a
survey. The December 2024 edition is explicit, not described as the latest.
Source-response hashes and the query predicate are retained in `jurisdiction`.
See [Esri spatial relationship definitions](https://developers.arcgis.com/documentation/portal-and-data-services/data-services/feature-services/query-features/).

### A complete candidate scan is not a complete asset inventory

GeoJSON CRS labels now require an exact reviewed identifier. OGC page totals,
returned counts and next-page indicators must agree. Conflicting metadata is a
source error or partial result; successful sources remain available.
Every corridor result explicitly has `inventory_complete: false`.

The strict corridor predicate is unchanged. Candidates within 25 m of its
threshold are flagged for positional review. Outside-radius candidates in that
band appear in `boundary_candidates`, **not** `data` or `matched_examined`.
Their CSV rows are `boundary_review_only`. Original point coordinates / CRS and
position basis are retained. The 25 m band is an engineering review heuristic,
not a statistical confidence bound or a claim that all position errors are
smaller than 25 m. Source precision and coordinate-operation limitations still
apply. This makes a representation-dependent near-threshold exclusion visible
without silently widening the requested corridor.

### Saved reports are validated before export

CSV and HTML exports use the same semantic validator: route length and saved
vertices; finite, bounded chainages and offsets; relation/event/count agreement;
polygon lengths; unique IDs; layer statuses, counts and truncation flags. Invalid
input is rejected before replacing an existing CSV. CSV replacement is atomic.
Legacy schema 1.0 reports can be exported when internally consistent, but are
labelled `unverified_legacy` for jurisdiction. Exporting an old report does not
retroactively perform the new coverage check. New results use schema 1.1.

### Derived caches are checked separately from downloaded sources

Census, collision and prepared HPI indexes now use schema 2 and a canonical
`derived_sha256` in addition to `source_sha256`. Every read checks the derived
digest and relevant semantic constraints. These include non-negative integer
counts (not booleans), collision severity sums and national totals, and
agreement between a census value and its retained published string. Suppressed
values remain null, not zero. HPI prices, months and edition are checked too.

**Existing schema 1 caches must be prepared again.** A rejected cache returns
`invalid_cache`, no values, and the exact operator command. Preserve an old file
for audit before replacing it, particularly when a provider revises a release.

```bash
uk-civil-data prepare ts001 stats19-2025 hpi-2025-01
```

A digest stored in the same editable file is **not authentication**. An actor
who can change both content and digest can reseal a coherent forgery. Compare
`derived_sha256` with a separately trusted receipt, or rebuild from the official
source and compare the retained source hash. The Python `cache_integrity.verify`
function also accepts a separately supplied expected digest; no remote caller
can choose a local manifest path or write a cache through MCP.

### Utility requests lead to an evidence holder, not a fabricated answer

The source directory recognises the 12 benchmark phrases and additional tested
professional wording. `civil_coverage` accepts an optional nation for handoff
instructions, not a blanket geography filter. `utility_handoff` is a new
read-only tool for gas, electricity, water and general utilities. It returns
required information, official routes and missing evidence explicitly as null.

```bash
uk-civil-data call civil_coverage --json '{"query":"sewer capacity","nation":"Wales"}'
uk-civil-data call utility_handoff --json '{"sector":"electricity","nation":"England","purpose":"connection"}'
```

Sewer capacity does not route to the leakage table. Scotland uses Vault / the
Scottish Road Works Register guidance rather than an English service. NUAR
eligibility and permitted use remain provider decisions. The current guidance
was reviewed on 11 November 2026; expansion plans do not grant the user access.
The operator, where supplied, is a user selection, not an automatically verified
service-area match. No passwords, registrations or paid products are requested.

Official handoff references: [NUAR](https://www.nuar.uk/faqs),
[Scottish Vault](https://roadworks.scot/legislation-guidance/commissioner-guidance/community-apparatus-data-vault-frequently-asked),
[Ofwat company directory](https://www.ofwat.gov.uk/households/your-water-company/contact-companies/),
[ENA operator finder](https://www.energynetworks.org/customers/find-my-network-operator),
[NGED indicative opportunity map](https://www.nationalgrid.co.uk/network-opportunity-map),
[HSE HSG47](https://www.hse.gov.uk/pubns/books/hsg47.htm).

## Validation and reproduction

The new deterministic tests are in `tests/test_evidence_integrity.py`. The live
script `scripts/check_evidence_integrity.py` uses the installed server through
an actual MCP stdio subprocess. It checks the vocabulary, 12 nation/sector
handoffs, a deliberately wrong Edinburgh/England declaration, a coastal/border
control, and the Digbeth and Leeds alignments against the DfT national CSV.
Its artifact records the exact implementation commit, environment, durations,
source hash, strict matches and separately flagged coordinate disagreements.
A reference mismatch is not silently reclassified as a strict match.

```bash
python -m pytest -q -m 'not live'
python scripts/check_evidence_integrity.py
```

The first command uses synthetic data. The second contacts the documented
providers and downloads one official DfT annual CSV into memory. Failed checks
are retained in the artifact; a completed workflow is not a safety approval.
No multi-user saturation test or human usability trial is claimed.
