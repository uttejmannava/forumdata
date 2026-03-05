"""Human-like mouse movements, scrolling, typing, and timing."""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


@dataclass
class BehaviorConfig:
    """Configuration for behavioral simulation intensity."""

    mouse_movements: bool = True
    scroll_simulation: bool = True
    typing_simulation: bool = True
    exploratory_interactions: bool = True
    min_action_delay_ms: int = 200
    max_action_delay_ms: int = 1500


class HumanBehavior:
    """Simulates human-like browser interactions."""

    def __init__(self, page: Page, config: BehaviorConfig | None = None) -> None:
        self._page = page
        self._config = config or BehaviorConfig()

    async def move_mouse_to(self, x: float, y: float) -> None:
        """Move mouse along a bezier curve with realistic acceleration."""
        if not self._config.mouse_movements:
            await self._page.mouse.move(x, y)
            return

        current = await self._page.evaluate("() => ({x: 0, y: 0})")
        points = self._bezier_points((current["x"], current["y"]), (x, y))
        for px, py in points:
            await self._page.mouse.move(px, py)
            await asyncio.sleep(random.uniform(0.005, 0.02))

    async def scroll_to_element(self, selector: str) -> None:
        """Scroll to element with variable speed, momentum, occasional overshoot."""
        if not self._config.scroll_simulation:
            await self._page.locator(selector).scroll_into_view_if_needed()
            return

        element = self._page.locator(selector)
        box = await element.bounding_box()
        if box is None:
            await element.scroll_into_view_if_needed()
            return

        viewport = self._page.viewport_size
        if viewport is None:
            await element.scroll_into_view_if_needed()
            return

        target_y = box["y"] - viewport["height"] / 3
        current_y = await self._page.evaluate("() => window.scrollY")
        distance = target_y - current_y
        steps = max(5, abs(int(distance / 100)))

        for i in range(steps):
            progress = (i + 1) / steps
            eased = progress * progress * (3 - 2 * progress)  # smoothstep
            step_y = current_y + distance * eased
            await self._page.evaluate(f"window.scrollTo(0, {step_y})")
            await asyncio.sleep(random.uniform(0.02, 0.06))

    async def scroll_page(self, direction: str = "down", distance: int = 500) -> None:
        """Scroll with human-like variable speed and occasional pauses."""
        sign = 1 if direction == "down" else -1
        steps = random.randint(3, 8)
        per_step = distance / steps

        for _i in range(steps):
            delta = per_step * sign * random.uniform(0.8, 1.2)
            await self._page.mouse.wheel(0, delta)
            delay = self._log_normal_delay(median_ms=80, sigma=0.6) / 1000
            await asyncio.sleep(delay)
            if random.random() < 0.15:
                await asyncio.sleep(random.uniform(0.3, 0.8))

    async def type_text(self, selector: str, text: str) -> None:
        """Type text with realistic inter-key delays."""
        if not self._config.typing_simulation:
            await self._page.fill(selector, text)
            return

        await self._page.click(selector)
        for char in text:
            await self._page.keyboard.press(char)
            delay = self._log_normal_delay(median_ms=150, sigma=0.5) / 1000
            await asyncio.sleep(delay)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.3, 1.0))

    async def click_element(self, selector: str) -> None:
        """Move to element with bezier curve, then click with slight position offset."""
        element = self._page.locator(selector)
        box = await element.bounding_box()
        if box is None:
            await element.click()
            return

        target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        await self.move_mouse_to(target_x, target_y)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await self._page.mouse.click(target_x, target_y)

    async def idle_behavior(self, duration_ms: int = 3000) -> None:
        """Simulate idle user: small mouse movements, occasional scrolls."""
        elapsed = 0.0
        while elapsed < duration_ms:
            action = random.choice(["mouse", "scroll", "wait"])
            if action == "mouse":
                viewport = self._page.viewport_size or {"width": 1920, "height": 1080}
                x = random.uniform(100, viewport["width"] - 100)
                y = random.uniform(100, viewport["height"] - 100)
                await self._page.mouse.move(x, y)
                wait = random.uniform(200, 800)
            elif action == "scroll":
                delta = random.uniform(-50, 50)
                await self._page.mouse.wheel(0, delta)
                wait = random.uniform(300, 1000)
            else:
                wait = random.uniform(500, 1500)
            await asyncio.sleep(wait / 1000)
            elapsed += wait

    async def exploratory_hover(self) -> None:
        """Hover over random non-target elements briefly."""
        if not self._config.exploratory_interactions:
            return
        links = await self._page.locator("a, button").all()
        if not links:
            return
        element = random.choice(links[:10])
        box = await element.bounding_box()
        if box:
            await self.move_mouse_to(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] / 2,
            )
            await asyncio.sleep(random.uniform(0.1, 0.5))

    @staticmethod
    def _bezier_points(
        start: tuple[float, float], end: tuple[float, float], steps: int = 20
    ) -> list[tuple[float, float]]:
        """Generate bezier curve control points for natural mouse movement."""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        cp1 = (
            start[0] + dx * random.uniform(0.2, 0.4) + random.uniform(-50, 50),
            start[1] + dy * random.uniform(0.0, 0.3) + random.uniform(-50, 50),
        )
        cp2 = (
            start[0] + dx * random.uniform(0.6, 0.8) + random.uniform(-30, 30),
            start[1] + dy * random.uniform(0.7, 1.0) + random.uniform(-30, 30),
        )
        points: list[tuple[float, float]] = []
        for i in range(1, steps + 1):
            t = i / steps
            inv_t = 1 - t
            x = inv_t**3 * start[0] + 3 * inv_t**2 * t * cp1[0] + 3 * inv_t * t**2 * cp2[0] + t**3 * end[0]
            y = inv_t**3 * start[1] + 3 * inv_t**2 * t * cp1[1] + 3 * inv_t * t**2 * cp2[1] + t**3 * end[1]
            points.append((x, y))
        return points

    @staticmethod
    def _log_normal_delay(median_ms: float = 150, sigma: float = 0.5) -> float:
        """Generate a log-normally distributed delay."""
        return random.lognormvariate(math.log(median_ms), sigma)
