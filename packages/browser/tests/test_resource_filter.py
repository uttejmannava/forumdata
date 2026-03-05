"""Tests for resource filtering."""

from __future__ import annotations

from forum_browser.resource_filter import ResourceFilterConfig, _matches_blocked_domain


class TestMatchesBlockedDomain:
    def test_exact_match(self) -> None:
        assert _matches_blocked_domain("https://google-analytics.com/track", frozenset({"google-analytics.com"}))

    def test_subdomain_match(self) -> None:
        assert _matches_blocked_domain(
            "https://www.google-analytics.com/track", frozenset({"google-analytics.com"})
        )

    def test_no_match(self) -> None:
        assert not _matches_blocked_domain("https://example.com/page", frozenset({"google-analytics.com"}))

    def test_partial_no_match(self) -> None:
        # "analytics.com" should NOT match "google-analytics.com"
        assert not _matches_blocked_domain("https://google-analytics.com/x", frozenset({"analytics.com"}))

    def test_empty_domains(self) -> None:
        assert not _matches_blocked_domain("https://example.com", frozenset())

    def test_invalid_url(self) -> None:
        assert not _matches_blocked_domain("not-a-url", frozenset({"example.com"}))


class TestResourceFilterConfig:
    def test_defaults(self) -> None:
        config = ResourceFilterConfig()
        assert "image" in config.blocked_types
        assert "media" in config.blocked_types
        assert "font" in config.blocked_types
        assert config.allow_stylesheets is False

    def test_allow_stylesheets(self) -> None:
        config = ResourceFilterConfig(
            blocked_types=frozenset({"image", "stylesheet"}),
            allow_stylesheets=True,
        )
        assert config.allow_stylesheets is True

    def test_blocked_domains(self) -> None:
        config = ResourceFilterConfig(blocked_domains=frozenset({"ads.example.com", "tracker.io"}))
        assert "ads.example.com" in config.blocked_domains
        assert len(config.blocked_domains) == 2


class TestResourceFilterIntegration:
    async def test_filter_installs_route_handler(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_browser.resource_filter import ResourceFilterConfig, install_resource_filter
        from forum_schemas.models.pipeline import StealthLevel

        config = BrowserConfig(
            stealth_level=StealthLevel.BASIC,
            headless=True,
            resource_blocking_enabled=False,  # Don't auto-install
        )
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            # Install filter manually to verify it works
            filter_config = ResourceFilterConfig(
                blocked_types=frozenset({"image", "font"}),
                blocked_domains=frozenset({"evil-tracker.com"}),
            )
            await install_resource_filter(page, filter_config)
            # Navigate — page works despite filter being installed
            await page.goto("data:text/html,<p>Filtered page</p>")
            text = await page.text_content("p")
            assert text == "Filtered page"

    async def test_filter_allows_html(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_schemas.models.pipeline import StealthLevel

        config = BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True, resource_blocking_enabled=True)
        async with ForumBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<p>Allowed</p>")
            text = await page.text_content("p")
            assert text == "Allowed"
