# Review fixes: evidence integrity and robust data handling

Implemented against `62fd3e6c75bfd81062646d391b9b255179d8708d` on 29 October 2026.
This change addresses the three reproduced correctness issues and adds offline CI.
It does not change the archived Birmingham observations, the D03 narrative, provider
licences, repository visibility, or any geotechnical design parameter.

## Report integrity

The Python validator is authoritative for CLI exports, HTML exports and browser
workspace loading through the local `/api/validate-report` endpoint. The browser
retains a defensive preflight check and installs a new workspace only after local
backend validation succeeds. This endpoint does not contact providers, write files
or retain a project on the server.

Validation now rejects invalid UK coordinate/radius inputs, unsupported nations or
coordinate systems, invalid assembly timestamps, duplicate record IDs, dangling
source references and conflicting outer/result query statuses. Malformed pagination
is rejected rather than causing an export error. These checks establish internal
consistency, not source authenticity or a verified country boundary.

`prepare_report()` returns a copy with recomputed investigation/query/failure/gap
counts and aggregate retrieval status. It preserves original evidence envelopes,
source hashes, source dates and human review notes. A saved `pagination_followed`
flag is insufficient on its own: a matching retained continuation must exist.
This shares the coverage accounting with study assembly. Known derived counts may
therefore change when an old workspace is loaded; source observations do not.

The schema remains 1.0. Previously accepted, inconsistent hand-edited workspaces
now produce explicit validation errors. Keep the original JSON and correct its
references/statuses from the original evidence; do not invent missing records.
Backend exports continue to tolerate optional null presentation fields where
previously supported. The GUI additionally requires its editable review fields.
No cryptographic authenticity or resistance to deliberate fabrication is claimed.

## Groundwater measurement selection

Selection uses explicit `observedProperty` or `parameterName` metadata, including
EA concept objects/URIs. Neither a station-level groundwater filter, a label, a
measure-ID substring nor the unit `mAOD` alone establishes the measured quantity.

EA station responses can contain compact measure references without those fields.
The composer therefore makes bounded metadata-only requests for unknown series
when confirmed groundwater series do not fill the requested follow-up budget.
The metadata lookup budget is `min(10, 2 * max_groundwater_measures)`; zero follow-up
budget makes zero metadata lookups. All requests are sequential and retain the
existing transport rate limits. Every description request is retained as source
evidence and is distinguished from actual readings. No arbitrary URLs are fetched.

Known non-groundwater series do not consume the readings budget. Conflicting or
still-unknown metadata remains an explicit omission. Confirmed series are selected
in provider order, not ranked as scientifically superior or more current. The
existing `hydrology_readings` backend supports a metadata-only mode for the
composer; the default public MCP reading operation is unchanged. No additional
MCP tool or API key is required.

Returned reading-series metadata and any returned identifier are checked again.
A mismatch is retained in the source register but excluded from groundwater
observations, with an omission explaining why. This interpretation decision does
not relabel a successful HTTP response as a network failure. Dipped/logged,
measured/qualified, dates, datum and per-reading quality remain distinct; a
`qualified` identifier never overrides an `Unchecked` reading.

Provider field reference: https://environment.data.gov.uk/hydrology/doc/reference

## JSON failure isolation

Provider responses, CLI JSON and browser request bodies now share finite JSON
parsing. A quote-aware nesting scan runs before the recursive decoder. Maximum
nesting is 64 levels and maximum traversed values are 500,000; existing byte limits
remain in place. Overflowed numbers such as `1e400`, non-finite constants and
excessively nested/complex payloads are rejected rather than changed to zero/null.

The transport converts these failures to `DataAccessError(code="invalid_response")`.
A failed provider remains an explicit failed evidence query while independently
successful queries can still be retained. Report validation also checks already
parsed Python objects, including cycles and non-finite numbers.

## Automated checks

`.github/workflows/ci.yml` runs on pushes, pull requests and manual dispatch. It
uses read-only repository permissions and commit-pinned actions. Its matrix covers
Linux Python 3.11/3.12/3.13 and Windows/macOS Python 3.12. It runs the full offline
Python suite (including MCP protocol tests), lint, dependency checks, JavaScript
syntax and validation tests, distribution builds and required wheel-file checks.
It records the exact checked-out commit and dependency versions with JUnit results.

There are no scheduled checks, bulk downloads, provider credentials, external LLM
calls or live public-provider tests in this workflow. CI success is evidence about
the tested commit/environment, not validation of field observations or engineering
suitability. Browser validation tests use a synthetic DOM and are not visual or
native browser end-to-end tests.

## Checks performed during this fix

- **138 targeted Python tests passed** on Linux / Python 3.13.5: 15 existing
  transport, 26 existing reporting, 35 desk-study cases, 11 review regressions and
  51 additional hardening cases. The two existing groundwater fixture definitions
  were given explicit synthetic measurement metadata; no assertions were removed.
- The local run of the 35 existing desk-study cases substituted only catalogue
  metadata with a local synthetic fixture, because the full source registry was
  not mounted. Their workflow, records, paging and assertions used repository code.
  The committed CI uses the real packaged registry, not that local substitute.
- **12 JavaScript validation tests passed**, running the actual application source
  in a synthetic DOM harness. JavaScript syntax and Python compilation passed.
- Relevant original files were reconstructed from GitHub and checked against
  their Git blob hashes before editing; the fixes were tested on those files.

This editing environment did not have the MCP SDK, Ruff or build tooling and could
not install the complete pinned environment. The full application suite, complete
lint/build, native Windows/macOS, actual browser E2E, Docker and live providers were
not rerun locally. Historical claims of 158 passing tests are inherited, not a new
result. Use the new GitHub Actions run for commit-linked full-suite results.

The original scanned borehole pages and the manually reviewed D03 narrative were
not reinterpreted, migrated or independently revalidated in this change.
