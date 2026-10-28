# Validation record

A fresh Windows review dated **28 October 2026**, including 86 passing tests,
live provider failures and geotechnical project opportunities, is recorded in
[MCP validation and geotechnical project opportunities](GEOTECHNICAL_REVIEW.md).
The dated record below describes the earlier run.

Date: **27 October 2026**. This record describes software/interface validation,
not the accuracy of geological maps, the completeness of datasets or the safety
of any site.

## Completed checks

| Check | Outcome |
|---|---|
| Python environment | Python 3.12.14; official MCP Python SDK 2.3.0; HTTPX 0.28.1 |
| Offline tests | 86 passing tests, including adapter/error boundaries, source metadata, nation coverage, MCP in-memory, real stdio and local HTTP protocol checks |
| Ruff | Import/lint checks pass; Python files formatted |
| Dependency consistency | `pip check` passes |
| Package build | Source distribution and Python wheel built successfully; source registry included |
| Editable package / CLI | Installed and invoked successfully |
| Real MCP stdio | Official SDK client initialized subprocess, listed tools and queried source registry |
| Real MCP Streamable HTTP | Official SDK client initialized local HTTP server, found 15 tools and 11 implemented source entries; no tool error |
| Live public API smoke suite | 18 checks, zero failures; all 20 HTTP responses returned 200 |
| Birmingham example | Eight component queries plus groundwater follow-up produced an evidence bundle with partial/empty results preserved |
| Docker | Definitions provided and reviewed; image **not built or run**, because Docker was unavailable in the execution environment |
| Other OS versions | No native Windows/macOS execution performed; standard cross-platform Python source and setup instructions supplied |

The HTTP test uses a local-only ephemeral port and does not contact provider
APIs. It disables environment proxies only for that loopback test client;
normal provider requests honor managed-network proxy settings. Protocol tests
need ordinary local process/pipe/socket permissions.

## What the offline tests cover

- Validation of CRS84 bounding boxes, identifiers, radii, page sizes and
  provider-specific inputs; rejection before network access.
- Correct BGS collection routing, offset pagination and compact geometry handling.
- Preservation of observation time, units/datum, per-reading quality and source
  attribution, including a synthetic stale/unchecked groundwater fixture.
- Successful empty responses, malformed payloads and upstream failures as
  distinct outcomes; successful components retained when another provider fails.
- Nation coverage in the combined site tool, explicitly tested with Northern
  Ireland versus England: UK-wide 625K geology is distinct from GB and
  England-only sources.
- Restriction metadata and dataset-specific licences in catalogue/planning output.
- HTTP host/path allowlisting, unsafe redirects, explicit/default ports,
  credential-bearing URLs, timeouts, response byte limits and invalid JSON.
- Respect for numeric and HTTP-date retry instructions; bounded retry attempts.
- OS metadata-only behaviour and DfT checks that requested year, count point and
  road filters are respected before data are returned.
- CLI malformed input and MCP tool/resource/prompt discovery, structured output
  and error signalling through actual protocol clients.

Fixtures are small synthetic API responses. They are not simulated
measurements or invented field investigations presented as real data.

## Live checks and evidence

[`live-checks-2026-10-27.json`](live-checks-2026-10-27.json) records every tool,
argument set, source request URL, retrieval timestamp, exact response hash,
status and returned count. The 18 checks are:

1. BGS collection catalogue.
2. Seven BGS collection queries: SOBI, AGS index, bedrock, superficial, faults,
   dykes and landslides.
3. EA station discovery, active warnings and station readings.
4. Hydrology station discovery and one latest measure reading with unit metadata.
5. Planning Data point query and its dataset attribution/licence metadata.
6. data.gov.uk catalogue search.
7. OS product discovery and product download-list discovery.
8. DfT AADF estimates filtered by year and road.

Two operations perform an extra metadata GET, giving 20 HTTP responses for 18
tool checks. Empty AGS/dyke/landslide/current-warning queries passed as empty,
not as proof those features or hazards do not exist. A successful endpoint
check today does not guarantee future availability; BGS labels its service
BETA and EA documents the absence of a guaranteed safety-critical service level.

The example JSON additionally records the combined 1 km demonstration query
and a groundwater reading with its actual age/quality. Its larger approximate
box is different from the fixed bbox in the smoke suite; their counts differ.
See [Birmingham demonstration](BIRMINGHAM_DEMO.md).

## Reproduce

```bash
python -m pip install '.[dev]'
python -m pytest -q
ruff check .
python -m pip check
python -m build
python scripts/smoke_live.py --output live-checks.json
```

The tests do not make provider network calls. The last command is explicitly
live and can fail if providers, connectivity or schemas change. Record and
investigate those errors rather than replacing them with a blank result.

## Outside this validation

No independent geological validation, professional design certification,
Eurocode check, utility clearance, PDF/AGS extraction, interpolation,
authorization to licensed datasets, cloud deployment or external client-account
installation was performed. No service availability guarantee is asserted.
