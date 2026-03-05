"""Browser action tools that wrap forum_browser for agent use."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from playwright.async_api import Page


@dataclass
class ToolResult:
    """Structured result from a tool invocation."""

    success: bool
    data: dict[str, Any]
    error: str | None = None


async def navigate(page: Page, url: str) -> ToolResult:
    """Navigate to a URL and wait for load."""
    try:
        response = await page.goto(url, wait_until="networkidle", timeout=30000)
        status = response.status if response else None
        return ToolResult(
            success=status is not None and status < 400,
            data={"url": page.url, "status": status},
        )
    except Exception as e:
        return ToolResult(success=False, data={"url": url}, error=str(e))


async def click(page: Page, selector: str) -> ToolResult:
    """Click an element by CSS selector."""
    try:
        await page.click(selector, timeout=5000)
        return ToolResult(success=True, data={"selector": selector})
    except Exception as e:
        return ToolResult(success=False, data={"selector": selector}, error=str(e))


async def type_text(page: Page, selector: str, text: str) -> ToolResult:
    """Type text into an input element."""
    try:
        await page.fill(selector, text, timeout=5000)
        return ToolResult(success=True, data={"selector": selector, "text": text})
    except Exception as e:
        return ToolResult(success=False, data={"selector": selector}, error=str(e))


async def scroll_down(page: Page, pixels: int = 500) -> ToolResult:
    """Scroll the page down by a number of pixels."""
    try:
        await page.evaluate(f"window.scrollBy(0, {pixels})")
        scroll_y = await page.evaluate("window.scrollY")
        return ToolResult(success=True, data={"scroll_y": scroll_y, "pixels": pixels})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def screenshot(page: Page, path: str | None = None) -> ToolResult:
    """Take a screenshot of the page, returning base64-encoded PNG."""
    try:
        raw = await page.screenshot(path=path, full_page=False)
        return ToolResult(
            success=True,
            data={
                "path": path,
                "size_bytes": len(raw),
                "base64": base64.b64encode(raw).decode() if path is None else None,
            },
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def get_page_content(page: Page) -> ToolResult:
    """Get the full HTML content of the page."""
    try:
        html = await page.content()
        return ToolResult(success=True, data={"html": html, "length": len(html)})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def get_page_url(page: Page) -> ToolResult:
    """Get the current URL of the page."""
    return ToolResult(success=True, data={"url": page.url})
