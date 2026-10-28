# Existing UK public-data and geospatial MCP projects

Recorded **28 October 2026**, from the project discussion preceding this repository import.

This is a comparison shortlist, not an independent runtime benchmark. The earlier review inspected published descriptions and selected repository files. These third-party servers and hosted endpoints were not run during the import. Recheck their current documentation, code, licence, maintenance and provider terms before adopting them. Tool counts and service availability can change.

## Closest projects

| Project | Documented emphasis in the earlier review | Relevance to this repository |
|---|---|---|
| [pyramid146/geo-mcp](https://github.com/pyramid146/geo-mcp) | BGS geology and nearby boreholes, EA flood information, OS and other onshore/marine spatial context | First comparison for BGS and infrastructure site evidence. Its self-hosting approach includes spatial storage and dataset ingestion; evaluate that against this project's direct, bounded API queries. |
| [HappyMonkeyAI/OpenUKPublicDataMCP](https://github.com/HappyMonkeyAI/OpenUKPublicDataMCP) | Broad UK public data, no-key-first tools, source metadata, optional credentialed integrations and a map explorer | First comparison for a general UK equivalent of the Korean public-data project. The README reviewed earlier did not list a dedicated BGS connector. That is a dated observation, not a permanent exclusion. |
| [chris-page-gov/mcp-geo](https://github.com/chris-page-gov/mcp-geo) | OS, ONS, NOMIS, geographic queries, statistics and map interfaces | Relevant to geographic context and statistics. The reviewed description identifies independent research rather than a government-approved production service. |
| [dwain-barnes/mcp-server-environment-agency](https://github.com/dwain-barnes/mcp-server-environment-agency) | EA monitoring stations, flood warnings, water levels and related readings | Focused environmental connector to compare before adding overlapping EA functions. |
| [CHRISCARLON/os-mcp](https://github.com/CHRISCARLON/os-mcp) | Ordnance Survey Data Hub queries and geographic workflows | Focused OS integration. Its reviewed README requires an OS API key and explicitly disclaims OS endorsement. |

`geo-mcp` and `mcp-geo` are different repositories. No source code from these projects was imported as part of this migration.

## Other routes discussed

[MCPBundles' BGS integration](https://www.mcpbundles.com/skills/bgs-geology) advertises an MCP interface to BGS OGC collections/items. It is a third-party integration, not evidence of an official BGS-operated MCP service. Its hosted endpoint was not independently exercised.

[GovData](https://docs.govdata.dev/) advertises a hosted UK government-data MCP service with an API key. Its documented emphasis in the earlier review was broad government information, rather than detailed ground investigation. Current access, costs and operational guarantees require direct verification.

The original inspiration, [Koomook/data-go-mcp-servers](https://github.com/Koomook/data-go-mcp-servers), demonstrates provider-specific Python MCP wrappers around Korean public APIs. See [NOTICE.md](../NOTICE.md) for this project's attribution and code provenance.

## Implications for development

Connecting UK public APIs or BGS to MCP is not, by itself, a new capability. This project should not claim to be the first such server or a comprehensive connection to all UK data. Start by benchmarking `geo-mcp` and `OpenUKPublicDataMCP` against the intended site-evidence workflow, then reuse compatible components or add only the missing capabilities.

A useful comparison should use identical locations, spatial predicates, dates, page limits and provider products. Check returned records, provenance, units and vertical datum, nation coverage, error handling, response size and deployment effort. A short response or successful request does not establish scientific accuracy or complete coverage.

Potential engineering extensions include reviewed AGS/borehole-log extraction, depth and unit reconciliation, terrain and groundwater context, reproducible evidence packs and explicit uncertainty in any parameter estimation. These are development candidates, not claims that every existing project lacks them.

Check software licensing separately from dataset licensing before reuse. Preserve notices and provider attribution. Do not interpret an open-source connector as permission to redistribute licensed data, access restricted utilities, or certify that excavation is safe.
