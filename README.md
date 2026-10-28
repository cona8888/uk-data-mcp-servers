# UK Infrastructure and Ground Data MCP

A working, read-only Python MCP server for discovering and querying UK public
data relevant to infrastructure, geology and preliminary ground investigations.
Version **0.1.0**; sources reviewed **27 October 2026**.

Inspired by [Koomook/data-go-mcp-servers](https://github.com/Koomook/data-go-mcp-servers),
which wraps Korean public APIs in MCP tools. This is an original UK implementation.
The `go` in that reference names `data.go.kr`; this project uses Python.

**15 tools, 2 resources, 1 prompt, 36 source-registry entries.** Twelve provider
tools implement selected operations across seven service families. The other
three tools expose the source registry and combine preliminary site evidence.
Eleven registry entries describe implemented data families; the remaining
entries are explicitly planned, discovery-only or restricted. This is an MVP,
not a complete UK data lake or an engineering design system.

## What works now

| Tools | Data returned | Geographic and practical limits |
|---|---|---|
| `list_sources`, `source_details` | Reviewed provider catalogue, access, licence scope, attribution and limitations | Curated and incomplete; distinguish implemented from planned |
| `bgs_collections` | Live BGS OGC collection discovery | Collections beyond the seven reviewed ones are not silently enabled |
| `bgs_features` | SOBI borehole index, AGS borehole index, landslide index, 625K bedrock/superficial/faults/dykes | Bounding-box candidates; 625K is national/regional geology; SOBI/landslides are GB sources |
| `ea_stations`, `ea_floods`, `ea_readings` | Monitoring stations, active alerts/warnings, latest available readings | England service; current warnings are not flood-risk maps; preserve units and datum |
| `hydrology_stations`, `hydrology_readings` | EA groundwater/river/rainfall station discovery and latest available series readings | Observation times and quality can differ substantially from retrieval time |
| `planning_entities` | Projected Planning Data records intersecting a point, with dataset-specific licence metadata | England; point intersection is not a search of a whole site or nearby point assets |
| `data_gov_search` | Dataset metadata and resource links from the national catalogue | Discovery only; some records describe restricted or licensed datasets |
| `os_products`, `os_downloads` | Product versions, documentation, formats, file sizes and download links | No-key OpenData endpoints; no bulk download or spatial road query |
| `dft_traffic` | Annual average daily traffic flow, optionally by road/count point | Great Britain; annual estimates, not live traffic or pavement design loads |
| `site_context` | Bounded evidence bundle with separate provider outcomes and missing design parameters | Caller supplies nation; England services omitted elsewhere; all reports remain preliminary |

All implemented upstream operations require **no provider API key**. The server
does not call an LLM and needs no AI API key. Your chosen MCP client may have its
own account or model/API costs. Source licences remain independent of the code
licence. See [the source guide](docs/DATA_SOURCES.md).

## Start locally

Requires Python 3.11 or newer. Works with ordinary Python on Windows, macOS and
Linux; Python 3.12 was tested here. Run commands from this directory.

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/uk-data-mcp sources --implemented
.venv/bin/uk-data-mcp tools
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\uk-data-mcp.exe sources --implemented
.venv\Scripts\uk-data-mcp.exe tools
```

The package is supplied as source; it has **not** been published to PyPI. Use
`pip install .` from this folder, not a similarly named package from a registry.
Direct runtime dependencies are pinned to the tested official `mcp==2.3.0`
and `httpx==0.28.1`. `requirements-runtime.txt` locks their tested transitive
dependencies; for that environment install the lock first, then the local
package with `pip install --no-deps .`.

## Try the Birmingham example

The coordinates below identify a demonstration area near the University of
Birmingham; they are not a defined construction site boundary.

```bash
uk-data-mcp brief --latitude 52.45 --longitude -1.93 --nation England --radius-km 1 --limit 3
```

Replace `uk-data-mcp` with the full executable path from the install instructions
if the virtual environment is not activated. Save the output with normal shell
redirection, for example `> birmingham-evidence.json`.

For one query, Bash examples are:

```bash
uk-data-mcp call bgs_features --json '{"collection":"onshoreboreholeindex","bbox":[-1.94,52.44,-1.92,52.46],"limit":5}'
uk-data-mcp call planning_entities --json '{"dataset":"local-planning-authority","latitude":52.45,"longitude":-1.93}'
uk-data-mcp call os_products --json '{"query":"roads"}'
uk-data-mcp call dft_traffic --json '{"year":2024,"road_name":"A38","limit":3}'
```

For Python and Windows-friendly examples without shell JSON quoting, see
[examples/query.py](examples/query.py). An actual evidence snapshot and its
interpretation are included in `examples/birmingham_evidence.json` and
[docs/BIRMINGHAM_DEMO.md](docs/BIRMINGHAM_DEMO.md). Those saved results are dated
examples; run the queries again for fresh retrievals.

## Connect an MCP client

Start the server over standard input/output:

```bash
uk-data-mcp serve
```

It waits for the MCP client. It is normal for no human-readable text to appear.
No public port or hosted service is required for stdio clients.

For a client using the common `mcpServers` JSON format:

```json
{
  "mcpServers": {
    "uk-infrastructure": {
      "command": "/ABSOLUTE/PATH/uk-data-mcp-servers/.venv/bin/python",
      "args": ["-m", "uk_data_mcp", "serve"]
    }
  }
}
```

On Windows use the installed interpreter path, for example
`C:\\Projects\\uk-data-mcp-servers\\.venv\\Scripts\\python.exe`.
Use a full path; GUI applications may not inherit your terminal PATH.
Templates are in [examples/mcp-local.json](examples/mcp-local.json) and
[examples/mcp-docker.json](examples/mcp-docker.json). Apply the template in your
chosen client's own MCP configuration. This package does not automatically
register itself with your ChatGPT account or any other client.

Example prompts after connecting:

- "Find borehole index records within this Birmingham bounding box. Show dates,
  position precision and log links. Explain which records need manual review."
- "For latitude 52.45, longitude -1.93 in England, gather preliminary ground and
  infrastructure evidence. Separate data gaps from empty searches."
- "Which source covers Scottish river levels, and is it implemented here?"
- "Find the OS Open Roads product, its current version and file formats."

## Docker

```bash
docker build -t uk-data-mcp:0.1.0 .
docker run --rm -i uk-data-mcp:0.1.0
```

Use `-i` and **no `-t`** for MCP stdio. The Docker image runs as an unprivileged
user. For local Streamable HTTP:

```bash
docker compose up --build
```

The supplied compose file publishes only `127.0.0.1:8000`; an MCP client can use
`http://127.0.0.1:8000/mcp`. This is an MCP endpoint, not a browser GUI. You can
also run `uk-data-mcp serve --transport streamable-http` directly.

There is no remote user authentication in v0.1. Do not publish this local
configuration as an Internet service. A hosted multi-user deployment needs
HTTPS, authentication/authorization, resource limits and provider credential
separation. See [deployment notes](docs/DEPLOYMENT.md). Docker definitions are
included; whether they were actually built in this session is stated in
[validation](docs/VALIDATION.md).

## How to interpret results

Each provider response includes the request URL, retrieval timestamp, exact
response-byte SHA-256, source attribution/terms, query parameters, returned
record count, pagination, warnings and source observation metadata. Hashes
identify the retrieved bytes; they do not guarantee provider correctness or
future availability. Network failures have `status: error`, while successful
queries with no matching records use `status: empty`.

- **Bbox order:** `[west, south, east, north]`, longitude/latitude decimal degrees
  in OGC CRS84. Point arguments are explicitly `latitude` and `longitude`.
- **National coverage:** UK, GB and England are different. The caller supplies
  `nation` for the combined tool; it is not independently geocoded.
- **Dates:** `retrieved_at_utc` is access time. Record dates describe the data.
- **Units:** preserve source units, quality and vertical datum. mAOD is elevation
  relative to Ordnance Datum; it is not depth below the ground surface.
- **Pages:** a bounded page is not a complete inventory. Use `next_page` arguments
  for the same tool. The server does not crawl subsequent pages automatically.
- **Permissions:** a public catalogue or map does not establish the licence of
  every underlying dataset or linked report.

`site_context` leaves friction angle, undrained strength, stiffness,
permeability, design groundwater level, bearing pressure and utility clearance
as `null` with explanations. It never guesses them from a mapped formation or a
nearby record. This is useful evidence for a desk study, not a Eurocode
compliance calculation, final ground model or safe-to-dig certificate.

## Reliability and development

The HTTP layer permits only reviewed official HTTPS hosts/routes, caps each
response at 2 MB, limits concurrency, spaces starts by one second per provider
host, bounds retries/timeouts, and rejects unexpected formats and unsafe
redirects. Standard managed-network proxy environment settings are respected.
The server never follows resource URLs from dataset descriptions, executes
downloaded instructions, or automatically fetches borehole PDFs and large GIS
files. Retrieved text must still be treated as untrusted by the client.

```bash
python -m pip install '.[dev]'
python -m pytest -q
ruff check .
python scripts/smoke_live.py --output live-checks.json
```

The first two checks are offline and deterministic. The live smoke script is
explicitly opt-in and sends small read-only requests to public providers. It
records failures without converting them to missing hazards. See
[validation evidence](docs/VALIDATION.md), [architecture and extension guide](docs/ARCHITECTURE.md),
[BGS notes](docs/BGS.md), and [EA/planning notes](docs/ENVIRONMENT.md).

## Next development priorities

1. Bring Scotland, Wales and Northern Ireland environmental/ground coverage to
   parity, using SEPA, NRW, GSNI and national planning sources under their terms.
2. Add EA LiDAR/terrain sampling with explicit resolution, datum and survey date,
   and NRFA time-series retrieval with conservative volume limits.
3. Add approved borehole PDF/AGS ingestion with source-level extraction checks,
   units and depth alignment; do not infer design values from OCR alone.
4. Add local spatial indexing, postcode/BNG conversion and exact site-polygon
   intersection. Keep any statistical parameter estimation separate and labelled.
5. Add registered transport/weather services; implement Street Manager as event
   ingestion. Integrate NUAR only through an authorized supported route.
6. Build a map/report GUI on the same evidence service, with an audit trail and
   human review before engineering use.

Code is MIT licensed. Provider data retain their original licences. This is an
independent project, not an official BGS, UK Government, OS or EA service.
