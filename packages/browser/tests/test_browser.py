"""Tests for browser lifecycle management."""

from __future__ import annotations

import pytest

from forum_browser.browser import BrowserConfig, BrowserEngine, ForumBrowser
from forum_schemas.models.pipeline import StealthLevel


class TestBrowserConfig:
    def test_defaults(self) -> None:
        config = BrowserConfig()
        assert config.headless is True
        assert config.engine == BrowserEngine.CHROMIUM
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.resource_blocking_enabled is True
        assert config.stealth_level == StealthLevel.NONE

    def test_custom_config(self) -> None:
        config = BrowserConfig(headless=False, viewport_width=1280, viewport_height=720)
        assert config.headless is False
        assert config.viewport_width == 1280


class TestForumBrowser:
    async def test_raises_for_stealth_none(self) -> None:
        config = BrowserConfig(stealth_level=StealthLevel.NONE)
        with pytest.raises(ValueError, match="StealthLevel.NONE"):
            async with ForumBrowser(config):
                pass

    async def test_launch_and_teardown(self) -> None:
        config = BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)
        async with ForumBrowser(config) as browser:
            assert browser._browser is not None

    async def test_new_page(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            assert page is not None
            await page.goto("data:text/html,<h1>Hello</h1>")
            title_text = await page.text_content("h1")
            assert title_text == "Hello"

    async def test_new_context(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            context = await browser.new_context()
            assert context is not None
            page = await context.new_page()
            await page.goto("data:text/html,<p>Test</p>")
            text = await page.text_content("p")
            assert text == "Test"

    async def test_context_not_launched_error(self) -> None:
        browser = ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True))
        with pytest.raises(RuntimeError, match="Browser not launched"):
            await browser.new_context()

    async def test_resource_blocking_on_page(self) -> None:
        """Verify resource blocking installs a route handler that blocks configured types."""
        config = BrowserConfig(
            stealth_level=StealthLevel.BASIC,
            headless=True,
            resource_blocking_enabled=True,
            blocked_resource_types=frozenset({"image", "media", "font"}),
        )
        blocked_types: list[str] = []

        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            # Intercept route to track what gets blocked
            original_routes = len(page._impl_obj._routes)
            assert original_routes > 0, "Resource blocking route handler should be installed"
            # Verify basic page still works
            await page.goto("data:text/html,<p>Blocking test</p>")
            text = await page.text_content("p")
            assert text == "Blocking test"

    async def test_custom_viewport(self) -> None:
        config = BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True, viewport_width=800, viewport_height=600)
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<p>Viewport</p>")
            viewport = page.viewport_size
            assert viewport is not None
            assert viewport["width"] == 800
            assert viewport["height"] == 600

    async def test_device_profile_applies_fingerprint_overrides(self) -> None:
        """Device profile should inject navigator/WebGL overrides into the context."""
        from forum_browser.stealth.profiles import DeviceProfile, OperatingSystem

        profile = DeviceProfile(
            profile_id="test_profile",
            os=OperatingSystem.WINDOWS,
            browser="chrome",
            user_agent="TestAgent/1.0",
            viewport_width=1280,
            viewport_height=720,
            screen_width=1280,
            screen_height=720,
            device_pixel_ratio=1.0,
            platform="Win32",
            hardware_concurrency=4,
            device_memory=8,
            timezone="America/Chicago",
            locale="en-GB",
            canvas_noise_seed=12345,
            webgl_vendor="Test Vendor",
            webgl_renderer="Test Renderer",
        )
        config = BrowserConfig(
            stealth_level=StealthLevel.STANDARD,
            headless=True,
            device_profile=profile,
        )
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<p>Profile test</p>")

            # Verify navigator overrides were injected
            hw_concurrency = await page.evaluate("navigator.hardwareConcurrency")
            assert hw_concurrency == 4

            device_memory = await page.evaluate("navigator.deviceMemory")
            assert device_memory == 8

            platform = await page.evaluate("navigator.platform")
            assert platform == "Win32"

            # Verify viewport matches profile
            viewport = page.viewport_size
            assert viewport is not None
            assert viewport["width"] == 1280
            assert viewport["height"] == 720

    async def test_device_profile_applies_user_agent(self) -> None:
        """Device profile user agent should be set on the context."""
        from forum_browser.stealth.profiles import DeviceProfile, OperatingSystem

        profile = DeviceProfile(
            profile_id="test_ua",
            os=OperatingSystem.MACOS,
            browser="chrome",
            user_agent="CustomUA/2.0",
            viewport_width=1920,
            viewport_height=1080,
            screen_width=1920,
            screen_height=1080,
            device_pixel_ratio=2.0,
            platform="MacIntel",
            hardware_concurrency=8,
            device_memory=16,
            timezone="America/New_York",
            locale="en-US",
        )
        config = BrowserConfig(
            stealth_level=StealthLevel.STANDARD,
            headless=True,
            device_profile=profile,
        )
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<p>UA test</p>")
            ua = await page.evaluate("navigator.userAgent")
            assert ua == "CustomUA/2.0"
