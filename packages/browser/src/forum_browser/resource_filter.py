"""Configurable resource blocking via Playwright network interception."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.async_api import Page, Route


@dataclass(frozen=True)
class ResourceFilterConfig:
    """What to block during page loads."""

    blocked_types: frozenset[str] = frozenset({"image", "media", "font"})
    blocked_domains: frozenset[str] = frozenset()
    allow_stylesheets: bool = False


async def install_resource_filter(page: Page, config: ResourceFilterConfig) -> None:
    """Install route handler on page to block configured resources."""
    effective_types = set(config.blocked_types)
    if config.allow_stylesheets:
        effective_types.discard("stylesheet")
    frozen_types = frozenset(effective_types)
    frozen_domains = config.blocked_domains

    async def _handle_route(route: Route) -> None:
        request = route.request
        if request.resource_type in frozen_types:
            await route.abort()
            return
        if frozen_domains and _matches_blocked_domain(request.url, frozen_domains):
            await route.abort()
            return
        await route.continue_()

    await page.route("**/*", _handle_route)


def _matches_blocked_domain(url: str, blocked_domains: frozenset[str]) -> bool:
    """Check if URL matches any blocked domain (with subdomain auto-matching)."""
    try:
        hostname = urlparse(url).hostname
    except Exception:
        return False
    if hostname is None:
        return False
    return any(hostname == domain or hostname.endswith("." + domain) for domain in blocked_domains)
