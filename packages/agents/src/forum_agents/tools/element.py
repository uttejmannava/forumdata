"""Element resolution tools wrapping forum_browser.resolution for agent use."""

from __future__ import annotations

from playwright.async_api import Page

from forum_browser.resolution.fingerprints import capture_fingerprint, find_by_fingerprint
from forum_browser.resolution.similarity import (
    find_by_regex,
    find_by_text,
    find_similar,
    generate_selector,
)
from forum_browser.resolution.storage import FingerprintStorage

from forum_agents.tools.browser import ToolResult


async def tool_find_by_text(
    page: Page,
    text: str,
    *,
    exact: bool = False,
    case_sensitive: bool = False,
) -> ToolResult:
    """Find elements matching text content."""
    try:
        selectors = await find_by_text(page, text, exact=exact, case_sensitive=case_sensitive)
        return ToolResult(success=True, data={"selectors": selectors, "count": len(selectors)})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def tool_find_by_regex(page: Page, pattern: str) -> ToolResult:
    """Find elements matching a regex pattern."""
    try:
        selectors = await find_by_regex(page, pattern)
        return ToolResult(success=True, data={"selectors": selectors, "count": len(selectors)})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def tool_find_similar(
    page: Page, reference_selector: str, *, threshold: float = 0.7
) -> ToolResult:
    """Find elements similar to a reference element."""
    try:
        selectors = await find_similar(page, reference_selector, threshold=threshold)
        return ToolResult(success=True, data={"selectors": selectors, "count": len(selectors)})
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def tool_generate_selector(page: Page, element_description: str) -> ToolResult:
    """Generate a CSS selector from a natural language element description."""
    try:
        selector = await generate_selector(page, element_description)
        return ToolResult(
            success=selector is not None,
            data={"selector": selector},
            error=None if selector else "Could not generate selector",
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=str(e))


async def save_fingerprint(
    page: Page,
    selector: str,
    identifier: str,
    storage: FingerprintStorage,
    tenant_id: str,
    pipeline_id: str,
) -> ToolResult:
    """Capture and save an element fingerprint for future self-healing."""
    try:
        fingerprint = await capture_fingerprint(page, selector, identifier)
        await storage.save(tenant_id, pipeline_id, identifier, fingerprint)
        return ToolResult(
            success=True,
            data={
                "identifier": identifier,
                "selector": selector,
                "tag_name": fingerprint.tag_name,
            },
        )
    except Exception as e:
        return ToolResult(success=False, data={"selector": selector}, error=str(e))


async def adaptive_match(
    page: Page,
    identifier: str,
    storage: FingerprintStorage,
    tenant_id: str,
    pipeline_id: str,
    *,
    threshold: float = 0.6,
) -> ToolResult:
    """Find an element using its stored fingerprint."""
    try:
        fingerprint = await storage.load(tenant_id, pipeline_id, identifier)
        if fingerprint is None:
            return ToolResult(
                success=False,
                data={"identifier": identifier},
                error="No stored fingerprint found",
            )
        matches = await find_by_fingerprint(page, fingerprint, threshold=threshold)
        return ToolResult(
            success=len(matches) > 0,
            data={
                "identifier": identifier,
                "matches": [{"selector": s, "score": sc} for s, sc in matches],
            },
        )
    except Exception as e:
        return ToolResult(success=False, data={"identifier": identifier}, error=str(e))
