"""Tests for element fingerprinting."""

from __future__ import annotations

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.resolution.fingerprints import (
    ElementFingerprint,
    capture_fingerprint,
    find_by_fingerprint,
    score_similarity,
)


class TestScoreSimilarity:
    def test_identical_fingerprints(self) -> None:
        fp = ElementFingerprint(
            identifier="test",
            tag_name="td",
            text_content="72.45",
            attributes={"class": "price"},
            sibling_tags=["td", "td", "td"],
            ancestor_path=["html", "body", "table", "tbody", "tr"],
            parent_tag="tr",
            parent_attributes={"class": "row"},
        )
        score = score_similarity(fp, fp)
        assert score > 0.9

    def test_completely_different(self) -> None:
        fp1 = ElementFingerprint(
            identifier="a",
            tag_name="td",
            text_content="Price",
            attributes={"class": "price"},
            ancestor_path=["html", "body", "table", "tr"],
            parent_tag="tr",
        )
        fp2 = ElementFingerprint(
            identifier="b",
            tag_name="div",
            text_content="Something completely different and unrelated",
            attributes={"id": "header"},
            ancestor_path=["html", "body", "nav"],
            parent_tag="nav",
        )
        score = score_similarity(fp1, fp2)
        assert score < 0.3

    def test_similar_elements(self) -> None:
        fp1 = ElementFingerprint(
            identifier="price1",
            tag_name="td",
            text_content="72.45",
            attributes={"class": "price"},
            sibling_tags=["td", "td", "td"],
            ancestor_path=["html", "body", "table", "tbody", "tr"],
            parent_tag="tr",
            parent_attributes={"class": "row"},
        )
        fp2 = ElementFingerprint(
            identifier="price2",
            tag_name="td",
            text_content="73.10",
            attributes={"class": "price"},
            sibling_tags=["td", "td", "td"],
            ancestor_path=["html", "body", "table", "tbody", "tr"],
            parent_tag="tr",
            parent_attributes={"class": "row"},
        )
        score = score_similarity(fp1, fp2)
        assert score > 0.6


class TestCaptureFingerprint:
    async def test_capture(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            fp = await capture_fingerprint(page, "td.price", "settlement_price")
            assert fp.tag_name == "td"
            assert fp.identifier == "settlement_price"
            assert "72.45" in fp.text_content
            assert fp.parent_tag == "tr"

    async def test_capture_not_found(self, simple_table_html: str) -> None:
        import pytest

        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            with pytest.raises(ValueError, match="Element not found"):
                await capture_fingerprint(page, "#nonexistent", "missing")


class TestFindByFingerprint:
    async def test_find_matching_elements(self, simple_table_html: str) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.set_content(simple_table_html)
            fp = await capture_fingerprint(page, "td.price", "price")
            matches = await find_by_fingerprint(page, fp, threshold=0.5)
            assert len(matches) > 0
            # All price cells should match well
            for _selector, score in matches:
                assert score >= 0.5
