"""Local filesystem response cache for Phase 0."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class CacheConfig:
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".forum" / "cache")
    ttl_seconds: int = 300
    max_size_bytes: int = 5 * 1024 * 1024


@dataclass
class CachedResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    body: str
    cached_at: datetime
    cache_key: str


class ResponseCache:
    """Local filesystem response cache.

    Cache key includes a timestamp bucket so responses are naturally partitioned
    by time window. The bucket width equals ttl_seconds from the config.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or CacheConfig()
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(self, url: str, *, region: str | None = None) -> CachedResponse | None:
        """Check cache for a fresh response."""
        key = self._cache_key(url, region)
        cache_file = self._config.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        data = json.loads(cache_file.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        age = (datetime.now(UTC) - cached_at).total_seconds()
        if age > self._config.ttl_seconds:
            cache_file.unlink(missing_ok=True)
            return None

        return CachedResponse(
            url=data["url"],
            status_code=data["status_code"],
            headers=data["headers"],
            body=data["body"],
            cached_at=cached_at,
            cache_key=key,
        )

    async def put(
        self,
        url: str,
        status_code: int,
        headers: dict[str, str],
        body: str,
        *,
        region: str | None = None,
    ) -> None:
        """Store a response in the cache."""
        if len(body) > self._config.max_size_bytes:
            return

        key = self._cache_key(url, region)
        data = {
            "url": url,
            "status_code": status_code,
            "headers": headers,
            "body": body,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        cache_file = self._config.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps(data))

    async def invalidate(self, url: str, *, region: str | None = None) -> None:
        """Remove a cached response."""
        key = self._cache_key(url, region)
        cache_file = self._config.cache_dir / f"{key}.json"
        cache_file.unlink(missing_ok=True)

    async def clear(self) -> None:
        """Clear all cached responses."""
        for f in self._config.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)

    def _cache_key(self, url: str, region: str | None) -> str:
        """Generate cache key from URL, region, and timestamp bucket."""
        bucket = self._timestamp_bucket()
        raw = f"{url}:{region or 'default'}:{bucket}"
        return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324

    def _timestamp_bucket(self) -> str:
        """Current timestamp bucket for cache keying.

        Returns a string representing the current time window. The bucket width
        equals ttl_seconds — e.g., with ttl_seconds=300, all requests within
        the same 5-minute window share a cache key.
        """
        ttl = self._config.ttl_seconds
        if ttl <= 0:
            # No bucketing when TTL is zero/negative — every request gets a unique bucket
            return str(int(datetime.now(UTC).timestamp()))
        now = int(datetime.now(UTC).timestamp())
        bucket = now // ttl
        return str(bucket)
