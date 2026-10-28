"""BGS adapter contracts; fixtures are synthetic, not site investigations."""

from __future__ import annotations

import httpx
import pytest

from uk_data_mcp.adapters.bgs import BGS_BASE, bgs_collections, bgs_features
from uk_data_mcp.transport import DataAccessError, HttpClient

BBOX = [-1.94, 52.44, -1.92, 52.46]


def feature(identifier: int = 12) -> dict:
    return {
        "type": "Feature",
        "id": identifier,
        "properties": {
            "reference": "SYNTHETIC-TEST",
            "length": 10.0,
            "precision": "± 10 METRES",
            "year_known": None,
            "date_updated": "2020-01-01T00:00:00",
            "scan_url": "https://api.bgs.ac.uk/sobi-scans/v1/borehole/scans/items/12",
        },
        "geometry": {"type": "Point", "coordinates": [-1.93, 52.45]},
    }


@pytest.mark.asyncio
async def test_bgs_uses_crs84_bbox_and_offset_with_compact_output():
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host == "ogcapi.bgs.ac.uk"
        assert request.url.path == "/collections/onshoreboreholeindex/items"
        assert request.url.params["bbox"] == "-1.94,52.44,-1.92,52.46"
        assert request.url.params["skipGeometry"] == "true"
        assert request.url.params["offset"] == "2"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [feature(12), feature(13)],
                "numberMatched": 9,
                "numberReturned": 2,
                "timeStamp": "2026-10-27T11:00:00Z",
                "links": [{"rel": "next", "href": "http://127.0.0.1/do-not-follow"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as underlying:
        result = await bgs_features(
            HttpClient(client=underlying, rate_interval=0),
            "onshoreboreholeindex",
            BBOX,
            limit=2,
            offset=2,
        )
    assert len(seen) == 1  # Does not fetch scans or the upstream next URL.
    assert len(result["data"]) == 2
    assert result["data"][0]["geometry"] is None
    assert result["data"][0]["properties"]["year_known"] is None
    assert result["metadata"]["upstream_timestamp"] == "2026-10-27T11:00:00Z"
    assert result["status"] == "partial"
    assert result["pagination"]["total_reported_by_provider"] == 9
    assert result["pagination"]["next_page"] == {
        "collection": "onshoreboreholeindex",
        "bbox": BBOX,
        "limit": 2,
        "offset": 4,
        "include_geometry": False,
    }


@pytest.mark.asyncio
async def test_bgs_retains_geometry_when_explicitly_requested():
    def handler(request):
        assert request.url.params["skipGeometry"] == "false"
        return httpx.Response(
            200, json={"type": "FeatureCollection", "features": [feature()], "numberMatched": 1}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as underlying:
        result = await bgs_features(
            HttpClient(client=underlying, rate_interval=0),
            "onshoreboreholeindex",
            BBOX,
            include_geometry=True,
        )
    assert result["data"][0]["geometry"]["coordinates"] == [-1.93, 52.45]


@pytest.mark.asyncio
async def test_bgs_empty_result_does_not_imply_absence():
    def handler(request):
        return httpx.Response(
            200, json={"type": "FeatureCollection", "features": [], "numberMatched": 0}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as underlying:
        result = await bgs_features(
            HttpClient(client=underlying, rate_interval=0), "landslideindex", BBOX
        )
    assert result["data"] == []
    assert any("not evidence" in message for message in result["warnings"])
    assert any("insurance" in message for message in result["warnings"])


@pytest.mark.asyncio
async def test_625k_geology_retains_scale_caution():
    def handler(request):
        return httpx.Response(
            200, json={"type": "FeatureCollection", "features": [feature()], "numberMatched": 1}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as underlying:
        result = await bgs_features(
            HttpClient(client=underlying, rate_interval=0), "bgsgeology625kbedrock", BBOX
        )
    assert result["metadata"]["nominal_scale_denominator"] == 625000
    assert any("1:625,000" in message for message in result["warnings"])


@pytest.mark.asyncio
async def test_discovered_collection_is_not_automatically_enabled():
    def handler(request):
        assert str(request.url).startswith(f"{BGS_BASE}/collections?")
        return httpx.Response(
            200,
            json={
                "collections": [
                    {"id": "onshoreboreholeindex", "title": "Boreholes"},
                    {"id": "new-unreviewed", "title": "Other"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as underlying:
        result = await bgs_collections(HttpClient(client=underlying, rate_interval=0))
    assert result["data"][0]["available_in_adapter"] is True
    assert result["data"][1]["available_in_adapter"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"collection": "../../etc/passwd"},
        {"collection": "https://example.test"},
        {"limit": 0},
        {"limit": 101},
        {"limit": True},
        {"offset": -1},
        {"offset": 1.5},
        {"bbox": [52.44, -1.94, 52.46, -1.92]},
        {"bbox": [-3, 52, 1, 53]},
        {"include_geometry": "false"},
    ],
)
async def test_invalid_arguments_never_reach_network(kwargs):
    def handler(request):
        pytest.fail("Invalid parameters must be rejected before any network request")

    arguments = {"collection": "onshoreboreholeindex", "bbox": BBOX, **kwargs}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as underlying:
        with pytest.raises(ValueError):
            await bgs_features(HttpClient(client=underlying, rate_interval=0), **arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"error": "backend unavailable"},
        {"type": "FeatureCollection", "features": ["not-a-feature"]},
    ],
)
async def test_provider_error_body_is_not_reported_as_no_features(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as underlying:
        with pytest.raises(DataAccessError):
            await bgs_features(
                HttpClient(client=underlying, rate_interval=0), "onshoreboreholeindex", BBOX
            )
