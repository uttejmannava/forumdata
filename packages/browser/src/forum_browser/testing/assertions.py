"""Test assertion helpers for browser testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

    from forum_browser.resolution.cascade import ResolutionResult, ResolutionTier
    from forum_browser.resolution.fingerprints import ElementFingerprint
    from forum_browser.stealth.signals import SignalMonitor


async def assert_element_exists(page: Page, selector: str, *, timeout_ms: int = 5000) -> None:
    """Assert that an element matching the selector exists on the page."""
    locator = page.locator(selector)
    count = await locator.count()
    if count == 0:
        msg = f"Expected element '{selector}' to exist, but none found"
        raise AssertionError(msg)


async def assert_element_text(page: Page, selector: str, expected: str, *, exact: bool = False) -> None:
    """Assert that an element's text content matches expected."""
    locator = page.locator(selector).first
    text = await locator.text_content()
    if text is None:
        msg = f"Element '{selector}' has no text content"
        raise AssertionError(msg)
    if exact:
        if text.strip() != expected:
            msg = f"Expected '{expected}', got '{text.strip()}'"
            raise AssertionError(msg)
    elif expected not in text:
        msg = f"Expected '{expected}' in '{text}'"
        raise AssertionError(msg)


async def assert_no_detection_signals(monitor: SignalMonitor) -> None:
    """Assert that no detection signals were recorded."""
    if monitor.is_detected:
        events = monitor.events
        msg = f"Detection signals recorded: {[e.signal.value for e in events]}"
        raise AssertionError(msg)


async def assert_resolution_tier(result: ResolutionResult, expected_tier: ResolutionTier) -> None:
    """Assert that resolution used the expected tier."""
    if result.tier != expected_tier:
        msg = f"Expected tier '{expected_tier}', got '{result.tier}'"
        raise AssertionError(msg)


def assert_fingerprint_similarity(
    fp1: ElementFingerprint, fp2: ElementFingerprint, *, min_score: float = 0.8
) -> None:
    """Assert that two fingerprints are sufficiently similar."""
    from forum_browser.resolution.fingerprints import score_similarity

    score = score_similarity(fp1, fp2)
    if score < min_score:
        msg = f"Fingerprint similarity {score:.3f} below threshold {min_score}"
        raise AssertionError(msg)
