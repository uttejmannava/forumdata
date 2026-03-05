"""Session-level stealth — warming, referrer chains, persistent browser profiles."""

from __future__ import annotations

import contextlib
import json
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.async_api import BrowserContext, Page


_COOKIE_CONSENT_SELECTORS = [
    "button:has-text('Accept')",
    "button:has-text('Accept All')",
    "button:has-text('Accept Cookies')",
    "button:has-text('I Agree')",
    "button:has-text('OK')",
    "button:has-text('Got it')",
    "[id*='cookie'] button",
    "[class*='cookie'] button",
    "[id*='consent'] button",
    "[class*='consent'] button",
    "[id*='gdpr'] button",
]


@dataclass(frozen=True)
class SessionConfig:
    """Session-level stealth configuration."""

    warming_enabled: bool = True
    accept_cookies: bool = True
    referrer_chain: bool = True
    persistent_profile_dir: Path | None = None


class SessionManager:
    """Manages session-level stealth behaviors."""

    def __init__(self, config: SessionConfig | None = None) -> None:
        self._config = config or SessionConfig()

    async def warm_session(self, page: Page, target_url: str) -> None:
        """Build realistic session history before extraction."""
        if not self._config.warming_enabled:
            return

        parsed = urlparse(target_url)
        homepage = f"{parsed.scheme}://{parsed.netloc}/"

        try:
            await page.goto(homepage, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            return

        if self._config.accept_cookies:
            consent_btn = await self._find_cookie_consent(page)
            if consent_btn:
                with contextlib.suppress(Exception):
                    await page.click(consent_btn, timeout=3000)

        links = await page.locator("a[href^='/']").all()
        internal_links = links[:20]
        if internal_links:
            chosen = random.sample(internal_links, min(2, len(internal_links)))
            for link in chosen:
                href = await link.get_attribute("href")
                if href:
                    try:
                        full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                        await page.goto(full_url, wait_until="domcontentloaded", timeout=10000)
                        await page.wait_for_timeout(random.randint(500, 1500))
                    except Exception:
                        break

    async def construct_referrer(self, page: Page, target_url: str) -> str:
        """Build a realistic referrer chain for the target URL."""
        if not self._config.referrer_chain:
            return ""

        parsed = urlparse(target_url)
        strategies = [
            f"https://www.google.com/search?q={parsed.netloc}",
            f"{parsed.scheme}://{parsed.netloc}/",
            "",
        ]
        return random.choice(strategies)

    async def save_browser_profile(self, context: BrowserContext, pipeline_id: str) -> None:
        """Save cookies, localStorage, and session storage for reuse across runs."""
        if self._config.persistent_profile_dir is None:
            return

        profile_dir = self._config.persistent_profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)

        state = await context.storage_state()
        profile_path = profile_dir / f"{pipeline_id}.json"
        profile_path.write_text(json.dumps(state, indent=2))

    async def load_browser_profile(self, context: BrowserContext, pipeline_id: str) -> bool:
        """Load a previously saved browser profile. Returns True if profile existed."""
        if self._config.persistent_profile_dir is None:
            return False

        profile_path = self._config.persistent_profile_dir / f"{pipeline_id}.json"
        if not profile_path.exists():
            return False

        state = json.loads(profile_path.read_text())
        for cookie in state.get("cookies", []):
            await context.add_cookies([cookie])
        return True

    async def _find_cookie_consent(self, page: Page) -> str | None:
        """Detect common cookie consent buttons/banners."""
        for selector in _COOKIE_CONSENT_SELECTORS:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=1000):
                    return selector
            except Exception:
                continue
        return None
