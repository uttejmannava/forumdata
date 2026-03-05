"""Tests for interaction recorder."""

from __future__ import annotations

from pathlib import Path

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.testing.recorder import InteractionRecorder


class TestInteractionRecorder:
    async def test_record_and_save(self, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with InteractionRecorder("test_session") as recorder:
            async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
                page = await browser.new_page()
                recorder.attach(page)
                await page.goto("data:text/html,<h1>Recorded</h1>")
                await recorder.capture_dom_snapshot(page, "initial")

            output_dir = tmp_path / "recording"
            recorder.save(output_dir)
            assert (output_dir / "recording.json").exists()

    async def test_load_recording(self, fixtures_dir: Path) -> None:
        session = InteractionRecorder.load(fixtures_dir / "simple_table")
        assert session.name == "simple_table"
        assert session.target_url == "https://test.local/settlements"
        assert len(session.interactions) == 1
        assert session.interactions[0].response_status == 200

    async def test_round_trip(self, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with InteractionRecorder("round_trip") as recorder:
            async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
                page = await browser.new_page()
                recorder.attach(page)
                await page.goto("data:text/html,<p>RT Test</p>")
                await recorder.capture_dom_snapshot(page, "test")

            output_dir = tmp_path / "rt"
            recorder.save(output_dir)

        loaded = InteractionRecorder.load(output_dir)
        assert loaded.name == "round_trip"
        # data: URLs don't trigger network requests, so interactions may be empty
        assert "test" in loaded.dom_snapshots
        assert "RT Test" in loaded.dom_snapshots["test"]

    async def test_dom_snapshot_capture(self, tmp_path: Path) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with InteractionRecorder("snap") as recorder:
            async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
                page = await browser.new_page()
                recorder.attach(page)
                await page.goto("data:text/html,<p>Snapshot</p>")
                await recorder.capture_dom_snapshot(page, "my_snap")

            output_dir = tmp_path / "snap"
            recorder.save(output_dir)
            # DOM snapshot file should exist
            assert any(f.name.startswith("dom_") for f in output_dir.iterdir())
