"""Bounded GETs to reviewed public APIs. No arbitrary URLs or file downloads."""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from . import __version__
from .json_safety import loads_json

ALLOWED_PATHS = {
    "ogcapi.bgs.ac.uk": ("/collections",),
    "environment.data.gov.uk": ("/flood-monitoring", "/hydrology"),
    "www.planning.data.gov.uk": ("/entity", "/dataset"),
    "ckan.publishing.service.gov.uk": ("/api/3/action/package_search", "/api/action/package_search"),
    "data.gov.uk": ("/api/3/action/package_search", "/api/action/package_search"),
    "api.os.uk": ("/downloads/v1/products",),
    "roadtraffic.dft.gov.uk": ("/api/",),
}
LEAKAGE_PATH = (
    "/government/publications/water-resources-2024-2025-analysis-of-the-water-industrys-annual-water-resources-performance"
    "/water-resources-2024-to-2025-analysis-of-the-water-industrys-annual-water-resources-performance"
)
# Opt-in, exact routes. The existing Groundwork client retains its original allowlist.
PUBLIC_EXACT = {
    "www.gov.uk": {"/api/search.json", "/api/content" + LEAKAGE_PATH},
    "api.beta.ons.gov.uk": {"/v1/search", "/v1/data"},
    "ckan.publishing.service.gov.uk": {"/api/3/action/package_show", "/api/action/package_show"},
    "data.gov.uk": {"/api/3/action/package_show", "/api/action/package_show"},
    "landregistry.data.gov.uk": {"/data/ukhpi.json"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DataAccessError(RuntimeError):
    def __init__(self, message: str, *, code: str = "upstream_error", url: str | None = None,
                 status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.url = url
        self.status_code = status_code


@dataclass(frozen=True)
class FetchResult:
    data: Any
    url: str
    retrieved_at: str
    sha256: str
    content_type: str = "application/json"
    status_code: int = 200

    def provenance(self) -> dict:
        return {"url": self.url, "retrieved_at_utc": self.retrieved_at,
                "response_sha256": self.sha256, "content_type": self.content_type,
                "http_status": self.status_code}


def checked_url(url: str, *, public_data: bool = False) -> str:
    try:
        parts = urlsplit(str(url))
        port = parts.port
    except ValueError as exc:
        raise DataAccessError("Invalid API URL.", code="unsafe_url") from exc
    host = parts.hostname
    if (parts.scheme != "https" or not host or port not in (None, 443)
        or parts.username is not None or parts.password is not None or parts.fragment
        or (host not in ALLOWED_PATHS and not (public_data and host in PUBLIC_EXACT))):
        raise DataAccessError("URL is outside the approved HTTPS public API origins.", code="unsafe_url")
    prefixes = ALLOWED_PATHS.get(host, ())
    exact = public_data and parts.path in PUBLIC_EXACT.get(host, ())
    if not exact and not any(parts.path == p or parts.path.startswith(p + "/")
                             or parts.path.startswith(p + ".")
                             or (p.endswith("/") and parts.path.startswith(p)) for p in prefixes):
        raise DataAccessError("URL path is outside the approved public API routes.", code="unsafe_url")
    if any(c in parts.path.lower() for c in ("..", "%2e", "%2f", "%5c", "\\")):
        raise DataAccessError("Encoded or parent paths are not permitted.", code="unsafe_url")
    return str(url)


class HttpClient:
    def __init__(self, *, client: httpx.AsyncClient | None = None, rate_interval: float = 1.0,
                 max_bytes: int = 2_000_000, max_retries: int = 1, timeout: float = 15.0,
                 public_data: bool = False):
        self._owned = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5), follow_redirects=False, trust_env=True,
            headers={"User-Agent": f"UK-Data-MCP/{__version__} (+read-only public data discovery)",
                     "Accept": "application/json" if public_data else "application/geo+json, application/json"},
        )
        self.public_data = public_data
        self.rate_interval = rate_interval
        self.max_bytes = max_bytes
        self.max_retries = max_retries
        self.timeout = timeout
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}
        self._concurrency = asyncio.Semaphore(4)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    async def aclose(self):
        if self._owned:
            await self._client.aclose()

    async def _throttle(self, host: str):
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            delay = self.rate_interval - (time.monotonic() - self._last.get(host, 0))
            if delay > 0:
                await asyncio.sleep(delay)
            self._last[host] = time.monotonic()

    async def get_json(self, url: str, params=None) -> FetchResult:
        initial = checked_url(url, public_data=self.public_data)
        target = str(httpx.URL(initial, params=params)) if params is not None else initial
        async with self._concurrency:
            try:
                async with asyncio.timeout(self.timeout * (self.max_retries + 1) + 5):
                    return await self._get(target)
            except TimeoutError as exc:
                raise DataAccessError("Public API request exceeded its time budget.", code="timeout", url=target) from exc

    async def _get(self, target: str) -> FetchResult:
        redirects = retries = 0
        while True:
            checked_url(target, public_data=self.public_data)
            host = urlsplit(target).hostname
            await self._throttle(host)
            try:
                async with self._client.stream("GET", target, follow_redirects=False) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location or redirects >= 2:
                            raise DataAccessError("API redirect limit exceeded or missing location.", code="redirect", url=target)
                        target = checked_url(urljoin(target, location), public_data=self.public_data)
                        redirects += 1
                        continue
                    if response.status_code in (429, 502, 503, 504) and retries < self.max_retries:
                        retries += 1
                        try:
                            wait = float(response.headers.get("retry-after", "1"))
                        except ValueError:
                            try:
                                when = parsedate_to_datetime(response.headers["retry-after"])
                                if when.tzinfo is None:
                                    when = when.replace(tzinfo=timezone.utc)
                                wait = max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
                            except (ValueError, TypeError, KeyError, OverflowError):
                                raise DataAccessError("Provider returned an unreadable retry delay; retry later.", code="rate_limited", url=target, status_code=response.status_code)
                        if not 0 <= wait <= 5:
                            raise DataAccessError("Provider requests a longer retry delay; retry later.", code="rate_limited", url=target, status_code=response.status_code)
                        await asyncio.sleep(wait)
                        continue
                    if response.status_code != 200:
                        raise DataAccessError(f"Public API returned HTTP {response.status_code}; data unavailable.", code="http_error", url=target, status_code=response.status_code)
                    length = response.headers.get("content-length")
                    if length and length.isdigit() and int(length) > self.max_bytes:
                        raise DataAccessError("Response exceeds the byte limit; narrow the query.", code="too_large", url=target)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(chunks) + len(chunk) > self.max_bytes:
                            raise DataAccessError("Response exceeds the byte limit; narrow the query.", code="too_large", url=target)
                        chunks.extend(chunk)
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and "json" not in content_type:
                        raise DataAccessError("Expected JSON from public API; received another format.", code="invalid_response", url=target)
                    try:
                        data = loads_json(chunks)
                    except (ValueError, RecursionError, OverflowError) as exc:
                        raise DataAccessError("Public API returned invalid or excessively complex JSON.", code="invalid_response", url=target) from exc
                    return FetchResult(data=data, url=str(response.url), retrieved_at=utc_now(), sha256=hashlib.sha256(chunks).hexdigest(), content_type=content_type, status_code=response.status_code)
            except httpx.TimeoutException as exc:
                raise DataAccessError("Public API timed out; no data were inferred.", code="timeout", url=target) from exc
            except httpx.HTTPError as exc:
                raise DataAccessError("Public API connection failed; no data were inferred.", code="network_error", url=target) from exc
