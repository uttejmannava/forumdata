"""curl_cffi-based HTTP client with browser-grade TLS fingerprints."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from curl_cffi.requests import AsyncSession

if TYPE_CHECKING:
    from curl_cffi.requests import Response


class BrowserImpersonation(enum.StrEnum):
    """Browser TLS fingerprint profiles for curl_cffi."""

    CHROME = "chrome"
    CHROME_ANDROID = "chrome_android"
    SAFARI = "safari"
    SAFARI_IOS = "safari_ios"
    FIREFOX = "firefox"
    EDGE = "edge"
    CHROME_131 = "chrome131"
    CHROME_136 = "chrome136"
    SAFARI_260 = "safari260"
    FIREFOX_135 = "firefox135"


@dataclass(frozen=True)
class HttpClientConfig:
    """Configuration for the stealth HTTP client."""

    impersonation: BrowserImpersonation = BrowserImpersonation.CHROME
    proxy_url: str | None = None
    timeout: float = 30.0
    max_redirects: int = 10
    verify_ssl: bool = True
    default_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HttpResponse:
    """Simplified HTTP response wrapper."""

    status_code: int
    headers: dict[str, str]
    text: str
    url: str
    elapsed_ms: float


class StealthHttpClient:
    """HTTP client with browser-grade TLS fingerprints via curl_cffi.

    Usage:
        async with StealthHttpClient(config) as client:
            response = await client.get("https://api.example.com/data")
    """

    def __init__(self, config: HttpClientConfig | None = None) -> None:
        self._config = config or HttpClientConfig()
        self._session: AsyncSession[Any] | None = None

    async def __aenter__(self) -> StealthHttpClient:
        proxies = None
        if self._config.proxy_url:
            proxies = {"http": self._config.proxy_url, "https": self._config.proxy_url}
        self._session = AsyncSession(
            impersonate=self._config.impersonation.value,
            proxies=proxies,  # type: ignore[arg-type]
            timeout=self._config.timeout,
            max_redirects=self._config.max_redirects,
            verify=self._config.verify_ssl,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Send a GET request."""
        return await self._request("GET", url, headers=headers, params=params)

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: Any = None,
        json: Any = None,
    ) -> HttpResponse:
        """Send a POST request."""
        return await self._request("POST", url, headers=headers, data=data, json=json)

    async def head(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        """Send a HEAD request."""
        return await self._request("HEAD", url, headers=headers)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: Any = None,
        json: Any = None,
    ) -> HttpResponse:
        """Execute an HTTP request and wrap the response."""
        if self._session is None:
            msg = "Client not started. Use 'async with StealthHttpClient(config) as client:'."
            raise RuntimeError(msg)

        merged_headers = {**self._config.default_headers}
        if headers:
            merged_headers.update(headers)

        start = time.monotonic()
        response: Response = await self._session.request(
            method,  # type: ignore[arg-type]
            url,
            headers=merged_headers if merged_headers else None,
            params=params,
            data=data,
            json=json,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        return HttpResponse(
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if v is not None},
            text=response.text,
            url=str(response.url),
            elapsed_ms=elapsed_ms,
        )
