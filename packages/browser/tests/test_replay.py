"""Tests for interaction replay."""

from __future__ import annotations

from pathlib import Path

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.testing.recorder import InteractionRecorder
from forum_browser.testing.replay import InteractionReplayer


class TestInteractionReplayer:
    async def test_replay_fixture(self, fixtures_dir: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        session = InteractionRecorder.load(fixtures_dir / "simple_table")
        replayer = InteractionReplayer(session)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await replayer.install(page)
            await page.goto(session.target_url)

            content = await page.content()
            assert "Settlement Prices" in content
            assert "72.45" in content

            await replayer.uninstall(page)

    async def test_unmatched_tracking(self, fixtures_dir: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        session = InteractionRecorder.load(fixtures_dir / "simple_table")
        replayer = InteractionReplayer(session)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await replayer.install(page)
            await page.goto(session.target_url)

            # Unmatched requests should be empty for matched URLs
            # The main page URL was matched
            assert session.target_url not in replayer.unmatched_requests

    async def test_unused_recordings(self, fixtures_dir: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        session = InteractionRecorder.load(fixtures_dir / "simple_table")
        replayer = InteractionReplayer(session)

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await replayer.install(page)
            # Don't navigate — all recordings should be unused
            unused = replayer.unused_recordings
            assert len(unused) > 0
