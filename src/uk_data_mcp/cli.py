"""Cross-platform CLI; tool JSON and MCP wire output never mix with progress logs."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .registry import list_sources
from .service import NATIONS, TOOLS, DataService
from .transport import HttpClient


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


async def _call(name, arguments):
    async with HttpClient() as http:
        return await DataService(http).call(name, arguments)


def save_report(report: dict, output_directory: str) -> dict:
    """Export fixed filenames; user text never becomes a filesystem path."""
    from .reporting import export_csv, render_html, render_markdown, validate_report

    validate_report(report)
    files = {
        "desk-study.json": json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        "desk-study.html": render_html(report),
        "desk-study.md": render_markdown(report),
        "investigations.csv": export_csv(report, "investigations"),
        "gi-gaps.csv": export_csv(report, "gaps"),
    }
    directory = Path(output_directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    return {
        "status": report["status"],
        "output_directory": str(directory),
        "files": list(files),
        "summary": report.get("summary", {}),
    }


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
    call.add_argument(
        "tool", choices=["list_sources", "source_details", "site_context", "desk_study", *TOOLS]
    )
    call.add_argument("--json", default="{}", help="JSON object with tool arguments")
    brief = commands.add_parser("brief", help="Collect a preliminary site evidence bundle as JSON")
    brief.add_argument("--latitude", type=float, required=True)
    brief.add_argument("--longitude", type=float, required=True)
    brief.add_argument("--nation", choices=NATIONS, required=True)
    brief.add_argument("--radius-km", type=float, default=1.0)
    brief.add_argument("--limit", type=int, default=5)
    study = commands.add_parser("desk-study", help="Build a desk study and GI gap register")
    study.add_argument("--latitude", type=float, required=True)
    study.add_argument("--longitude", type=float, required=True)
    study.add_argument("--nation", choices=NATIONS, required=True)
    study.add_argument("--project-name", default="Untitled project")
    study.add_argument(
        "--development-type",
        choices=[
            "general",
            "housing",
            "industrial",
            "solar_battery",
            "basement",
            "corridor",
            "brownfield",
        ],
        default="general",
    )
    study.add_argument("--works-description", default="")
    study.add_argument("--radius-km", type=float, default=1)
    study.add_argument("--limit", type=int, default=10, help="Records per source page, 1..20")
    study.add_argument("--max-borehole-pages", type=int, default=3)
    study.add_argument("--max-groundwater-measures", type=int, default=3)
    study.add_argument("--output-dir", help="Save HTML, JSON, Markdown and two CSV registers")
    report = commands.add_parser("report", help="Export a saved, locally reviewed workspace")
    report.add_argument("--input", required=True, help="Saved desk-study JSON")
    report.add_argument("--output-dir", required=True)
    app = commands.add_parser("app", help="Run the local Groundwork desk-study application")
    app.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "app":
            import uvicorn

            from .webapp import create_app

            if not 1 <= args.port <= 65535:
                parser.error("port must be between 1 and 65535")
            print(f"Groundwork: http://127.0.0.1:{args.port}", flush=True)
            uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
            return
        if args.command == "report":
            path = Path(args.input)
            if path.stat().st_size > 10_000_000:
                raise ValueError("Saved workspace exceeds the 10 MB limit.")
            value = json.loads(path.read_text(encoding="utf-8"))
            emit(save_report(value, args.output_dir))
            return
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
                    "tools": [
                        "list_sources",
                        "source_details",
                        *TOOLS,
                        "site_context",
                        "desk_study",
                    ],
                    "resources": ["ukdata://sources", "ukdata://limitations"],
                }
            )
            return
        if args.command == "desk-study":
            name = "desk_study"
            arguments = {
                "latitude": args.latitude,
                "longitude": args.longitude,
                "nation": args.nation,
                "project_name": args.project_name,
                "development_type": args.development_type,
                "works_description": args.works_description,
                "radius_km": args.radius_km,
                "limit_per_source": args.limit,
                "max_borehole_pages": args.max_borehole_pages,
                "max_groundwater_measures": args.max_groundwater_measures,
            }
        elif args.command == "brief":
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
        if args.command == "desk-study" and args.output_dir:
            emit(save_report(result, args.output_dir))
        else:
            emit(result)
        if result.get("status") == "error":
            raise SystemExit(1)
    except (ValueError, TypeError, OSError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
