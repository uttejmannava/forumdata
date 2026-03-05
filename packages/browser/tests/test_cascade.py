"""Tests for resolution cascade."""

from __future__ import annotations

from pathlib import Path

import pytest

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.resolution.cascade import ResolutionCascade, ResolutionError, ResolutionTier
from forum_browser.resolution.storage import SqliteFingerprintStorage


class TestResolutionCascade:
    async def test_tier1_direct_selector(self, simple_table_html: str, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        cascade = ResolutionCascade(storage)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            result = await cascade.resolve(page, "td.price", "price")
            assert result.tier == ResolutionTier.DIRECT_SELECTOR
            assert result.confidence == 1.0
            assert result.element_count >= 1

    async def test_tier3_content_match(self, simple_table_html: str, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        cascade = ResolutionCascade(storage)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            result = await cascade.resolve(
                page, "#nonexistent", "price", expected_text="72.45"
            )
            assert result.tier == ResolutionTier.CONTENT_MATCH

    async def test_all_tiers_fail(self, simple_table_html: str, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        cascade = ResolutionCascade(storage)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            with pytest.raises(ResolutionError):
                await cascade.resolve(page, "#nonexistent", "missing")

    async def test_fingerprint_saved_on_direct_hit(self, simple_table_html: str, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        cascade = ResolutionCascade(storage)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            await cascade.resolve(page, "td.price", "price")
            # Fingerprint should now be saved
            fp = await storage.load("default", "default", "price")
            assert fp is not None
            assert fp.tag_name == "td"

    async def test_tier2_fingerprint_match(self, simple_table_html: str, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resolution.fingerprints import capture_fingerprint

        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        cascade = ResolutionCascade(storage)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            # First, save a fingerprint via direct resolution
            fp = await capture_fingerprint(page, "td.price", "price")
            await storage.save("default", "default", "price", fp)
            # Now try with a broken selector — should fall through to Tier 2
            result = await cascade.resolve(page, "#broken_selector", "price")
            assert result.tier == ResolutionTier.FINGERPRINT_MATCH
            assert result.confidence > 0.5
