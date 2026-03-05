"""Proxy rotation interface with geo-targeting."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass


class ProxyType(enum.StrEnum):
    DATACENTER = "datacenter"
    RESIDENTIAL = "residential"


@dataclass(frozen=True)
class ProxyConfig:
    """Proxy configuration."""

    url: str
    proxy_type: ProxyType = ProxyType.DATACENTER
    region: str | None = None
    username: str | None = None
    password: str | None = None


class ProxyRotator:
    """Manages a pool of proxies with rotation and health monitoring."""

    def __init__(self, proxies: list[ProxyConfig] | None = None, *, cooldown_seconds: float = 60.0) -> None:
        self._proxies: list[ProxyConfig] = list(proxies) if proxies else []
        self._failed: dict[str, float] = {}  # proxy url -> failure timestamp
        self._cooldown = cooldown_seconds
        self._index = 0

    def get_proxy(self, *, region: str | None = None, proxy_type: ProxyType | None = None) -> ProxyConfig | None:
        """Get next proxy from pool, optionally filtered by region/type."""
        available = self._get_available(region=region, proxy_type=proxy_type)
        if not available:
            return None
        proxy = available[self._index % len(available)]
        self._index += 1
        return proxy

    def mark_failed(self, proxy: ProxyConfig) -> None:
        """Mark a proxy as temporarily failed."""
        self._failed[proxy.url] = time.monotonic()

    def mark_healthy(self, proxy: ProxyConfig) -> None:
        """Mark a proxy as healthy again."""
        self._failed.pop(proxy.url, None)

    def add_proxy(self, proxy: ProxyConfig) -> None:
        """Add a proxy to the pool."""
        self._proxies.append(proxy)

    @property
    def available_count(self) -> int:
        """Number of currently available (non-failed) proxies."""
        return len(self._get_available())

    def _get_available(
        self, *, region: str | None = None, proxy_type: ProxyType | None = None
    ) -> list[ProxyConfig]:
        now = time.monotonic()
        result: list[ProxyConfig] = []
        for p in self._proxies:
            if region and p.region != region:
                continue
            if proxy_type and p.proxy_type != proxy_type:
                continue
            failed_at = self._failed.get(p.url)
            if failed_at and (now - failed_at) < self._cooldown:
                continue
            result.append(p)
        return result
