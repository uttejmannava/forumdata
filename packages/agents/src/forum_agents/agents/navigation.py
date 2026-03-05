"""Navigation Agent — generates Playwright code for reaching data pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page

from forum_agents.agents.base import AgentContext, AgentResult
from forum_agents.agents.search import SearchResult
from forum_agents.llm_gateway import AgentRole
from forum_agents.prompts import navigation_codegen
from forum_agents.tools.dom import get_page_structure


@dataclass
class NavigationResult(AgentResult):
    """Result from the Navigation Agent."""

    navigation_code: str = ""
    pages_found: int = 0
    sample_html: list[str] = field(default_factory=list)


_SINGLE_PAGE_TEMPLATE = '''async def navigate(page, config: dict) -> list[str]:
    """Navigate to a single page and return its HTML."""
    url = config["url"]
    await page.goto(url, wait_until="networkidle", timeout=30000)
    html = await page.content()
    return [html]
'''


async def run_navigation(
    ctx: AgentContext,
    search_result: SearchResult,
    page: Page,
) -> NavigationResult:
    """Generate navigation code based on search analysis."""
    result = NavigationResult(success=False)

    try:
        # Single page — no LLM needed, use template
        if not search_result.pagination:
            result.navigation_code = _SINGLE_PAGE_TEMPLATE
            result.pages_found = 1
            result.sample_html = [search_result.page_html] if search_result.page_html else []
            result.success = True
            return result

        # Paginated — use LLM to generate navigation loop
        structure = await get_page_structure(page)
        page_skeleton = structure.data.get("skeleton", "") if structure.success else ""

        system_prompt = navigation_codegen.build_system_prompt()
        user_message = navigation_codegen.build_user_message(
            url=ctx.source_url,
            pagination=search_result.pagination,
            page_structure=page_skeleton,
        )

        llm_response = await ctx.llm.complete(
            AgentRole.NAVIGATION_CODEGEN,
            system_prompt,
            [{"role": "user", "content": user_message}],
        )
        result.llm_calls = 1
        result.total_tokens = llm_response.input_tokens + llm_response.output_tokens

        code = _clean_code(llm_response.content)

        # Validate generated code is syntactically valid
        try:
            compile(code, "<navigation>", "exec")
        except SyntaxError as e:
            result.errors.append(f"EXTRACTION_FAILED: Generated navigation code has syntax error: {e}")
            result.navigation_code = code
            return result

        result.navigation_code = code

        # Execute navigation to collect sample pages
        sample_html = await _execute_navigation(page, code, ctx.source_url)
        result.sample_html = sample_html
        result.pages_found = len(sample_html)
        result.success = True

    except Exception as e:
        result.errors.append(f"EXTRACTION_FAILED: {e}")

    return result


def _clean_code(content: str) -> str:
    """Strip markdown fences and clean up LLM-generated code."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return text.strip()


async def _execute_navigation(page: Page, code: str, url: str) -> list[str]:
    """Execute generated navigation code and return HTML snapshots."""
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102

    navigate_fn = namespace.get("navigate")
    if navigate_fn is None:
        return []

    config = {"url": url, "max_pages": 3}
    try:
        result = await navigate_fn(page, config)
        if isinstance(result, list):
            return [str(h) for h in result[:5]]
    except Exception:
        pass

    return []
