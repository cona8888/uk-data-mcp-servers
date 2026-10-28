"""Tests of licence handling, point-query scope and bounded dataset discovery."""

import httpx
import pytest

from uk_data_mcp.adapters.discovery import data_gov_search, planning_entities
from uk_data_mcp.transport import DataAccessError, HttpClient

pytestmark = pytest.mark.asyncio


async def _invoke(handler, function, *args, **kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        async with HttpClient(client=raw, rate_interval=0, max_retries=0) as client:
            return await function(client, *args, **kwargs)


async def test_planning_point_projection_and_dataset_licence_are_explicit():
    paths = []
    attribution = "© Historic England 2026. Contains Ordnance Survey data."

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/entity.json":
            assert request.url.params["dataset"] == "conservation-area"
            assert request.url.params["latitude"] == "52.45"
            assert request.url.params["longitude"] == "-1.93"
            assert "geometry" not in request.url.params.get_list("field")
            assert "entry-date" in request.url.params.get_list("field")
            return httpx.Response(
                200,
                json={
                    "entities": [
                        {
                            "entity": 1,
                            "name": "Example",
                            "dataset": "conservation-area",
                            "geometry": "POLYGON (...)",
                        }
                    ],
                    "count": 3,
                    "links": {"next": "https://evil.example/next"},
                },
            )
        assert request.url.path == "/dataset/conservation-area.json"
        return httpx.Response(
            200,
            json={
                "dataset": "conservation-area",
                "licence": "ogl3",
                "attribution-text": attribution,
                "text": "Incomplete and may contain duplicates.",
            },
        )

    result = await _invoke(handler, planning_entities, "conservation-area", 52.45, -1.93, limit=1)
    assert paths == ["/entity.json", "/dataset/conservation-area.json"]
    assert "geometry" not in result["data"][0]
    assert result["metadata"]["dataset_metadata"]["attribution-text"] == attribution
    assert result["metadata"]["spatial_predicate"] == "intersects_point"
    assert result["pagination"]["next_page"]["offset"] == 1
    assert result["status"] == "partial"


async def test_metadata_failure_does_not_invent_reuse_permission():
    def handler(request):
        if request.url.path == "/entity.json":
            return httpx.Response(200, json={"entities": [], "links": {}, "count": 0})
        return httpx.Response(404, json={"error": "missing metadata"})

    result = await _invoke(handler, planning_entities, "conservation-area", 52.45, -1.93)
    assert result["status"] == "partial"
    assert result["metadata"]["licence_status"] == "unknown_until_dataset_metadata_checked"
    assert any("reuse permission remains unverified" in warning for warning in result["warnings"])


async def test_planning_absence_does_not_clear_site_constraints():
    def handler(request):
        if request.url.path == "/entity.json":
            return httpx.Response(200, json={"entities": [], "links": {}, "count": 0})
        return httpx.Response(200, json={"dataset": "listed-building", "licence": "ogl3"})

    result = await _invoke(handler, planning_entities, "listed-building", 52.45, -1.93)
    assert result["status"] == "empty"
    assert any(
        "does not establish absence of planning constraints" in warning
        for warning in result["warnings"]
    )
    assert any("Point assets" in warning for warning in result["warnings"])


async def test_catalogue_preserves_restricted_access_and_never_downloads_resources():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert request.url.host == "ckan.publishing.service.gov.uk"
        assert request.url.params["q"] == "borehole"
        assert request.url.params["rows"] == "1"
        assert request.url.params["start"] == "4"
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "count": 361,
                    "results": [
                        {
                            "id": "bgs-example",
                            "name": "borehole-notifications",
                            "title": "Borehole Notifications",
                            "isopen": False,
                            "license_id": None,
                            "license_title": None,
                            "metadata_modified": "2026-10-16T13:44:30",
                            "organization": {"name": "bgs", "title": "British Geological Survey"},
                            "extras": [
                                {"key": "access_constraints", "value": "Access restrictions apply."}
                            ],
                            "resources": [
                                {
                                    "id": "r1",
                                    "format": "PDF",
                                    "url": "http://169.254.169.254/latest/meta-data/",
                                }
                            ],
                        }
                    ],
                },
            },
        )

    result = await _invoke(handler, data_gov_search, "borehole", limit=1, offset=4)
    assert len(paths) == 1
    assert result["status"] == "partial"
    assert result["data"][0]["license_id"] is None
    assert result["data"][0]["isopen"] is False
    assert result["data"][0]["reuse_status"] == "restricted_or_unconfirmed_check_publisher_terms"
    assert (
        result["data"][0]["access_and_coverage_metadata"][0]["value"]
        == "Access restrictions apply."
    )
    assert result["metadata"]["resource_urls_followed"] is False
    assert result["pagination"]["next_page"]["offset"] == 5
    assert any("not the observation date" in warning for warning in result["warnings"])


async def test_catalogue_error_is_not_empty_search():
    with pytest.raises(DataAccessError, match="unsuccessful"):
        await _invoke(
            lambda _: httpx.Response(
                200, json={"success": False, "error": {"message": "invalid query"}}
            ),
            data_gov_search,
            "borehole",
        )


@pytest.mark.parametrize(
    "dataset", ["../private", "https://example.com/a", "listed-building?limit=10000"]
)
async def test_dataset_path_injection_rejected(dataset):
    with pytest.raises(ValueError):
        await _invoke(
            lambda _: pytest.fail("Unexpected request"), planning_entities, dataset, 52.45, -1.93
        )


@pytest.mark.parametrize("query", ["", " ", "x" * 501, "borehole\nprivate"])
async def test_invalid_catalogue_queries_rejected(query):
    with pytest.raises(ValueError):
        await _invoke(lambda _: pytest.fail("Unexpected request"), data_gov_search, query)
