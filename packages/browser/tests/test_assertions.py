"""Tests for test assertion helpers."""

from __future__ import annotations

import pytest

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.resolution.cascade import ResolutionResult, ResolutionTier
from forum_browser.resolution.fingerprints import ElementFingerprint
from forum_browser.stealth.signals import SignalMonitor
from forum_browser.testing.assertions import (
    assert_element_exists,
    assert_element_text,
    assert_fingerprint_similarity,
    assert_no_detection_signals,
    assert_resolution_tier,
)


class TestAssertElementExists:
    async def test_exists(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            await assert_element_exists(page, "td.price")

    async def test_not_exists(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            with pytest.raises(AssertionError, match="Expected element"):
                await assert_element_exists(page, "#nonexistent")


class TestAssertElementText:
    async def test_contains(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            await assert_element_text(page, "h1", "Settlement")

    async def test_exact(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            await assert_element_text(page, "h1", "Settlement Prices", exact=True)

    async def test_mismatch(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            with pytest.raises(AssertionError):
                await assert_element_text(page, "h1", "Wrong Text", exact=True)


class TestAssertNoDetectionSignals:
    async def test_clean(self) -> None:
        monitor = SignalMonitor()
        await assert_no_detection_signals(monitor)

    async def test_detected(self) -> None:
        monitor = SignalMonitor()
        for _ in range(5):
            monitor.record_response_time(100)
        monitor.record_response_time(1000)
        with pytest.raises(AssertionError, match="Detection signals"):
            await assert_no_detection_signals(monitor)


class TestAssertResolutionTier:
    async def test_correct_tier(self) -> None:
        result = ResolutionResult(
            selector="td.price",
            tier=ResolutionTier.DIRECT_SELECTOR,
            confidence=1.0,
            element_count=1,
        )
        await assert_resolution_tier(result, ResolutionTier.DIRECT_SELECTOR)

    async def test_wrong_tier(self) -> None:
        result = ResolutionResult(
            selector="td.price",
            tier=ResolutionTier.FINGERPRINT_MATCH,
            confidence=0.8,
            element_count=1,
        )
        with pytest.raises(AssertionError, match="Expected tier"):
            await assert_resolution_tier(result, ResolutionTier.DIRECT_SELECTOR)


class TestAssertFingerprintSimilarity:
    def test_similar(self) -> None:
        fp = ElementFingerprint(
            identifier="test",
            tag_name="td",
            text_content="72.45",
            attributes={"class": "price"},
            ancestor_path=["html", "body", "table", "tr"],
            parent_tag="tr",
        )
        assert_fingerprint_similarity(fp, fp, min_score=0.8)

    def test_dissimilar(self) -> None:
        fp1 = ElementFingerprint(identifier="a", tag_name="td", text_content="Price")
        fp2 = ElementFingerprint(identifier="b", tag_name="div", text_content="Unrelated")
        with pytest.raises(AssertionError, match="below threshold"):
            assert_fingerprint_similarity(fp1, fp2, min_score=0.8)
