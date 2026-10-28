"""Cross-platform CLI; tool JSON and MCP wire output never mix with progress logs."""

import argparse
import asyncio
import json
import sys

from . import __version__
from .registry import list_sources
from .service import NATIONS, TOOLS, DataService
from .transport import HttpClient


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


async def _call(name, arguments):
    async with HttpClient() as http:
        return await DataService(http).call(name, arguments)


def main():
    parser = argparse.ArgumentParser(description="UK public-data MCP server and bounded query CLI")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run MCP (stdio by default)")
    serve.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    serve.add_argument(
        "--host",
        choices=["127.0.0.1", "0.0.0.0"],
        default="127.0.0.1",
        help="Use 0.0.0.0 only inside the supplied Docker container; local deployment has no authentication",
    )
    serve.add_argument("--port", type=int, default=8000)
    sources = commands.add_parser("sources", help="Show the reviewed source registry")
    sources.add_argument("query", nargs="?", default="")
    sources.add_argument("--implemented", action="store_true")
    commands.add_parser("tools", help="List callable tools")
    call = commands.add_parser("call", help="Invoke one tool with a JSON argument object")
    call.add_argument("tool", choices=["list_sources", "source_details", "site_context", *TOOLS])
    call.add_argument("--json", default="{}", help="JSON object with tool arguments")
    brief = commands.add_parser("brief", help="Collect a preliminary site evidence bundle as JSON")
    brief.add_argument("--latitude", type=float, required=True)
    brief.add_argument("--longitude", type=float, required=True)
    brief.add_argument("--nation", choices=NATIONS, required=True)
    brief.add_argument("--radius-km", type=float, default=1.0)
    brief.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            from mcp.server.transport_security import TransportSecuritySettings

            from .server import mcp

            if not 1 <= args.port <= 65535:
                parser.error("port must be between 1 and 65535")
            if args.transport == "stdio":
                mcp.run(transport="stdio")
            else:
                mcp.run(
                    transport="streamable-http",
                    host=args.host,
                    port=args.port,
                    json_response=True,
                    stateless_http=True,
                    max_request_body_size=32768,
                    transport_security=TransportSecuritySettings(
                        enable_dns_rebinding_protection=True,
                        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
                        allowed_origins=[
                            "http://127.0.0.1:*",
                            "http://localhost:*",
                            "http://[::1]:*",
                        ],
                    ),
                )
            return
        if args.command == "sources":
            emit(list_sources(args.query, args.implemented))
            return
        if args.command == "tools":
            emit(
                {
                    "tools": ["list_sources", "source_details", *TOOLS, "site_context"],
                    "resources": ["ukdata://sources", "ukdata://limitations"],
                }
            )
            return
        if args.command == "brief":
            name = "site_context"
            arguments = {
                "latitude": args.latitude,
                "longitude": args.longitude,
                "nation": args.nation,
                "radius_km": args.radius_km,
                "limit_per_source": args.limit,
            }
        else:
            name, arguments = args.tool, json.loads(args.json)
            if not isinstance(arguments, dict):
                raise ValueError("--json must contain an object, not a list or string.")
        result = asyncio.run(_call(name, arguments))
        emit(result)
        if result.get("status") == "error":
            raise SystemExit(1)
    except (ValueError, TypeError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
