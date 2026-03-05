"""Rotating tab pool for multi-page sessions."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

    from forum_browser.browser import ForumBrowser


@dataclass(frozen=True)
class TabPoolConfig:
    max_tabs: int = 5
    shared_context: bool = True
    rotate_on_reuse: bool = True


class TabPool:
    """Manages a pool of browser tabs for multi-page navigation.

    When shared_context=True (default), all tabs share one BrowserContext
    (same cookies, session). When shared_context=False, each tab gets its
    own isolated BrowserContext for cookie isolation.
    """

    def __init__(self, browser: ForumBrowser, config: TabPoolConfig | None = None) -> None:
        self._browser = browser
        self._config = config or TabPoolConfig()
        self._available: list[Page] = []
        self._in_use: set[Page] = set()
        self._isolated_contexts: list[BrowserContext] = []
        self._lock = asyncio.Lock()
        self._available_event = asyncio.Event()

    async def _create_page(self) -> Page:
        """Create a new page, using shared or isolated context."""
        if self._config.shared_context:
            return await self._browser.new_page()
        # Isolated: each tab gets its own BrowserContext
        context = await self._browser.new_context()
        self._isolated_contexts.append(context)
        return await context.new_page()

    async def acquire(self) -> Page:
        """Get an available tab from the pool."""
        async with self._lock:
            if self._available:
                page = self._available.pop(0)
                self._in_use.add(page)
                return page
            if len(self._in_use) < self._config.max_tabs:
                page = await self._create_page()
                self._in_use.add(page)
                return page

        # At capacity — wait for a release
        while True:
            self._available_event.clear()
            await self._available_event.wait()
            async with self._lock:
                if self._available:
                    page = self._available.pop(0)
                    self._in_use.add(page)
                    return page

    async def release(self, page: Page) -> None:
        """Return a tab to the pool for reuse."""
        async with self._lock:
            self._in_use.discard(page)
            if self._config.rotate_on_reuse:
                try:
                    await page.goto("about:blank")
                except Exception:
                    return
            self._available.append(page)
            self._available_event.set()

    async def close_all(self) -> None:
        """Close all tabs and clean up."""
        async with self._lock:
            for page in [*self._available, *self._in_use]:
                with contextlib.suppress(Exception):
                    await page.close()
            for ctx in self._isolated_contexts:
                with contextlib.suppress(Exception):
                    await ctx.close()
            self._available.clear()
            self._in_use.clear()
            self._isolated_contexts.clear()

    @property
    def active_count(self) -> int:
        return len(self._in_use)

    @property
    def available_count(self) -> int:
        return len(self._available)
