"""Tests for response cache."""

from __future__ import annotations

from pathlib import Path

from forum_browser.cache import CacheConfig, ResponseCache


class TestResponseCache:
    async def test_put_and_get(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache", ttl_seconds=60)
        cache = ResponseCache(config)
        await cache.put(
            "https://example.com",
            200,
            {"content-type": "text/html"},
            "<html>body</html>",
        )
        result = await cache.get("https://example.com")
        assert result is not None
        assert result.status_code == 200
        assert result.body == "<html>body</html>"
        assert result.url == "https://example.com"

    async def test_miss(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache")
        cache = ResponseCache(config)
        result = await cache.get("https://missing.com")
        assert result is None

    async def test_ttl_expiration(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache", ttl_seconds=0)
        cache = ResponseCache(config)
        await cache.put("https://example.com", 200, {}, "body")
        # TTL of 0 means immediately expired
        result = await cache.get("https://example.com")
        assert result is None

    async def test_invalidate(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache", ttl_seconds=60)
        cache = ResponseCache(config)
        await cache.put("https://example.com", 200, {}, "body")
        await cache.invalidate("https://example.com")
        result = await cache.get("https://example.com")
        assert result is None

    async def test_clear(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache", ttl_seconds=60)
        cache = ResponseCache(config)
        await cache.put("https://a.com", 200, {}, "a")
        await cache.put("https://b.com", 200, {}, "b")
        await cache.clear()
        assert await cache.get("https://a.com") is None
        assert await cache.get("https://b.com") is None

    async def test_max_size_skips(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache", max_size_bytes=10)
        cache = ResponseCache(config)
        await cache.put("https://example.com", 200, {}, "x" * 100)
        result = await cache.get("https://example.com")
        assert result is None  # Too large, should have been skipped

    async def test_timestamp_bucket_in_cache_key(self, tmp_path: Path) -> None:
        """Cache keys include a timestamp bucket derived from ttl_seconds."""
        config = CacheConfig(cache_dir=tmp_path / "cache", ttl_seconds=300)
        cache = ResponseCache(config)
        # Two calls within the same 5-minute bucket should produce the same key
        key1 = cache._cache_key("https://example.com", None)
        key2 = cache._cache_key("https://example.com", None)
        assert key1 == key2

    async def test_region_isolation(self, tmp_path: Path) -> None:
        config = CacheConfig(cache_dir=tmp_path / "cache", ttl_seconds=60)
        cache = ResponseCache(config)
        await cache.put("https://example.com", 200, {}, "us-body", region="US")
        await cache.put("https://example.com", 200, {}, "eu-body", region="EU")
        us = await cache.get("https://example.com", region="US")
        eu = await cache.get("https://example.com", region="EU")
        assert us is not None
        assert eu is not None
        assert us.body == "us-body"
        assert eu.body == "eu-body"
