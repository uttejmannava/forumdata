"""Wait helpers, retry logic, element interaction patterns."""

from __future__ import annotations

import asyncio
import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


async def wait_human_like(min_ms: int = 500, max_ms: int = 2000) -> None:
    """Wait a random human-like duration (log-normal distribution)."""
    median = (min_ms + max_ms) / 2
    sigma = 0.4
    delay_ms = random.lognormvariate(math.log(median), sigma)
    delay_ms = max(min_ms, min(max_ms, delay_ms))
    await asyncio.sleep(delay_ms / 1000.0)


async def retry_with_backoff[T](
    coro_factory: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> T:
    """Retry an async operation with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            await asyncio.sleep(delay + jitter)
    raise last_exc  # type: ignore[misc]
