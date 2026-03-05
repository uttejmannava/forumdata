"""Resolution cascade orchestrator — tiered element resolution."""

from __future__ import annotations

import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from forum_browser.resolution.fingerprints import (
    ElementFingerprint,
    capture_fingerprint,
    find_by_fingerprint,
)
from forum_browser.resolution.similarity import find_by_regex, find_by_text, find_similar

if TYPE_CHECKING:
    from playwright.async_api import Page

    from forum_browser.resolution.storage import FingerprintStorage


class ResolutionTier(enum.StrEnum):
    DIRECT_SELECTOR = "direct_selector"
    FINGERPRINT_MATCH = "fingerprint_match"
    CONTENT_MATCH = "content_match"
    SIMILARITY_MATCH = "similarity_match"
    LLM_RELOCATION = "llm_relocation"


@dataclass
class ResolutionResult:
    """Result of element resolution."""

    selector: str
    tier: ResolutionTier
    confidence: float
    element_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


LlmRelocator = Callable[["Page", ElementFingerprint, dict[str, Any]], Awaitable[ResolutionResult | None]]


class ResolutionError(Exception):
    """Raised when all resolution tiers fail."""


class ResolutionCascade:
    """Orchestrates tiered element resolution."""

    def __init__(
        self,
        storage: FingerprintStorage,
        *,
        llm_relocator: LlmRelocator | None = None,
        tenant_id: str = "default",
        pipeline_id: str = "default",
    ) -> None:
        self._storage = storage
        self._llm_relocator = llm_relocator
        self._tenant_id = tenant_id
        self._pipeline_id = pipeline_id

    async def resolve(
        self,
        page: Page,
        selector: str,
        identifier: str,
        *,
        expected_text: str | None = None,
        expected_pattern: str | None = None,
    ) -> ResolutionResult:
        """Resolve an element using the cascade."""
        # Tier 1: Direct selector
        result = await self._try_direct_selector(page, selector)
        if result:
            await self.update_fingerprint(page, selector, identifier)
            return result

        # Tier 2: Fingerprint match
        result = await self._try_fingerprint(page, identifier)
        if result:
            return result

        # Tier 3: Content/similarity search
        result = await self._try_content_search(
            page, identifier, expected_text=expected_text, expected_pattern=expected_pattern
        )
        if result:
            return result

        # Tier 4: LLM relocation (if configured)
        if self._llm_relocator:
            fp = await self._storage.load(self._tenant_id, self._pipeline_id, identifier)
            if fp:
                result = await self._llm_relocator(page, fp, {"selector": selector, "identifier": identifier})
                if result:
                    return result

        msg = f"All resolution tiers failed for '{identifier}' (selector: {selector})"
        raise ResolutionError(msg)

    async def _try_direct_selector(self, page: Page, selector: str) -> ResolutionResult | None:
        """Tier 1: Try the CSS/XPath selector directly."""
        try:
            count = await page.locator(selector).count()
            if count > 0:
                return ResolutionResult(
                    selector=selector,
                    tier=ResolutionTier.DIRECT_SELECTOR,
                    confidence=1.0,
                    element_count=count,
                )
        except Exception:
            pass
        return None

    async def _try_fingerprint(self, page: Page, identifier: str) -> ResolutionResult | None:
        """Tier 2: Load stored fingerprint, score all page elements."""
        fp = await self._storage.load(self._tenant_id, self._pipeline_id, identifier)
        if fp is None:
            return None

        matches = await find_by_fingerprint(page, fp)
        if matches:
            best_selector, best_score = matches[0]
            return ResolutionResult(
                selector=best_selector,
                tier=ResolutionTier.FINGERPRINT_MATCH,
                confidence=best_score,
                element_count=len(matches),
                metadata={"all_matches": matches[:5]},
            )
        return None

    async def _try_content_search(
        self,
        page: Page,
        identifier: str,
        *,
        expected_text: str | None,
        expected_pattern: str | None,
    ) -> ResolutionResult | None:
        """Tier 3: Try find_by_text, find_by_regex, find_similar."""
        if expected_text:
            selectors = await find_by_text(page, expected_text)
            if selectors:
                return ResolutionResult(
                    selector=selectors[0],
                    tier=ResolutionTier.CONTENT_MATCH,
                    confidence=0.7,
                    element_count=len(selectors),
                )

        if expected_pattern:
            selectors = await find_by_regex(page, expected_pattern)
            if selectors:
                return ResolutionResult(
                    selector=selectors[0],
                    tier=ResolutionTier.CONTENT_MATCH,
                    confidence=0.6,
                    element_count=len(selectors),
                )

        # Try structural similarity using stored fingerprint's original selector
        fp = await self._storage.load(self._tenant_id, self._pipeline_id, identifier)
        if fp and fp.css_selector:
            similar = await find_similar(page, fp.css_selector)
            if similar:
                return ResolutionResult(
                    selector=similar[0],
                    tier=ResolutionTier.SIMILARITY_MATCH,
                    confidence=0.5,
                    element_count=len(similar),
                )

        return None

    async def update_fingerprint(self, page: Page, selector: str, identifier: str) -> None:
        """Save/update fingerprint after successful resolution."""
        try:
            fp = await capture_fingerprint(page, selector, identifier)
            await self._storage.save(self._tenant_id, self._pipeline_id, identifier, fp)
        except Exception:
            pass
