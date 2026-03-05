"""Tests for behavioral simulation."""

from __future__ import annotations

from forum_browser.stealth.behavior import BehaviorConfig, HumanBehavior


class TestBezierPoints:
    def test_generates_correct_count(self) -> None:
        points = HumanBehavior._bezier_points((0, 0), (100, 100), steps=10)
        assert len(points) == 10

    def test_ends_at_target(self) -> None:
        points = HumanBehavior._bezier_points((0, 0), (500, 300), steps=50)
        last = points[-1]
        assert abs(last[0] - 500) < 1
        assert abs(last[1] - 300) < 1

    def test_starts_near_origin(self) -> None:
        points = HumanBehavior._bezier_points((10, 20), (200, 150), steps=30)
        first = points[0]
        # First point should be near the start (bezier begins at t=1/steps)
        assert first[0] < 50
        assert first[1] < 50

    def test_points_are_tuples(self) -> None:
        points = HumanBehavior._bezier_points((10, 20), (200, 150))
        for p in points:
            assert isinstance(p, tuple)
            assert len(p) == 2

    def test_different_runs_produce_different_curves(self) -> None:
        points1 = HumanBehavior._bezier_points((0, 0), (100, 100), steps=20)
        points2 = HumanBehavior._bezier_points((0, 0), (100, 100), steps=20)
        # Random control points mean curves should differ (extremely unlikely to match)
        assert points1 != points2


class TestLogNormalDelay:
    def test_positive_values(self) -> None:
        for _ in range(100):
            delay = HumanBehavior._log_normal_delay(median_ms=150, sigma=0.5)
            assert delay > 0

    def test_reasonable_range(self) -> None:
        delays = [HumanBehavior._log_normal_delay(median_ms=150, sigma=0.5) for _ in range(1000)]
        avg = sum(delays) / len(delays)
        assert 50 < avg < 500  # Median ~150, mean slightly higher due to log-normal


class TestBehaviorConfig:
    def test_defaults(self) -> None:
        config = BehaviorConfig()
        assert config.mouse_movements is True
        assert config.scroll_simulation is True
        assert config.typing_simulation is True

    def test_custom(self) -> None:
        config = BehaviorConfig(mouse_movements=False, min_action_delay_ms=100)
        assert config.mouse_movements is False
        assert config.min_action_delay_ms == 100


class TestHumanBehaviorIntegration:
    async def test_scroll_page(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_schemas.models.pipeline import StealthLevel

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<div style='height:5000px'><p>Top</p></div>")
            behavior = HumanBehavior(page)
            await behavior.scroll_page("down", 200)
            scroll_y = await page.evaluate("() => window.scrollY")
            assert scroll_y > 0

    async def test_move_mouse(self) -> None:
        from forum_browser.browser import BrowserConfig, ForumBrowser
        from forum_schemas.models.pipeline import StealthLevel

        async with ForumBrowser(BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True)) as browser:
            page = await browser.new_page()
            await page.goto("data:text/html,<div style='width:500px;height:500px'><p>Hello</p></div>")
            behavior = HumanBehavior(page)
            # Track mouse position via JS
            await page.evaluate("() => { window._lastMouseX = 0; window._lastMouseY = 0; document.addEventListener('mousemove', e => { window._lastMouseX = e.clientX; window._lastMouseY = e.clientY; }); }")
            await behavior.move_mouse_to(100, 100)
            mouse_x = await page.evaluate("() => window._lastMouseX")
            mouse_y = await page.evaluate("() => window._lastMouseY")
            # Mouse should have moved close to the target
            assert abs(mouse_x - 100) < 15
            assert abs(mouse_y - 100) < 15
