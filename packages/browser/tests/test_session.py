"""Tests for session-level stealth management."""

from __future__ import annotations

from pathlib import Path

from forum_schemas.models.pipeline import StealthLevel

from forum_browser.stealth.session import SessionConfig, SessionManager


class TestSessionConfig:
    def test_defaults(self) -> None:
        config = SessionConfig()
        assert config.warming_enabled is True
        assert config.accept_cookies is True
        assert config.referrer_chain is True
        assert config.persistent_profile_dir is None


class TestSessionManager:
    async def test_construct_referrer(self) -> None:
        manager = SessionManager()
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            referrer = await manager.construct_referrer(page, "https://example.com/data")
            assert isinstance(referrer, str)

    async def test_construct_referrer_disabled(self) -> None:
        config = SessionConfig(referrer_chain=False)
        manager = SessionManager(config)
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            referrer = await manager.construct_referrer(page, "https://example.com/data")
            assert referrer == ""

    async def test_save_and_load_profile(self, tmp_path: Path) -> None:
        config = SessionConfig(persistent_profile_dir=tmp_path / "profiles")
        manager = SessionManager(config)

        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            context = await browser.new_context()
            await manager.save_browser_profile(context, "test_pipeline")
            profile_file = tmp_path / "profiles" / "test_pipeline.json"
            assert profile_file.exists()

            context2 = await browser.new_context()
            loaded = await manager.load_browser_profile(context2, "test_pipeline")
            assert loaded is True

    async def test_load_nonexistent_profile(self, tmp_path: Path) -> None:
        config = SessionConfig(persistent_profile_dir=tmp_path)
        manager = SessionManager(config)

        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            context = await browser.new_context()
            loaded = await manager.load_browser_profile(context, "nonexistent")
            assert loaded is False

    async def test_load_profile_no_dir_configured(self) -> None:
        manager = SessionManager(SessionConfig(persistent_profile_dir=None))
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            context = await browser.new_context()
            loaded = await manager.load_browser_profile(context, "any")
            assert loaded is False

    async def test_warming_disabled(self) -> None:
        config = SessionConfig(warming_enabled=False)
        manager = SessionManager(config)
        from forum_browser.browser import BrowserConfig, ForumBrowser

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await manager.warm_session(page, "https://example.com")
            # Should be a no-op, page URL shouldn't change
