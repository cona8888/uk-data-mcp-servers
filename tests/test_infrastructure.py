"""Contracts for infrastructure discovery; all provider data here are synthetic."""

import httpx
import pytest

from uk_data_mcp.adapters.infrastructure import dft_traffic, os_downloads, os_products
from uk_data_mcp.transport import DataAccessError, HttpClient


@pytest.mark.asyncio
async def test_os_product_search_projects_metadata_without_bulk_fetch():
    requests = []
    products = [
        {
            "id": "OpenRoads",
            "name": "OS Open Roads",
            "description": "Road network",
            "downloadsUrl": "http://127.0.0.1/bulk",
            "downloads": [{"large": "do not include"}],
        },
        {"id": "Other", "name": "Other data", "description": "Not relevant"},
    ]

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=products)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        result = await os_products(
            HttpClient(client=upstream, rate_interval=0), query="roads", limit=5
        )
    assert len(requests) == 1
    assert requests[0].url.params["expanded"] == "true"
    assert [row["id"] for row in result["data"]] == ["OpenRoads"]
    assert "downloads" not in result["data"][0]
    assert result["metadata"]["downloaded_dataset_files"] is False


@pytest.mark.asyncio
async def test_os_download_pagination_lists_files_without_fetching_them():
    requests = []
    files = [
        {
            "fileName": f"part-{index}.zip",
            "url": "https://files.example.invalid/large.zip",
            "size": 2_000_000_000,
            "md5": "provider-checksum",
        }
        for index in range(3)
    ]

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=files)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        result = await os_downloads(
            HttpClient(client=upstream, rate_interval=0), "OpenRoads", limit=1, offset=1
        )
    assert len(requests) == 1
    assert result["data"][0]["fileName"] == "part-1.zip"
    assert result["pagination"]["next_page"]["offset"] == 2
    assert result["metadata"]["downloaded_dataset_files"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [None, {"dataProvider": None}])
async def test_null_os_optional_provider_metadata_does_not_crash(metadata):
    def handler(request):
        return httpx.Response(
            200, json=[{"id": "Example", "name": "Example", "thirdPartyInfo": metadata}]
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        result = await os_products(HttpClient(client=upstream, rate_interval=0))
    assert result["data"][0]["id"] == "Example"
    assert isinstance(result["data"][0]["data_provider"], dict)


@pytest.mark.asyncio
async def test_os_invalid_product_id_does_not_reach_network():
    def handler(request):
        pytest.fail("Invalid product identifiers must not cause requests")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(ValueError):
            await os_downloads(HttpClient(client=upstream, rate_interval=0), "../../secret")


@pytest.mark.asyncio
async def test_dft_withholds_wrong_year_response():
    def handler(request):
        assert request.url.params["filter[year]"] == "2024"
        return httpx.Response(
            200, json={"data": [{"year": 2023, "count_point_id": 1, "road_name": "A38"}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError, match="year"):
            await dft_traffic(HttpClient(client=upstream, rate_interval=0), 2024)


@pytest.mark.asyncio
async def test_dft_withholds_wrong_count_point_response():
    def handler(request):
        return httpx.Response(
            200, json={"data": [{"year": 2024, "count_point_id": 999, "road_name": "A38"}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError, match="count point"):
            await dft_traffic(HttpClient(client=upstream, rate_interval=0), 2024, count_point_id=1)


@pytest.mark.asyncio
async def test_dft_withholds_wrong_road_response():
    def handler(request):
        return httpx.Response(
            200, json={"data": [{"year": 2024, "count_point_id": 1, "road_name": "M6"}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError, match="road"):
            await dft_traffic(HttpClient(client=upstream, rate_interval=0), 2024, road_name="A38")


@pytest.mark.asyncio
async def test_dft_preserves_estimation_metadata_and_never_follows_next_link():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "year": 2024,
                        "count_point_id": 1,
                        "road_name": "A38",
                        "all_motor_vehicles": 1000,
                        "estimation_method": "Estimated",
                        "estimation_method_detailed": "Synthetic fixture",
                    }
                ],
                "total": 2,
                "next_page_url": "http://127.0.0.1/do-not-follow",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        result = await dft_traffic(
            HttpClient(client=upstream, rate_interval=0), 2024, road_name="A38", limit=1
        )
    assert len(requests) == 1
    assert result["data"][0]["estimation_method"] == "Estimated"
    assert result["pagination"]["next_page"] == {
        "year": 2024,
        "road_name": "A38",
        "count_point_id": None,
        "limit": 1,
        "page": 2,
    }
    assert "vehicles/day" in result["metadata"]["units"]["all_motor_vehicles"]
