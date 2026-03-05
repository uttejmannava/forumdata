"""Search Agent — page/API discovery and classification."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.network import NetworkInterceptor
from forum_browser.stealth.calibrator import StealthCalibrator

from forum_schemas.models.pipeline import NavigationMode, StealthLevel

from forum_agents.agents.base import AgentContext, AgentResult
from forum_agents.llm_gateway import AgentRole
from forum_agents.prompts import page_analysis
from forum_agents.tools.browser import navigate
from forum_agents.tools.compliance import check_llms_txt, check_robots_txt
from forum_agents.tools.dom import get_accessibility_tree, get_page_structure


@dataclass
class SearchResult(AgentResult):
    """Result from the Search Agent."""

    page_type: str = ""
    api_candidates: list[dict[str, Any]] = field(default_factory=list)
    data_regions: list[dict[str, str]] = field(default_factory=list)
    recommended_nav_mode: NavigationMode = NavigationMode.SINGLE_PAGE
    stealth_level: StealthLevel = StealthLevel.NONE
    pagination: dict[str, Any] | None = None
    has_llms_txt: bool = False
    robots_allowed: bool = True
    page_html: str = ""


async def run_search(ctx: AgentContext, page: Page | None = None) -> SearchResult:
    """Execute the search agent to analyze a source URL.

    If `page` is provided, uses it directly. Otherwise creates a browser session.
    """
    result = SearchResult(success=False)

    # 1. Check compliance (robots.txt + llms.txt)
    robots = await check_robots_txt(ctx.source_url)
    result.robots_allowed = robots.allowed
    if not robots.allowed:
        result.errors.append(f"COMPLIANCE_BLOCKED: {robots.reason}")
        return result

    llms = await check_llms_txt(ctx.source_url)
    result.has_llms_txt = llms.details.get("has_llms_txt", False)

    # 2. Determine stealth level
    if result.has_llms_txt:
        result.stealth_level = StealthLevel.NONE
    elif robots.recommended_stealth:
        result.stealth_level = robots.recommended_stealth
    else:
        try:
            calibrator = StealthCalibrator()
            cal_result = await calibrator.calibrate(ctx.source_url)
            result.stealth_level = cal_result.recommended_level
        except Exception:
            result.stealth_level = StealthLevel.BASIC

    # 3. Load page and analyze
    owns_page = page is None
    browser = None

    try:
        if owns_page:
            if result.stealth_level == StealthLevel.NONE:
                config = BrowserConfig(stealth_level=StealthLevel.BASIC)
            else:
                config = BrowserConfig(stealth_level=result.stealth_level)
            browser = ForumBrowser(config)
            await browser.__aenter__()
            page = await browser.new_page()

        assert page is not None

        # Install network interceptor to capture API traffic
        interceptor = NetworkInterceptor()
        await interceptor.install(page)

        # Navigate to URL
        nav_result = await navigate(page, ctx.source_url)
        if not nav_result.success:
            result.errors.append(f"SOURCE_UNAVAILABLE: {nav_result.error}")
            return result

        # Get page content
        result.page_html = await page.content()

        # Capture API candidates
        api_candidates_raw = interceptor.get_api_candidates()
        result.api_candidates = [
            {
                "url": c.url,
                "method": c.method,
                "response_status": c.response_status,
                "response_content_type": c.response_content_type,
            }
            for c in api_candidates_raw
        ]

        await interceptor.uninstall(page)

        # 4. Analyze page with DOM tools
        a11y = await get_accessibility_tree(page)
        structure = await get_page_structure(page)

        a11y_tree = a11y.data.get("tree", "") if a11y.success else ""
        page_skeleton = structure.data.get("skeleton", "") if structure.success else ""

        # 5. Use LLM to classify page
        system_prompt = page_analysis.build_system_prompt()
        user_message = page_analysis.build_user_message(
            url=ctx.source_url,
            user_description=ctx.user_description,
            accessibility_tree=a11y_tree,
            page_structure=page_skeleton,
            api_candidates=result.api_candidates if result.api_candidates else None,
        )

        llm_response = await ctx.llm.complete(
            AgentRole.PAGE_ANALYSIS,
            system_prompt,
            [{"role": "user", "content": user_message}],
        )
        result.llm_calls = 1
        result.total_tokens = llm_response.input_tokens + llm_response.output_tokens

        # Parse LLM response
        analysis = _parse_analysis(llm_response.content)
        result.page_type = analysis.get("page_type", "static_html")
        result.data_regions = analysis.get("data_regions", [])
        result.pagination = analysis.get("pagination")

        nav_mode_str = analysis.get("recommended_nav_mode", "SINGLE_PAGE")
        try:
            result.recommended_nav_mode = NavigationMode(nav_mode_str)
        except ValueError:
            result.recommended_nav_mode = NavigationMode.SINGLE_PAGE

        # Override to API_DISCOVERY if we found good API candidates
        if result.api_candidates and result.page_type == "spa_with_api":
            result.recommended_nav_mode = NavigationMode.API_DISCOVERY

        result.success = True

    except Exception as e:
        result.errors.append(f"EXTRACTION_FAILED: {e}")
    finally:
        if owns_page and browser:
            await browser.__aexit__(None, None, None)

    return result


def _parse_analysis(content: str) -> dict[str, Any]:
    """Parse LLM JSON response, handling potential markdown wrapping."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        return {"page_type": "static_html", "data_regions": [], "recommended_nav_mode": "SINGLE_PAGE"}
