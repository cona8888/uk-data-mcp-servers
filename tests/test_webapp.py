"""Browser API boundaries and export round trips without provider requests."""

import asyncio
import copy
import json
from importlib.resources import files

import httpx
import pytest
from starlette.testclient import TestClient

from uk_data_mcp.webapp import create_app


def demo_report():
    return json.loads(
        files("uk_data_mcp").joinpath("demo_desk_study.json").read_text(encoding="utf-8")
    )


def test_dated_demo_and_assets_require_no_live_requests():
    async def forbidden(arguments):
        pytest.fail("Loading the application and dated demo must not contact providers.")

    with TestClient(create_app(forbidden), base_url="http://127.0.0.1") as client:
        for path, content_type in [
            ("/", "text/html"),
            ("/app.js", "text/javascript"),
            ("/styles.css", "text/css"),
        ]:
            response = client.get(path)
            assert response.status_code == 200
            assert content_type in response.headers["content-type"]
            assert response.headers["x-content-type-options"] == "nosniff"
        report = client.get("/api/demo").json()
        assert report["demo"] is True
        assert report["generated_at_utc"].startswith("2026-10-27")
        assert client.get("/api/health").json()["version"] == "0.2.0"


def test_study_validates_input_before_invoking_runner():
    calls = []

    async def runner(arguments):
        calls.append(arguments)
        return demo_report()

    with TestClient(create_app(runner), base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/desk-study", json={"latitude": 52.45, "longitude": -1.93, "nation": "England"}
        )
        assert response.status_code == 200
        assert calls[0]["max_borehole_pages"] == 3
        assert "bgs_bbox_crs84" not in calls[0]
        for invalid in [
            {"latitude": "wrong", "longitude": -1.93, "nation": "England"},
            {"latitude": 52.45, "longitude": -1.93, "nation": "England", "max_borehole_pages": 6},
            {
                "latitude": 52.45,
                "longitude": -1.93,
                "nation": "England",
                "url": "https://example.org",
            },
            [],
        ]:
            assert client.post("/api/desk-study", json=invalid).status_code == 400
        assert len(calls) == 1
        assert (
            client.post(
                "/api/desk-study",
                content='{"latitude": NaN}',
                headers={"Content-Type": "application/json"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/desk-study", content="x" * 32769, headers={"Content-Type": "application/json"}
            ).status_code
            == 400
        )
        assert client.post("/api/desk-study", content="{}").status_code == 400


def test_local_host_and_same_origin_protections():
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
        assert (
            client.post(
                "/api/desk-study", json={}, headers={"Origin": "https://attacker.example"}
            ).status_code
            == 403
        )
        assert client.get("/api/health", headers={"Origin": "http://[invalid"}).status_code == 403
        assert client.get("/api/health", headers={"Origin": "http://127.0.0.1"}).status_code == 200
        assert client.get("/../pyproject.toml").status_code == 404


def test_reviewed_workspace_exports_without_changing_evidence():
    report = copy.deepcopy(demo_report())
    report["investigations"][0]["review"] = {
        "status": "needs_review",
        "notes": "Check original log <script>unsafe()</script>",
    }
    report["gaps"][0]["status"] = "in_progress"
    report["gaps"][0]["notes"] = "Boundary requested"
    with TestClient(create_app(), base_url="http://127.0.0.1") as client:
        response = client.post("/api/export/report", json=report)
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert "Boundary requested" in response.text
        assert "&lt;script&gt;unsafe()&lt;/script&gt;" in response.text
        assert "<script>unsafe()" not in response.text
        report["design_parameters"]["permeability_m_per_s"]["value"] = 1e-5
        assert client.post("/api/export/report", json=report).status_code == 400


@pytest.mark.asyncio
async def test_parallel_live_study_is_rejected_while_current_study_runs():
    started, release = asyncio.Event(), asyncio.Event()

    async def runner(arguments):
        started.set()
        await release.wait()
        return demo_report()

    transport = httpx.ASGITransport(app=create_app(runner))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        args = {"latitude": 52.45, "longitude": -1.93, "nation": "England"}
        first = asyncio.create_task(client.post("/api/desk-study", json=args))
        await asyncio.wait_for(started.wait(), 2)
        second = await client.post("/api/desk-study", json=args)
        assert second.status_code == 409
        release.set()
        assert (await first).status_code == 200


@pytest.mark.parametrize(
    "exception,status", [(RuntimeError("private detail"), 502), (TimeoutError(), 504)]
)
def test_unexpected_runner_failures_return_bounded_public_errors(exception, status):
    async def runner(arguments):
        raise exception

    with TestClient(create_app(runner), base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/desk-study", json={"latitude": 52.45, "longitude": -1.93, "nation": "England"}
        )
        assert response.status_code == status
        assert "private detail" not in response.text
