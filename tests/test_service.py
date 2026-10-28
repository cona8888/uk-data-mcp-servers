"""Integration of bounded provider calls, coverage policy and error envelopes."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

from uk_data_mcp.registry import get_source, list_sources
from uk_data_mcp.service import DataService
from uk_data_mcp.transport import HttpClient

pytestmark = pytest.mark.asyncio


async def test_northern_ireland_omits_gb_only_indexes_and_england_services():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "ogcapi.bgs.ac.uk"
        assert any(
            collection in request.url.path
            for collection in ("bgsgeology625kbedrock", "bgsgeology625ksuperficial")
        )
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [],
                "numberMatched": 0,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        async with HttpClient(client=raw, rate_interval=0, max_retries=0) as http:
            result = await DataService(http).call(
                "site_context",
                {
                    "latitude": 54.6,
                    "longitude": -5.93,
                    "nation": "Northern Ireland",
                },
            )
    assert len(requests) == 2
    assert set(result["results"]) == {"bgsgeology625kbedrock", "bgsgeology625ksuperficial"}
    assert result["status"] == "partial"
    assert any("GSNI" in item for item in result["omitted_queries"])
    assert any("England" in item for item in result["omitted_queries"])
    assert result["site"]["nation_basis"] == "caller supplied; not boundary-validated"
    assert all(parameter["value"] is None for parameter in result["design_parameters"].values())


async def test_site_context_keeps_successful_providers_when_one_fails():
    def handler(request):
        if request.url.host == "ogcapi.bgs.ac.uk":
            return httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [],
                    "numberMatched": 0,
                },
            )
        if request.url.path == "/flood-monitoring/id/floods.json":
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        if request.url.host == "environment.data.gov.uk":
            return httpx.Response(200, json={"items": [], "meta": {"limit": 5}})
        if request.url.path == "/entity.json":
            return httpx.Response(
                200,
                json={
                    "entities": [
                        {
                            "entity": 626130,
                            "name": "Birmingham LPA",
                            "dataset": "local-planning-authority",
                        }
                    ],
                    "links": {},
                    "count": 1,
                },
            )
        if request.url.path == "/dataset/local-planning-authority.json":
            return httpx.Response(
                200, json={"dataset": "local-planning-authority", "licence": "ogl3"}
            )
        pytest.fail(f"Unexpected request: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        async with HttpClient(client=raw, rate_interval=0, max_retries=0) as http:
            result = await DataService(http).call(
                "site_context",
                {
                    "latitude": 52.45,
                    "longitude": -1.93,
                    "nation": "England",
                },
            )
    assert result["status"] == "partial"
    assert result["failed_queries"] == ["ea_floods"]
    assert result["results"]["ea_floods"]["error"]["http_status"] == 503
    assert result["results"]["planning_authority"]["data"][0]["name"] == "Birmingham LPA"
    assert result["results"]["bgsgeology625kbedrock"]["status"] == "empty"
    assert all(parameter["value"] is None for parameter in result["design_parameters"].values())


@pytest.mark.parametrize("arguments", [[], "", False, 0, "{}"])
async def test_service_rejects_non_object_arguments_even_if_falsey(arguments):
    async with HttpClient(rate_interval=0) as http:
        with pytest.raises(ValueError, match="JSON object"):
            await DataService(http).call("list_sources", arguments)


async def test_missing_or_extra_provider_arguments_become_invalid_input_envelopes():
    def handler(request):
        pytest.fail("Bad arguments should not contact an upstream provider.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        async with HttpClient(client=raw, rate_interval=0) as http:
            service = DataService(http)
            missing = await service.call("ea_stations", {})
            extra = await service.call(
                "ea_readings", {"station_id": "4039", "url": "https://example.org"}
            )
    assert missing["status"] == extra["status"] == "error"
    assert missing["error"]["code"] == extra["error"]["code"] == "invalid_input"
    assert missing["data"] == extra["data"] == []


async def test_source_catalogue_distinguishes_implementation_from_access_restriction():
    all_records = list_sources()["sources"]
    implemented = list_sources(implemented_only=True)["sources"]
    assert {record["status"] for record in all_records} >= {
        "implemented",
        "planned",
        "restricted",
        "discovery_only",
    }
    assert implemented and all(record["status"] == "implemented" for record in implemented)
    assert get_source("ea_flood")["status"] == "implemented"
    assert get_source("nuar")["status"] == "restricted"
    assert get_source("sepa_hydrometry")["status"] == "planned"
    assert "nuar" not in {record["id"] for record in implemented}
    # A consumer must not be able to mutate the cached provider catalogue.
    detached = get_source("nuar")
    detached["status"] = "implemented"
    assert get_source("nuar")["status"] == "restricted"


async def test_invalid_nation_or_unknown_tool_fails_without_network():
    def handler(request):
        pytest.fail("Unsupported operation must not issue a request.")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        async with HttpClient(client=raw, rate_interval=0) as http:
            service = DataService(http)
            with pytest.raises(ValueError, match="nation"):
                await service.call(
                    "site_context", {"latitude": 52.45, "longitude": -1.93, "nation": "UK"}
                )
            with pytest.raises(ValueError, match="Unknown tool"):
                await service.call("download_arbitrary_url", {"url": "https://example.org"})


@pytest.mark.parametrize("raw_json", ["{not-json", "[]"])
async def test_cli_malformed_or_non_object_json_has_clear_input_error(raw_json):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uk_data_mcp",
        "call",
        "list_sources",
        "--json",
        raw_json,
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
    assert process.returncode == 2
    assert stdout == b""
    assert b"Input error:" in stderr
