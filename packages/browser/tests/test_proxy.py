"""Tests for proxy rotation."""

from __future__ import annotations

from forum_browser.proxy import ProxyConfig, ProxyRotator, ProxyType


class TestProxyConfig:
    def test_defaults(self) -> None:
        config = ProxyConfig(url="http://proxy:8080")
        assert config.proxy_type == ProxyType.DATACENTER
        assert config.region is None


class TestProxyRotator:
    def test_empty_pool(self) -> None:
        rotator = ProxyRotator()
        assert rotator.get_proxy() is None
        assert rotator.available_count == 0

    def test_round_robin(self) -> None:
        proxies = [
            ProxyConfig(url="http://proxy1:8080"),
            ProxyConfig(url="http://proxy2:8080"),
            ProxyConfig(url="http://proxy3:8080"),
        ]
        rotator = ProxyRotator(proxies)
        urls = [rotator.get_proxy().url for _ in range(6)]  # type: ignore[union-attr]
        assert urls == [
            "http://proxy1:8080",
            "http://proxy2:8080",
            "http://proxy3:8080",
            "http://proxy1:8080",
            "http://proxy2:8080",
            "http://proxy3:8080",
        ]

    def test_filter_by_region(self) -> None:
        proxies = [
            ProxyConfig(url="http://us:8080", region="US"),
            ProxyConfig(url="http://eu:8080", region="EU"),
        ]
        rotator = ProxyRotator(proxies)
        proxy = rotator.get_proxy(region="EU")
        assert proxy is not None
        assert proxy.url == "http://eu:8080"

    def test_filter_by_type(self) -> None:
        proxies = [
            ProxyConfig(url="http://dc:8080", proxy_type=ProxyType.DATACENTER),
            ProxyConfig(url="http://res:8080", proxy_type=ProxyType.RESIDENTIAL),
        ]
        rotator = ProxyRotator(proxies)
        proxy = rotator.get_proxy(proxy_type=ProxyType.RESIDENTIAL)
        assert proxy is not None
        assert proxy.url == "http://res:8080"

    def test_mark_failed_excludes(self) -> None:
        proxies = [
            ProxyConfig(url="http://proxy1:8080"),
            ProxyConfig(url="http://proxy2:8080"),
        ]
        rotator = ProxyRotator(proxies, cooldown_seconds=300)
        rotator.mark_failed(proxies[0])
        assert rotator.available_count == 1
        proxy = rotator.get_proxy()
        assert proxy is not None
        assert proxy.url == "http://proxy2:8080"

    def test_mark_healthy_restores(self) -> None:
        proxies = [ProxyConfig(url="http://proxy1:8080")]
        rotator = ProxyRotator(proxies, cooldown_seconds=300)
        rotator.mark_failed(proxies[0])
        assert rotator.available_count == 0
        rotator.mark_healthy(proxies[0])
        assert rotator.available_count == 1

    def test_add_proxy(self) -> None:
        rotator = ProxyRotator()
        rotator.add_proxy(ProxyConfig(url="http://new:8080"))
        assert rotator.available_count == 1

    def test_no_match_returns_none(self) -> None:
        proxies = [ProxyConfig(url="http://proxy:8080", region="US")]
        rotator = ProxyRotator(proxies)
        assert rotator.get_proxy(region="JP") is None
