"""Tests for detection signal monitoring."""

from __future__ import annotations

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.stealth.signals import DetectionSignal, SignalMonitor, _SIGNAL_TO_ERROR


class TestSignalMonitor:
    def test_initially_clean(self) -> None:
        monitor = SignalMonitor()
        assert not monitor.is_detected
        assert monitor.events == []

    def test_throttling_detection(self) -> None:
        monitor = SignalMonitor()
        # Build up baseline
        for _ in range(5):
            monitor.record_response_time(100)
        # Spike should trigger throttling
        detected = monitor.record_response_time(1000)
        assert detected is True
        assert monitor.is_detected
        assert monitor.events[-1].signal == DetectionSignal.THROTTLING

    def test_no_throttling_with_consistent_times(self) -> None:
        monitor = SignalMonitor()
        for _ in range(10):
            detected = monitor.record_response_time(100)
        assert detected is False
        assert not monitor.is_detected

    def test_not_enough_data_for_throttling(self) -> None:
        monitor = SignalMonitor()
        detected = monitor.record_response_time(1000)
        assert detected is False

    async def test_check_challenge_page(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto(
                "data:text/html,<html><body><div class='cf-browser-verification'>Checking...</div></body></html>"
            )
            monitor = SignalMonitor()
            event = await monitor.check_page_content(page)
            assert event is not None
            assert event.signal == DetectionSignal.CHALLENGE_PAGE
            assert "cf-browser-verification" in event.details.get("marker", "")

    async def test_check_clean_page(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<html><body><p>Normal content</p></body></html>")
            monitor = SignalMonitor()
            event = await monitor.check_page_content(page)
            assert event is None
            assert not monitor.is_detected

    async def test_check_captcha_page(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<html><body><div id='captcha'>Please solve the CAPTCHA</div></body></html>")
            monitor = SignalMonitor()
            event = await monitor.check_page_content(page)
            assert event is not None
            assert event.signal == DetectionSignal.CHALLENGE_PAGE


class TestCheckResponse:
    """Tests for HTTP response-based detection."""

    async def test_rate_limited_429(self) -> None:
        from unittest.mock import AsyncMock

        monitor = SignalMonitor()
        response = AsyncMock()
        response.url = "https://example.com"
        response.status = 429
        response.headers = {}
        event = await monitor.check_response(response)
        assert event is not None
        assert event.signal == DetectionSignal.RATE_LIMITED
        assert event.response_status == 429

    async def test_rate_limit_header_zero(self) -> None:
        from unittest.mock import AsyncMock

        monitor = SignalMonitor()
        response = AsyncMock()
        response.url = "https://example.com"
        response.status = 200
        response.headers = {"x-ratelimit-remaining": "0"}
        event = await monitor.check_response(response)
        assert event is not None
        assert event.signal == DetectionSignal.RATE_LIMITED

    async def test_soft_block_403(self) -> None:
        from unittest.mock import AsyncMock

        monitor = SignalMonitor()
        response = AsyncMock()
        response.url = "https://example.com"
        response.status = 403
        response.headers = {}
        event = await monitor.check_response(response)
        assert event is not None
        assert event.signal == DetectionSignal.SOFT_BLOCK

    async def test_cookie_challenge_redirect_with_cookie(self) -> None:
        from unittest.mock import AsyncMock

        monitor = SignalMonitor()
        response = AsyncMock()
        response.url = "https://example.com"
        response.status = 302
        response.headers = {"set-cookie": "challenge=abc123; Path=/"}
        event = await monitor.check_response(response)
        assert event is not None
        assert event.signal == DetectionSignal.COOKIE_CHALLENGE

    async def test_normal_redirect_no_cookie(self) -> None:
        from unittest.mock import AsyncMock

        monitor = SignalMonitor()
        response = AsyncMock()
        response.url = "https://example.com"
        response.status = 301
        response.headers = {}
        event = await monitor.check_response(response)
        assert event is None

    async def test_clean_200_response(self) -> None:
        from unittest.mock import AsyncMock

        monitor = SignalMonitor()
        response = AsyncMock()
        response.url = "https://example.com"
        response.status = 200
        response.headers = {}
        event = await monitor.check_response(response)
        assert event is None


class TestFingerprintProbeDetection:
    async def test_fingerprint_js_detected(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto(
                "data:text/html,<html><body><script src='fingerprintjs'></script><p>Content</p></body></html>"
            )
            monitor = SignalMonitor()
            event = await monitor.check_page_content(page)
            assert event is not None
            assert event.signal == DetectionSignal.FINGERPRINT_PROBE
            assert event.details["marker"] == "fingerprintjs"

    async def test_botd_detected(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto(
                "data:text/html,<html><body><script>var botd = require('botd')</script></body></html>"
            )
            monitor = SignalMonitor()
            event = await monitor.check_page_content(page)
            assert event is not None
            assert event.signal == DetectionSignal.FINGERPRINT_PROBE


class TestSignalToErrorMapping:
    def test_signal_to_error_code_mapping(self) -> None:
        from forum_schemas.models.errors import ErrorCode, WarningCode

        monitor = SignalMonitor()
        assert monitor.to_error_code(DetectionSignal.CHALLENGE_PAGE) == ErrorCode.DETECTION_BLOCKED
        assert monitor.to_error_code(DetectionSignal.RATE_LIMITED) == ErrorCode.RATE_LIMITED
        assert monitor.to_error_code(DetectionSignal.SOFT_BLOCK) == ErrorCode.ACCESS_BLOCKED
        assert monitor.to_error_code(DetectionSignal.THROTTLING) == WarningCode.DETECTION_SIGNAL

    def test_all_signals_have_error_mapping(self) -> None:
        for signal in DetectionSignal:
            assert signal in _SIGNAL_TO_ERROR
