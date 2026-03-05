"""Playwright trace capture for debugging failed extractions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.async_api import BrowserContext


async def start_tracing(
    context: BrowserContext, *, screenshots: bool = True, snapshots: bool = True
) -> None:
    """Start Playwright tracing on a context."""
    await context.tracing.start(screenshots=screenshots, snapshots=snapshots)


async def stop_tracing(context: BrowserContext, output_path: Path) -> Path:
    """Stop tracing and save to file. Returns the trace file path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    await context.tracing.stop(path=str(output_path))
    return output_path
