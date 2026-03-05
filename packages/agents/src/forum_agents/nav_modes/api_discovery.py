"""API discovery setup — detect and use underlying REST/GraphQL APIs."""

from __future__ import annotations

from typing import Any

from playwright.async_api import Page

from forum_agents.agents.base import AgentContext
from forum_agents.agents.search import SearchResult
from forum_agents.llm_gateway import AgentRole
from forum_agents.nav_modes.single_page import SetupResult


_API_EXTRACT_TEMPLATE = '''async def extract(page) -> list[dict]:
    """Extract data from API response.

    This extraction uses the StealthHttpClient instead of browser scraping.
    The page parameter is unused — kept for interface compatibility.
    """
    from forum_browser.http import StealthHttpClient

    async with StealthHttpClient() as client:
        resp = await client.get("{api_url}")
        import json
        data = json.loads(resp.text)
        {extract_logic}
    return rows
'''


async def setup_api_discovery(
    ctx: AgentContext,
    search_result: SearchResult,
    page: Page,
) -> SetupResult:
    """API discovery setup — find and use underlying REST/GraphQL APIs."""
    result = SetupResult(success=False, search=search_result)

    if not search_result.api_candidates:
        result.errors.append("EXTRACTION_FAILED: No API candidates found")
        return result

    # Pick best API candidate (prefer JSON, lowest status code)
    best = _pick_best_candidate(search_result.api_candidates)
    if not best:
        result.errors.append("EXTRACTION_FAILED: No suitable API candidate")
        return result

    # Use LLM to analyze the API response and generate extraction code
    api_url = best["url"]

    system_prompt = (
        "You are an expert API data extraction engineer.\n"
        "Given an API endpoint URL and the user's data needs, generate Python code "
        "that fetches and parses the API response.\n"
        "The code must define an `async def extract(page) -> list[dict]` function "
        "and a SELECTORS dict (use API field paths as values).\n"
        "Use forum_browser.http.StealthHttpClient for HTTP requests.\n"
        "Respond with ONLY Python code — no markdown, no explanation."
    )

    user_message = (
        f"API endpoint: {api_url}\n"
        f"User wants: {ctx.user_description}\n"
        f"API method: {best.get('method', 'GET')}\n"
        f"Response content type: {best.get('response_content_type', 'application/json')}\n\n"
        f"Generate extraction code that fetches this API and returns structured data."
    )

    try:
        llm_response = await ctx.llm.complete(
            AgentRole.EXTRACTION_CODEGEN,
            system_prompt,
            [{"role": "user", "content": user_message}],
        )
        result.llm_calls += 1
        result.total_tokens += llm_response.input_tokens + llm_response.output_tokens

        code = _clean_code(llm_response.content)

        try:
            compile(code, "<api_extraction>", "exec")
        except SyntaxError as e:
            result.errors.append(f"EXTRACTION_FAILED: Generated API code has syntax error: {e}")
            return result

        # Build a minimal extraction result
        from forum_agents.agents.extraction import ExtractionResult
        from forum_agents.agents.navigation import NavigationResult

        result.navigation = NavigationResult(
            success=True,
            navigation_code=f"# API mode — no browser navigation needed\n# API endpoint: {api_url}\n",
            pages_found=1,
        )
        result.extraction = ExtractionResult(
            success=True,
            extraction_code=code,
            schema={},
            selectors={"api_endpoint": api_url},
        )
        result.success = True

    except Exception as e:
        result.errors.append(f"EXTRACTION_FAILED: {e}")

    return result


def _pick_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the best API candidate from captured traffic."""
    json_candidates = [
        c for c in candidates
        if c.get("response_content_type", "").startswith("application/json")
    ]
    if json_candidates:
        return json_candidates[0]
    return candidates[0] if candidates else None


def _clean_code(content: str) -> str:
    """Strip markdown fences."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return text.strip()
