"""Tests for network interception."""

from __future__ import annotations

from forum_browser.network import CapturedRequest, NetworkInterceptor


class TestCapturedRequest:
    def test_defaults(self) -> None:
        req = CapturedRequest(url="https://api.example.com/v1/data", method="GET")
        assert req.response_status is None
        assert req.response_body is None
        assert req.resource_type == ""
        assert req.headers == {}

    def test_full_request(self) -> None:
        req = CapturedRequest(
            url="https://api.example.com/data",
            method="POST",
            headers={"content-type": "application/json"},
            post_data='{"query": "test"}',
            resource_type="xhr",
            response_status=200,
            response_content_type="application/json",
            response_body='{"results": []}',
        )
        assert req.method == "POST"
        assert req.post_data == '{"query": "test"}'
        assert req.response_body == '{"results": []}'


class TestNetworkInterceptor:
    def test_api_candidate_json(self) -> None:
        interceptor = NetworkInterceptor()
        interceptor._captured.append(
            CapturedRequest(
                url="https://example.com/data",
                method="GET",
                resource_type="xhr",
                response_status=200,
                response_content_type="application/json",
                response_body='{"data": []}',
            )
        )
        candidates = interceptor.get_api_candidates()
        assert len(candidates) == 1
        assert candidates[0].url == "https://example.com/data"

    def test_api_candidate_url_pattern(self) -> None:
        interceptor = NetworkInterceptor()
        interceptor._captured.append(
            CapturedRequest(
                url="https://example.com/api/v1/users",
                method="GET",
                resource_type="xhr",
                response_status=200,
                response_content_type="text/html",
            )
        )
        candidates = interceptor.get_api_candidates()
        assert len(candidates) == 1

    def test_api_candidate_graphql(self) -> None:
        interceptor = NetworkInterceptor()
        interceptor._captured.append(
            CapturedRequest(
                url="https://example.com/graphql",
                method="POST",
                resource_type="fetch",
                response_status=200,
                response_content_type="text/html",
            )
        )
        candidates = interceptor.get_api_candidates()
        assert len(candidates) == 1

    def test_non_api_request_filtered(self) -> None:
        interceptor = NetworkInterceptor()
        interceptor._captured.append(
            CapturedRequest(
                url="https://example.com/page.html",
                method="GET",
                resource_type="xhr",
                response_status=200,
                response_content_type="text/html",
            )
        )
        candidates = interceptor.get_api_candidates()
        assert len(candidates) == 0

    def test_empty_interceptor(self) -> None:
        interceptor = NetworkInterceptor()
        assert interceptor.captured_requests == []
        assert interceptor.get_api_candidates() == []

    async def test_install_attaches_listeners(self) -> None:
        """Verify install/uninstall works without crashing."""
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_schemas.models.pipeline import StealthLevel

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            interceptor = NetworkInterceptor()
            await interceptor.install(page)
            assert interceptor._request_handler is not None
            assert interceptor._response_handler is not None
            await interceptor.uninstall(page)

    async def test_captured_requests_is_list(self) -> None:
        interceptor = NetworkInterceptor()
        assert isinstance(interceptor.captured_requests, list)
        assert len(interceptor.captured_requests) == 0
