"""Paginated list extraction setup — auto-detect and handle pagination."""

from __future__ import annotations

from playwright.async_api import Page

from forum_agents.agents.base import AgentContext
from forum_agents.agents.extraction import run_extraction
from forum_agents.agents.navigation import run_navigation
from forum_agents.agents.search import SearchResult
from forum_agents.nav_modes.single_page import SetupResult


async def setup_paginated_list(
    ctx: AgentContext,
    search_result: SearchResult,
    page: Page,
) -> SetupResult:
    """Paginated list extraction setup."""
    result = SetupResult(success=False, search=search_result)

    # Navigation agent generates pagination loop
    nav = await run_navigation(ctx, search_result, page)
    result.navigation = nav
    result.llm_calls += nav.llm_calls
    result.total_tokens += nav.total_tokens

    if not nav.success:
        result.errors.extend(nav.errors)
        return result

    # Extract from first page (representative sample)
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
