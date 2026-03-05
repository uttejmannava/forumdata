"""Tests for HTTP client with curl_cffi impersonation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forum_browser.http import (
    BrowserImpersonation,
    HttpClientConfig,
    HttpResponse,
    StealthHttpClient,
)


class TestHttpClientConfig:
    def test_defaults(self) -> None:
        config = HttpClientConfig()
        assert config.impersonation == BrowserImpersonation.CHROME
        assert config.proxy_url is None
        assert config.timeout == 30.0
        assert config.verify_ssl is True

    def test_custom_impersonation(self) -> None:
        config = HttpClientConfig(impersonation=BrowserImpersonation.FIREFOX)
        assert config.impersonation == BrowserImpersonation.FIREFOX

    def test_proxy_config(self) -> None:
        config = HttpClientConfig(proxy_url="http://proxy:8080")
        assert config.proxy_url == "http://proxy:8080"

    def test_default_headers(self) -> None:
        config = HttpClientConfig(default_headers={"X-Custom": "value"})
        assert config.default_headers == {"X-Custom": "value"}


class TestHttpResponse:
    def test_fields(self) -> None:
        response = HttpResponse(
            status_code=200,
            headers={"content-type": "text/html"},
            text="<html></html>",
            url="https://example.com",
            elapsed_ms=150.0,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html"
        assert response.text == "<html></html>"
        assert response.elapsed_ms == 150.0

    def test_non_200_status(self) -> None:
        response = HttpResponse(
            status_code=404,
            headers={},
            text="Not Found",
            url="https://example.com/missing",
            elapsed_ms=50.0,
        )
        assert response.status_code == 404


class TestStealthHttpClient:
    async def test_not_started_error(self) -> None:
        client = StealthHttpClient()
        with pytest.raises(RuntimeError, match="Client not started"):
            await client.get("https://example.com")

    async def test_context_manager_lifecycle(self) -> None:
        async with StealthHttpClient() as client:
            assert client._session is not None
        assert client._session is None

    async def test_get_request(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"origin": "1.2.3.4"}'
        mock_response.url = "https://example.com/get"

        config = HttpClientConfig(impersonation=BrowserImpersonation.CHROME)
        async with StealthHttpClient(config) as client:
            client._session.request = AsyncMock(return_value=mock_response)
            response = await client.get("https://example.com/get")
            assert response.status_code == 200
            assert response.elapsed_ms > 0
            assert "example.com" in response.url
            client._session.request.assert_called_once()

    async def test_post_request(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"key": "value"}'
        mock_response.url = "https://example.com/post"

        async with StealthHttpClient() as client:
            client._session.request = AsyncMock(return_value=mock_response)
            response = await client.post(
                "https://example.com/post",
                json={"key": "value"},
            )
            assert response.status_code == 200
            assert '"key": "value"' in response.text

    async def test_head_request(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = ""
        mock_response.url = "https://example.com/head"

        async with StealthHttpClient() as client:
            client._session.request = AsyncMock(return_value=mock_response)
            response = await client.head("https://example.com/head")
            assert response.status_code == 200
            assert response.text == ""

    async def test_default_headers_merged(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "{}"
        mock_response.url = "https://example.com/headers"

        config = HttpClientConfig(default_headers={"X-Custom": "default"})
        async with StealthHttpClient(config) as client:
            client._session.request = AsyncMock(return_value=mock_response)
            await client.get(
                "https://example.com/headers",
                headers={"X-Override": "per-request"},
            )
            # Verify merged headers were passed
            call_kwargs = client._session.request.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
            assert headers["X-Custom"] == "default"
            assert headers["X-Override"] == "per-request"

    async def test_per_request_headers_override_defaults(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = "{}"
        mock_response.url = "https://example.com"

        config = HttpClientConfig(default_headers={"X-Custom": "default"})
        async with StealthHttpClient(config) as client:
            client._session.request = AsyncMock(return_value=mock_response)
            await client.get(
                "https://example.com",
                headers={"X-Custom": "override"},
            )
            call_kwargs = client._session.request.call_args
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
            assert headers["X-Custom"] == "override"

    async def test_different_impersonation_profiles(self) -> None:
        for profile in [BrowserImpersonation.CHROME, BrowserImpersonation.FIREFOX]:
            config = HttpClientConfig(impersonation=profile)
            async with StealthHttpClient(config) as client:
                assert client._session is not None
                # Verify session was created with the correct impersonation
                # (curl_cffi stores it internally)

    async def test_proxy_configuration(self) -> None:
        config = HttpClientConfig(proxy_url="http://proxy:8080")
        with patch("forum_browser.http.AsyncSession") as mock_session_cls:
            mock_session_cls.return_value = MagicMock()
            mock_session_cls.return_value.close = AsyncMock()
            async with StealthHttpClient(config):
                mock_session_cls.assert_called_once()
                call_kwargs = mock_session_cls.call_args
                proxies = call_kwargs.kwargs.get("proxies") or call_kwargs[1].get("proxies")
                assert proxies == {"http": "http://proxy:8080", "https": "http://proxy:8080"}
