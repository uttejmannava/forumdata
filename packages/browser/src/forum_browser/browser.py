"""Browser lifecycle management — launch, configure, and teardown Playwright browsers."""

from __future__ import annotations

import contextlib
import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from forum_browser.resource_filter import ResourceFilterConfig, install_resource_filter
from forum_browser.tracing import start_tracing, stop_tracing
from forum_schemas.models.pipeline import StealthLevel

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

    from forum_browser.stealth.profiles import DeviceProfile


class BrowserEngine(enum.StrEnum):
    """Supported browser engines."""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"


@dataclass(frozen=True)
class BrowserConfig:
    """Configuration for a browser session."""

    stealth_level: StealthLevel = StealthLevel.NONE
    engine: BrowserEngine = BrowserEngine.CHROMIUM
    headless: bool = True
    proxy_url: str | None = None
    resource_blocking_enabled: bool = True
    blocked_resource_types: frozenset[str] = frozenset({"image", "media", "font"})
    blocked_domains: frozenset[str] = frozenset()
    device_profile: DeviceProfile | None = None
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str | None = None
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    geolocation: dict[str, float] | None = None
    extra_http_headers: dict[str, str] = field(default_factory=dict)
    trace_enabled: bool = False
    trace_dir: str = "traces"


class ForumBrowser:
    """Managed browser session with stealth and resource management.

    Usage:
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("https://example.com")
    """

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self._config = config or BrowserConfig()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._default_context: BrowserContext | None = None
        self._contexts: list[BrowserContext] = []
        self._trace_counter = 0

    @property
    def config(self) -> BrowserConfig:
        return self._config

    async def __aenter__(self) -> ForumBrowser:
        await self._launch()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._teardown()

    async def new_page(self) -> Page:
        """Create a new page in the default context."""
        if self._default_context is None:
            self._default_context = await self.new_context()
        page = await self._default_context.new_page()
        if self._config.resource_blocking_enabled:
            await self._setup_resource_blocking(page)
        return page

    async def new_context(self, **overrides: object) -> BrowserContext:
        """Create a new browser context with configured defaults.

        When a device_profile is set on the config, the context is configured
        with the profile's viewport, user agent, locale, timezone, and
        fingerprint overrides (canvas/WebGL noise, navigator spoofing).
        """
        if self._browser is None:
            msg = "Browser not launched. Use 'async with ForumBrowser(config) as browser:'."
            raise RuntimeError(msg)

        profile = self._config.device_profile

        # Use profile values when available, falling back to config defaults
        viewport_w = profile.viewport_width if profile else self._config.viewport_width
        viewport_h = profile.viewport_height if profile else self._config.viewport_height
        user_agent = (profile.user_agent if profile else self._config.user_agent) or None
        locale = profile.locale if profile else self._config.locale
        timezone_id = profile.timezone if profile else self._config.timezone_id

        context_opts: dict[str, object] = {
            "viewport": {"width": viewport_w, "height": viewport_h},
            "locale": locale,
            "timezone_id": timezone_id,
        }
        if user_agent:
            context_opts["user_agent"] = user_agent
        if self._config.geolocation:
            context_opts["geolocation"] = self._config.geolocation
            context_opts["permissions"] = ["geolocation"]
        if self._config.extra_http_headers:
            context_opts["extra_http_headers"] = self._config.extra_http_headers

        context_opts.update(overrides)
        context = await self._browser.new_context(**context_opts)  # type: ignore[arg-type]
        self._contexts.append(context)

        # Inject fingerprint overrides (canvas/WebGL noise, navigator props)
        if profile:
            from forum_browser.stealth.injections import inject_fingerprint_overrides

            await inject_fingerprint_overrides(context, profile)

        if self._config.trace_enabled:
            await start_tracing(context)

        return context

    async def _launch(self) -> None:
        """Launch the browser."""
        if self._config.stealth_level == StealthLevel.NONE:
            msg = (
                "StealthLevel.NONE does not use a browser. "
                "Use StealthHttpClient for non-browser requests."
            )
            raise ValueError(msg)

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        launch_opts: dict[str, object] = {"headless": self._config.headless}
        if self._config.proxy_url:
            launch_opts["proxy"] = {"server": self._config.proxy_url}

        # Apply TLS-matching browser args when a device profile is configured
        if self._config.device_profile:
            from forum_browser.stealth.tls import get_browser_args_for_profile

            extra_args = get_browser_args_for_profile(self._config.device_profile)
            launch_opts["args"] = extra_args

        engine_launcher = getattr(self._playwright, self._config.engine.value)
        self._browser = await engine_launcher.launch(**launch_opts)

    async def _setup_resource_blocking(self, page: Page) -> None:
        """Install resource blocking on a page."""
        filter_config = ResourceFilterConfig(
            blocked_types=self._config.blocked_resource_types,
            blocked_domains=self._config.blocked_domains,
        )
        await install_resource_filter(page, filter_config)

    async def _teardown(self) -> None:
        """Close browser and save traces."""
        for context in self._contexts:
            if self._config.trace_enabled:
                self._trace_counter += 1
                trace_path = Path(self._config.trace_dir) / f"trace_{self._trace_counter}.zip"
                with contextlib.suppress(Exception):
                    await stop_tracing(context, trace_path)
            with contextlib.suppress(Exception):
                await context.close()
        self._contexts.clear()
        self._default_context = None

        if self._browser:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None

        if self._playwright:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None
