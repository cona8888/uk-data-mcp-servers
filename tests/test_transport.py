"""Security and failure contracts for the shared public-API transport."""

import hashlib
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from uk_data_mcp.transport import DataAccessError, HttpClient, checked_url

URL = "https://ogcapi.bgs.ac.uk/collections"


@pytest.mark.parametrize(
    "url",
    [
        "http://ogcapi.bgs.ac.uk/collections",
        "https://ogcapi.bgs.ac.uk.attacker.test/collections",
        "https://user:secret@ogcapi.bgs.ac.uk/collections",
        "https://ogcapi.bgs.ac.uk/collections/%2e%2e/private",
    ],
)
def test_disallowed_url_is_rejected_before_network(url):
    with pytest.raises(DataAccessError) as error:
        checked_url(url)
    assert error.value.code == "unsafe_url"


@pytest.mark.asyncio
async def test_redirect_to_loopback_never_gets_requested():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert error.value.code == "unsafe_url"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_relative_redirect_keeps_allowed_origin_and_is_bounded():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(307, headers={"Location": "/collections?f=json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert error.value.code == "redirect"
    assert len(requests) == 3
    assert all(request.url.host == "ogcapi.bgs.ac.uk" for request in requests)


@pytest.mark.asyncio
async def test_content_length_above_cap_is_rejected():
    response = httpx.Response(
        200, content=b"{}", headers={"content-type": "application/json", "content-length": "99"}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0, max_bytes=8).get_json(URL)
    assert error.value.code == "too_large"


@pytest.mark.asyncio
async def test_streamed_body_without_content_length_is_capped():
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"padding":"'
            yield b"01234567890123456789"
            yield b'"}'

    def handler(request):
        return httpx.Response(200, stream=Stream(), headers={"content-type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0, max_bytes=16).get_json(URL)
    assert error.value.code == "too_large"


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b'{"broken":', b'{"value":NaN}'])
async def test_invalid_json_is_a_provider_error_not_empty_data(body):
    response = httpx.Response(200, content=body, headers={"content-type": "application/json"})
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert error.value.code == "invalid_response"


@pytest.mark.asyncio
async def test_html_error_page_is_not_returned_as_data():
    response = httpx.Response(
        200, text="<html>Gateway error</html>", headers={"content-type": "text/html"}
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert error.value.code == "invalid_response"


@pytest.mark.asyncio
async def test_retry_after_http_date_is_not_shortened_to_one_second():
    requests = []
    retry_date = format_datetime(datetime.now(timezone.utc) + timedelta(hours=1), usegmt=True)

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": retry_date})
        return httpx.Response(200, json={"unexpected_early_retry": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert error.value.code == "rate_limited"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_temporary_error_retries_once_when_provider_allows_it():
    requests = []

    def handler(request):
        requests.append(request)
        return (
            httpx.Response(503, headers={"Retry-After": "0"})
            if len(requests) == 1
            else httpx.Response(200, json={"ok": True})
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        result = await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert len(requests) == 2
    assert result.data == {"ok": True}


@pytest.mark.asyncio
async def test_http_timeout_has_explicit_error_code():
    def handler(request):
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        with pytest.raises(DataAccessError) as error:
            await HttpClient(client=upstream, rate_interval=0).get_json(URL)
    assert error.value.code == "timeout"


@pytest.mark.asyncio
async def test_provenance_hashes_actual_response_bytes():
    body = b'{ "ok": true }'

    def handler(request):
        assert request.method == "GET"
        assert request.url.params["f"] == "json"
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        result = await HttpClient(client=upstream, rate_interval=0).get_json(URL, {"f": "json"})
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    assert result.data == {"ok": True}
    assert result.url == URL + "?f=json"
    assert result.retrieved_at.endswith("Z")
