# Evidence-integrity milestone: verified results

11 November 2026. Tested implementation: `2291f47e1a23e0b41e0b1f1c10a551f605ecb314`.
Baseline: `c7debb9`. This receipt adds documentation only; it does not change the tested application.

## Changes delivered

The corridor gateway verifies the entire padded search envelope against the ONS December 2024 country polygons before querying asset layers. A wrong nation, unverifiable coverage or a cross-border envelope is an explicit failure, not a zero. This conservative check can reject a valid route close to a coastline or border.

CRS identifiers and pagination now have strict contracts. Contradictory totals, unexpected coordinate labels and ambiguous next-page metadata cannot produce a complete scan. A complete candidate scan is explicitly distinguished from a complete asset inventory.

CSV and HTML exporters share a saved-report validator. They check route length, chainages, offsets, contacts, counts, statuses and truncation. Invalid CSV input leaves a previous export unchanged. Internally consistent historical reports remain labelled as having unverified legacy jurisdiction.

Prepared census, collision and HPI indexes use schema 2, semantic checks and a derived-content SHA-256 separate from the source-file hash. Old or inconsistent caches return an actionable error. A digest stored beside editable content is not authentication; compare with a separately trusted receipt or rebuild.

The new `utility_handoff` tool and vocabulary routing direct gas, electricity and water requests to the evidence holder. Asset positions, network capacity, connection offers and excavation clearance remain unknown. A supplied operator name does not establish site coverage.

## Verified checks

| Check | Result |
|---|---|
| Full Python and MCP tests | 392 passed, zero failed/skipped in the inspected Ubuntu Python 3.12 artifact |
| New stakeholder regressions | 84 passed |
| Frontend validation tests | 12 passed; synthetic DOM, not a human browser trial |
| Cross-platform CI | All five configurations passed: Ubuntu 3.11/3.12/3.13, Windows 3.12 and macOS 3.12 |
| Lint, dependencies and distributions | Passed |
| Directory vocabulary benchmark | 12/12 intended categories, versus 6/12 in the baseline; this is not a general natural-language accuracy score |
| Utility guidance | 12 nation/sector combinations checked; no capacity or clearance invented |
| Official-file cache preparation/readback | Five Census 2021 tables, two annual collision files and one historical HPI release passed schema-2 checks |

## Independent collision comparison

The live MCP benchmark compared published map event IDs with an independent point-to-segment calculation using the official DfT 2025 national CSV. It contains 101,525 rows, of which two lack usable grid coordinates. Neither comparison was display-truncated.

Digbeth: 22 strict collision matches agreed with all 22 reference IDs. The full five-layer query retained 40 borehole index records, five Trust-network bridge points, 14 defence records, 22 collisions and two wards. It also retained ten outside-radius records separately for positional review.

Leeds: 31 strict map-position matches versus 32 native-CSV-position reference matches. The one difference is now visible in the review list: 249.701 m using the CSV coordinates and 250.735 m using map coordinates. It is not silently promoted to a strict match. Five outside-radius collision candidates were retained; the known disagreement was among them. Both comparisons had zero unflagged disagreements. These are checks of two published representations, not surveyed ground truth or national recall estimates.

The successful final run took 2.156 s for Digbeth and 2.231 s for Leeds. Three cold MCP starts took 0.682–0.702 s; 30 warm directory calls had a 1.479 ms median. These are observations from one runner, not throughput or availability guarantees.

One earlier repeat hit an Environment Agency timeout. The gateway preserved an explicit source error and the successful layers in a partial report. The failed run is retained; a single retry passed. No failed query was converted into zero or silently replaced with historical data.

## Update and migrate

With the project environment active, update the main checkout and install from it:

```bash
git switch main
git pull --ff-only
python -m pip install .
```

Preserve existing cache files for audit before rebuilding them, especially where the publisher may revise an edition. Then explicitly prepare the releases you use, for example:

```bash
uk-civil-data prepare ts001 stats19-2025 hpi-2025-01
uk-civil-data call civil_coverage --json '{"query":"sewer capacity","nation":"Wales"}'
uk-civil-data call utility_handoff --json '{"sector":"electricity","nation":"England","purpose":"connection"}'
```

The default prepared cache is `~/.cache/uk-civil-data`, or the directory set by `UK_CIVIL_CACHE`. Groundwork and the original narrower MCP profiles remain available. No new repository or public deployment was created.

See [implementation and limitations](EVIDENCE_INTEGRITY.md) and the [machine-readable receipt](validation/evidence-integrity-2026-11-11.json). Test evidence: [cross-platform CI](https://github.com/cona8888/uk-data-mcp-servers/actions/runs/42940052351), [live acceptance](https://github.com/cona8888/uk-data-mcp-servers/actions/runs/42940052306), [successful evidence artifact](https://github.com/cona8888/uk-data-mcp-servers/actions/runs/42940052306/artifacts/13819804549).
