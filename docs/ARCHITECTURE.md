# Architecture and extension guide

## Layers

| Layer | Files | Responsibility |
|---|---|---|
| MCP / command line | `server.py`, `cli.py` | Typed tools, resources, prompt, stdio/HTTP, JSON output |
| Application | `service.py` | Shared tool dispatch and bounded combined site queries; errors stay visible |
| Providers | `adapters/` | Validated provider parameters, upstream schemas, licence/freshness/spatial caveats |
| Evidence | `results.py`, `registry.py`, `sources.json` | Provenance, attribution, licence scope, counts, warnings, implementation status |
| Network and coordinates | `transport.py`, `geo.py` | Official API allowlist, byte/time/rate limits, explicit WGS84 inputs |

The single MCP gateway keeps local configuration simple. Providers remain
separate modules and can be split into separate server processes later without
changing their data contracts. The service layer has no model dependency. An
MCP client chooses tools; provider code performs deterministic requests and
validation. This makes retrieval testable independently of an assistant's prose.

## Evidence contract

Provider tools return a JSON envelope with `schema_version`, `source_id`,
`status`, `source`, `retrieved_at_utc`, `query`, `data`, `pagination`,
`provenance`, `metadata`, `warnings` and `use`.

`ok` means the particular API operation succeeded, not that the site is safe.
`empty` is a successful query with no records. `partial` means a page is only
part of the result set or supporting metadata could not be checked. `error`
means the operation failed and includes an error code. MCP marks those tool
responses `isError: true`. The combined site tool exposes per-query statuses
and its separate omitted-query/coverage-gap lists.

Provenance hashes refer to decompressed response bytes before JSON parsing.
They identify what was observed; raw responses are not retained automatically.
This version has no persistent cache. It cannot prove that a provider's record
was true, original or unchanged before retrieval.

## Adding a provider

1. Verify the official endpoint and a small representative response. Read the
   dataset's terms, permitted uses, geographic coverage, dates, units and limits.
2. Add a specific source entry. `planned` means no executable connector exists.
   `discovery_only` does not claim that this package automatically queries it.
3. Add only the required HTTPS host/path to the network allowlist. Avoid generic
   URL tools. Do not follow catalogued resources or provider `next` URLs directly.
4. Implement a typed bounded adapter. Validate response shape and filters. Keep
   source observation metadata unchanged and return an evidence envelope.
5. Add tests for a realistic successful response, empty result, provider failure,
   bad input, incomplete pages and the scientifically important semantics.
6. Register it in the application service and MCP layer, run the stdio protocol
   check, and add a dated low-volume live check.
7. Update the catalogue status and documentation only to the extent validated.

## Future processing layer

PostGIS or DuckDB/GeoParquet can provide local spatial indexing after datasets
have been legitimately downloaded. A borehole processing module should retain
original log references, depth units, datum, location accuracy, test standards,
OCR confidence tied to actual fields, and manual corrections. Parameter
correlations/kriging should be a separate calculation service with explicit
calibration datasets, spatial domains and uncertainty checks. This release does
not implement interpolation, OCR, constitutive parameters or numerical design.

## Operational limits

One second between request starts per host, at most four active HTTP operations
per process, 2 MB per response, bounded redirects/retries and a total operation
deadline. These limits are conservative local defaults, not provider quotas or
a guarantee against shared multi-user load. No continuous crawler or scheduler
is installed. New registered services need per-provider credentials and rate
policies rather than one shared API key.
