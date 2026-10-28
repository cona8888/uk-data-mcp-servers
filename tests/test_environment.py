"""Meaningful provider-boundary tests; no network calls."""

import httpx
import pytest

from uk_data_mcp.adapters.environment import (
    ea_floods,
    ea_readings,
    ea_stations,
    hydrology_readings,
    hydrology_stations,
)
from uk_data_mcp.transport import DataAccessError, HttpClient

pytestmark = pytest.mark.asyncio


async def _invoke(handler, function, *args, **kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        async with HttpClient(client=raw, rate_interval=0, max_retries=0) as client:
            return await function(client, *args, **kwargs)


async def test_station_page_preserves_units_and_does_not_claim_exhaustiveness():
    def handler(request):
        assert request.url.path == "/flood-monitoring/id/stations.json"
        assert request.url.params["lat"] == "52.45"
        assert request.url.params["long"] == "-1.93"
        assert request.url.params["_offset"] == "4"
        return httpx.Response(
            200,
            json={
                "meta": {
                    "licence": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                    "limit": 1,
                },
                "items": [
                    {
                        "stationReference": "4039",
                        "label": "Calthorpe Park",
                        "measures": [{"unitName": "mASD", "qualifier": "Stage"}],
                    }
                ],
            },
        )

    result = await _invoke(handler, ea_stations, 52.45, -1.93, limit=20, offset=4)
    assert result["status"] == "partial"  # upstream cap is smaller than requested
    assert result["pagination"]["next_page"]["offset"] == 5
    assert result["pagination"]["total_reported_by_provider"] is None
    assert result["data"][0]["measures"][0]["unitName"] == "mASD"
    assert result["metadata"]["pagination"]["has_more"] is None
    assert any("bounding box" in warning for warning in result["warnings"])


async def test_empty_current_warnings_are_not_no_flood_risk():
    def handler(request):
        assert request.url.params["min-severity"] == "3"
        return httpx.Response(200, json={"meta": {"limit": 20}, "items": []})

    result = await _invoke(handler, ea_floods, 52.45, -1.93)
    assert result["status"] == "empty"
    assert result["data"] == []
    assert any(
        "does not establish absence of flood risk" in warning for warning in result["warnings"]
    )


async def test_latest_flood_readings_preserve_observation_time_and_datum():
    observation = {
        "dateTime": "2020-01-02T11:15:00Z",
        "value": 0.125,
        "measure": {"unitName": "mASD", "datumType": "datumASD"},
    }

    def handler(request):
        assert request.url.path == "/flood-monitoring/id/stations/4039/readings.json"
        assert request.url.params["_view"] == "full"
        assert "latest" in request.url.params
        return httpx.Response(200, json={"meta": {}, "items": [observation]})

    result = await _invoke(handler, ea_readings, "4039")
    assert result["data"] == [observation]
    assert result["retrieved_at_utc"] != observation["dateTime"]
    assert any("predates retrieval" in warning for warning in result["warnings"])


async def test_hydrology_defaults_to_groundwater_and_preserves_measure_reference():
    def handler(request):
        assert request.url.params["observedProperty"] == "groundwaterLevel"
        return httpx.Response(
            200,
            json={
                "meta": {"license": "OGL3", "limit": 20},
                "items": [
                    {
                        "notation": "station-suid",
                        "label": "Birmingham University",
                        "measures": [
                            {"@id": "http://environment.data.gov.uk/hydrology/id/measures/example"}
                        ],
                    }
                ],
            },
        )

    result = await _invoke(handler, hydrology_stations, 52.45, -1.93)
    assert result["metadata"]["upstream_metadata"]["license"] == "OGL3"
    assert result["data"][0]["measures"][0]["@id"].startswith("http:")
    assert any("different aquifer" in warning for warning in result["warnings"])


async def test_qualified_measure_does_not_overwrite_unchecked_reading():
    paths = []
    observation = {
        "date": "2020-06-16",
        "dateTime": "2020-06-16T09:28:28",
        "value": 129.14,
        "quality": "Unchecked",
    }

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/readings.json"):
            return httpx.Response(
                200, json={"meta": {"licenseName": "OGL 3"}, "items": [observation]}
            )
        return httpx.Response(
            200,
            json={
                "meta": {},
                "items": [
                    {
                        "notation": "example-qualified",
                        "unitName": "mAOD",
                        "observationType": {"label": "Qualified"},
                    }
                ],
            },
        )

    result = await _invoke(handler, hydrology_readings, "example-qualified")
    assert paths == [
        "/hydrology/id/measures/example-qualified.json",
        "/hydrology/id/measures/example-qualified/readings.json",
    ]
    assert result["data"] == [observation]
    assert result["metadata"]["measure"]["unitName"] == "mAOD"
    assert len(result["provenance"]) == 2
    assert any("Unchecked" in warning for warning in result["warnings"])
    assert any("not depth below ground" in warning for warning in result["warnings"])


@pytest.mark.parametrize(
    "station_id", ["../4039", "https://example.org/4039", "4039?x=y", "4039%2fother"]
)
async def test_invalid_identifier_rejected_without_request(station_id):
    def handler(request):
        pytest.fail("Invalid identifier must not trigger a request.")

    with pytest.raises(ValueError):
        await _invoke(handler, ea_readings, station_id)


@pytest.mark.parametrize("radius", [float("nan"), float("inf"), -1, 0, 51, True])
async def test_invalid_radius_rejected(radius):
    with pytest.raises(ValueError):
        await _invoke(
            lambda _: pytest.fail("Unexpected request"), ea_stations, 52.45, -1.93, radius_km=radius
        )


async def test_invalid_upstream_payload_is_error_not_empty_result():
    with pytest.raises(DataAccessError, match="items"):
        await _invoke(
            lambda _: httpx.Response(200, json={"error": "upstream failure"}),
            ea_stations,
            52.45,
            -1.93,
        )
