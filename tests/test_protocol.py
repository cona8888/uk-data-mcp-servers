"""Real MCP SDK discovery/calls and subprocess stdio/HTTP handshakes."""

import asyncio
import json
import os
import socket
import sys
from pathlib import Path

import httpx
import httpx2
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from uk_data_mcp.server import create_server
from uk_data_mcp.transport import HttpClient

pytestmark = pytest.mark.asyncio
SOURCE_ROOT = str(Path(__file__).resolve().parents[1] / "src")


async def test_in_memory_mcp_discovers_tools_resources_and_prompt():
    def handler(request):
        pytest.fail("MCP discovery must not contact upstream providers.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        server = create_server(HttpClient(client=raw, rate_interval=0))
        async with Client(server, read_timeout_seconds=10) as client:
            assert client.protocol_version
            tools = (await client.list_tools()).tools
            names = {tool.name for tool in tools}
            assert names >= {
                "list_sources",
                "source_details",
                "bgs_features",
                "ea_stations",
                "hydrology_readings",
                "site_context",
            }
            assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools)
            assert all(
                tool.annotations and tool.annotations.destructive_hint is False for tool in tools
            )
            resources = (await client.list_resources()).resources
            assert {str(resource.uri) for resource in resources} >= {
                "ukdata://sources",
                "ukdata://limitations",
            }
            limitations = await client.read_resource("ukdata://limitations")
            assert any(
                "site-scale" in getattr(content, "text", "") for content in limitations.contents
            )
            prompts = await client.list_prompts()
            assert "preliminary_site_review" in {prompt.name for prompt in prompts.prompts}


async def test_in_memory_tool_call_preserves_structured_evidence_and_errors():
    def handler(request):
        if request.url.path == "/flood-monitoring/id/floods.json":
            return httpx.Response(200, json={"items": [], "meta": {"limit": 20}})
        return httpx.Response(503, json={"error": "temporarily unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        server = create_server(HttpClient(client=raw, rate_interval=0, max_retries=0))
        async with Client(server, read_timeout_seconds=10) as client:
            empty = await client.call_tool("ea_floods", {"latitude": 52.45, "longitude": -1.93})
            assert empty.is_error is False
            assert empty.structured_content["status"] == "empty"
            assert empty.structured_content["provenance"][0]["http_status"] == 200
            assert json.loads(empty.content[0].text)["status"] == "empty"
            failed = await client.call_tool("ea_stations", {"latitude": 52.45, "longitude": -1.93})
            assert failed.is_error is True
            assert failed.structured_content["status"] == "error"
            assert failed.structured_content["error"]["http_status"] == 503


async def test_mcp_invalid_arguments_return_an_error_and_make_no_request():
    def handler(request):
        pytest.fail("Invalid tool input must be rejected before network access.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        server = create_server(HttpClient(client=raw, rate_interval=0))
        async with Client(server, read_timeout_seconds=10) as client:
            result = await client.call_tool(
                "ea_stations", {"latitude": "not-a-number", "longitude": -1.93}
            )
            assert result.is_error is True
            bad_identifier = await client.call_tool("ea_readings", {"station_id": "../../private"})
            assert bad_identifier.is_error is True
            assert bad_identifier.structured_content["error"]["code"] == "invalid_input"


async def test_real_stdio_handshake_and_list_sources():
    # Do not inherit API keys or proxy credentials into the spawned server. The
    # server performs only registry operations in this test, requiring no network.
    environment = {"PYTHONPATH": SOURCE_ROOT}
    # Windows subprocesses need SystemRoot; this path has no service credentials.
    if "SYSTEMROOT" in os.environ:
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "uk_data_mcp", "serve"],
        env=environment,
    )
    async with Client(parameters, read_timeout_seconds=15) as client:
        assert client.protocol_version
        response = await client.call_tool("list_sources", {"implemented_only": True})
        assert response.is_error is False
        assert response.structured_content["count"] > 0
        assert all(
            source["status"] == "implemented" for source in response.structured_content["sources"]
        )
        tools = await client.list_tools()
        assert "site_context" in {tool.name for tool in tools.tools}


async def test_real_loopback_streamable_http_handshake_and_list_sources():
    # Probe TCP readiness rather than GET /mcp: an SSE response may intentionally
    # remain open. Ignore proxy environment variables for this local test.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = {"PYTHONPATH": SOURCE_ROOT}
    if "SYSTEMROOT" in os.environ:
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uk_data_mcp", "serve",
        "--transport", "streamable-http", "--port", str(port),
        env=environment, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(15):
            for _ in range(80):
                if process.returncode is not None:
                    pytest.fail("Streamable HTTP server exited before opening its listening socket.")
                try:
                    _, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.08)
            else:
                pytest.fail("Streamable HTTP server did not become ready within 6.4 seconds.")
            async with httpx2.AsyncClient(trust_env=False, timeout=5) as http:
                transport = streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http)
                async with Client(transport, read_timeout_seconds=5) as client:
                    assert client.protocol_version
                    tools = await client.list_tools()
                    assert "site_context" in {tool.name for tool in tools.tools}
                    result = await client.call_tool("list_sources", {"implemented_only": True})
                    assert result.is_error is False
                    assert result.structured_content["count"] > 0
                    assert all(source["status"] == "implemented" for source in result.structured_content["sources"])
    finally:
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(process.communicate(), timeout=3)
        except TimeoutError:
            process.kill()
            await asyncio.wait_for(process.communicate(), timeout=3)
