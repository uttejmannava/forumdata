"""Single page extraction setup — navigate to URL, extract from one page."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import Page

from forum_agents.agents.base import AgentContext, AgentResult
from forum_agents.agents.extraction import ExtractionResult, run_extraction
from forum_agents.agents.navigation import NavigationResult, run_navigation
from forum_agents.agents.search import SearchResult


@dataclass
class SetupResult(AgentResult):
    """Combined result from a navigation mode setup."""

    search: SearchResult | None = None
    navigation: NavigationResult | None = None
    extraction: ExtractionResult | None = None


async def setup_single_page(
    ctx: AgentContext,
    search_result: SearchResult,
    page: Page,
) -> SetupResult:
    """Single page extraction setup. No navigation complexity."""
    result = SetupResult(success=False, search=search_result)

    # Navigation is trivial for single page
    nav = await run_navigation(ctx, search_result, page)
    result.navigation = nav
    result.llm_calls += nav.llm_calls
    result.total_tokens += nav.total_tokens

    if not nav.success:
        result.errors.extend(nav.errors)
        return result

    # Extract from the single page
    sample_html = nav.sample_html[0] if nav.sample_html else search_result.page_html
    extraction = await run_extraction(ctx, search_result, page, sample_html)
    result.extraction = extraction
    result.llm_calls += extraction.llm_calls
    result.total_tokens += extraction.total_tokens

    if not extraction.success:
        result.errors.extend(extraction.errors)
        return result

    result.success = True
    return result
