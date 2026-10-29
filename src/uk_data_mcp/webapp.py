"""Loopback-only browser interface; the live workflow runs through the MCP SDK."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from importlib.resources import files
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from . import __version__
from .json_safety import loads_json

INPUT_FIELDS = {
    "latitude",
    "longitude",
    "nation",
    "project_name",
    "development_type",
    "works_description",
    "radius_km",
    "limit_per_source",
    "max_borehole_pages",
    "max_groundwater_measures",
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


async def _json_body(request: Request, maximum: int) -> dict:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise ValueError("Send an application/json request.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum:
            raise ValueError(f"Request exceeds the {maximum:,} byte limit.")
    try:
        value = loads_json(body)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Request must contain valid finite JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Request must contain a JSON object.")
    return value


async def _run_through_mcp(arguments: dict) -> dict:
    from mcp import Client

    from .server import create_server

    async with Client(create_server(), read_timeout_seconds=610) as client:
        result = await client.call_tool("desk_study", arguments)
        value = result.structured_content
        if not isinstance(value, dict) or value.get("kind") != "geotechnical_desk_study":
            raise RuntimeError("MCP did not return a desk-study report.")
        return value


def create_app(run_study: Callable[[dict], Awaitable[dict]] | None = None) -> Starlette:
    """No server-side project storage. Review edits and downloads stay in the browser."""
    runner = run_study or _run_through_mcp
    study_lock = asyncio.Lock()

    async def static_asset(request: Request) -> Response:
        name = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}[
            request.url.path
        ]
        media_type = {
            "index.html": "text/html",
            "app.js": "text/javascript",
            "styles.css": "text/css",
        }[name]
        return Response(
            files("uk_data_mcp").joinpath("web", name).read_bytes(), media_type=media_type
        )

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok", "version": __version__, "mode": "local"})

    async def demo(request: Request) -> Response:
        resource = files("uk_data_mcp").joinpath("demo_desk_study.json")
        if not resource.is_file():
            return JSONResponse({"error": "The bundled example is unavailable."}, status_code=503)
        return Response(resource.read_bytes(), media_type="application/json")

    async def desk_study(request: Request) -> Response:
        from .deskstudy import validate_request

        try:
            payload = await _json_body(request, 32_768)
            if set(payload) - INPUT_FIELDS:
                raise ValueError("Unknown desk-study fields were supplied.")
            normalized = validate_request(**payload)
            arguments = {key: value for key, value in normalized.items() if key in INPUT_FIELDS}
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if study_lock.locked():
            return JSONResponse(
                {"error": "A study is already running. Wait for it to finish."}, status_code=409
            )
        async with study_lock:
            try:
                async with asyncio.timeout(600):
                    value = await runner(arguments)
                return JSONResponse(value)
            except TimeoutError:
                return JSONResponse(
                    {"error": "The workflow exceeded ten minutes. Try a smaller page budget."},
                    status_code=504,
                )
            except Exception:
                return JSONResponse(
                    {
                        "error": "The MCP workflow did not complete. Check the local server and retry."
                    },
                    status_code=502,
                )

    async def validate_workspace(request: Request) -> Response:
        from .reporting import prepare_report

        try:
            report = await _json_body(request, 10_000_000)
            prepared = prepare_report(report)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        # Local validation only: no provider calls, disk writes or remote storage.
        return JSONResponse(prepared)

    async def export_report(request: Request) -> Response:
        from .reporting import render_html

        try:
            report = await _json_body(request, 10_000_000)
            rendered = render_html(report)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return Response(
            rendered,
            media_type="text/html",
            headers={"Content-Disposition": 'attachment; filename="desk-study.html"'},
        )

    app = Starlette(
        routes=[
            Route("/", static_asset),
            Route("/app.js", static_asset),
            Route("/styles.css", static_asset),
            Route("/api/health", health),
            Route("/api/demo", demo),
            Route("/api/desk-study", desk_study, methods=["POST"]),
            Route("/api/validate-report", validate_workspace, methods=["POST"]),
            Route("/api/export/report", export_report, methods=["POST"]),
        ],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])],
    )

    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            try:
                parsed = urlsplit(origin)
            except ValueError:
                return JSONResponse({"error": "Invalid request origin."}, status_code=403)
            if (
                parsed.scheme != request.url.scheme
                or parsed.netloc != request.headers.get("host", "")
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                return JSONResponse(
                    {"error": "Same-origin requests are required."}, status_code=403
                )
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.add_middleware(BaseHTTPMiddleware, dispatch=local_requests)
    return app
