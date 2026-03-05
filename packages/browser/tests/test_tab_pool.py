"""Tests for tab pool management."""

from __future__ import annotations

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.tab_pool import TabPool, TabPoolConfig
from forum_schemas.models.pipeline import StealthLevel


class TestTabPool:
    async def test_acquire_and_release(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=3))
            page = await pool.acquire()
            assert pool.active_count == 1
            assert pool.available_count == 0
            await pool.release(page)
            assert pool.active_count == 0
            assert pool.available_count == 1
            await pool.close_all()

    async def test_reuses_released_tabs(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=2))
            page1 = await pool.acquire()
            await pool.release(page1)
            page2 = await pool.acquire()
            # Should reuse the released page
            assert page2 is page1
            await pool.close_all()

    async def test_max_tabs_limit(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=2))
            p1 = await pool.acquire()
            p2 = await pool.acquire()
            assert pool.active_count == 2
            # Pool is at capacity, release one
            await pool.release(p1)
            p3 = await pool.acquire()
            assert p3 is p1  # Reused
            await pool.close_all()

    async def test_close_all(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=3))
            await pool.acquire()
            await pool.acquire()
            assert pool.active_count == 2
            await pool.close_all()
            assert pool.active_count == 0
            assert pool.available_count == 0

    async def test_navigate_in_pool(self) -> None:
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=2))
            page = await pool.acquire()
            await page.goto("data:text/html,<p>Pool test</p>")
            text = await page.text_content("p")
            assert text == "Pool test"
            await pool.release(page)
            await pool.close_all()

    async def test_tab_pool_config_defaults(self) -> None:
        config = TabPoolConfig()
        assert config.max_tabs == 5
        assert config.shared_context is True
        assert config.rotate_on_reuse is True

    async def test_isolated_context_per_tab(self) -> None:
        """With shared_context=False, each tab gets its own BrowserContext."""
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=3, shared_context=False))
            page1 = await pool.acquire()
            page2 = await pool.acquire()
            # Each page should have a different context
            assert page1.context != page2.context
            await pool.close_all()

    async def test_shared_context_same_context(self) -> None:
        """With shared_context=True, tabs share the same BrowserContext."""
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            pool = TabPool(browser, TabPoolConfig(max_tabs=3, shared_context=True))
            page1 = await pool.acquire()
            page2 = await pool.acquire()
            # Both pages should share the same context
            assert page1.context == page2.context
            await pool.close_all()
