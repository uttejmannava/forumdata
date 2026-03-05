"""Tests for content-based similarity search."""

from __future__ import annotations

from forum_schemas.models.pipeline import StealthLevel


class TestFindByText:
    async def test_exact_match(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.similarity import find_by_text

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            results = await find_by_text(page, "72.45")
            assert len(results) > 0

    async def test_no_match(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.similarity import find_by_text

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            results = await find_by_text(page, "nonexistent_text_xyz")
            assert len(results) == 0


class TestFindByRegex:
    async def test_price_pattern(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.similarity import find_by_regex

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            results = await find_by_regex(page, r"^\d+\.\d{2}$")
            assert len(results) >= 3  # 3 price cells


class TestFindSimilar:
    async def test_find_similar_rows(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.similarity import find_similar

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            results = await find_similar(page, "tr.row", threshold=0.7)
            assert len(results) >= 2  # At least 2 other similar rows


class TestGenerateSelector:
    async def test_generate_by_id(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.similarity import generate_selector

        html = '<html><body><div id="unique-element">Test</div></body></html>'
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(html)
            selector = await generate_selector(page, "unique-element")
            assert selector == "#unique-element"

    async def test_generate_returns_none(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.similarity import generate_selector

        html = "<html><body><p>Generic</p></body></html>"
        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(html)
            selector = await generate_selector(page, "something_that_doesnt_exist_at_all")
            assert selector is None
