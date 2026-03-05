"""Navigation code generation prompt template (v1).

Used by the Navigation Agent to generate Playwright Python code
for navigating to and through pages of data.
"""

from __future__ import annotations

from typing import Any


def build_system_prompt() -> str:
    return """You are an expert Playwright automation engineer.
You generate clean, production-quality Python async functions that navigate web pages.

Rules:
- Use Playwright's async API (page.goto, page.click, page.wait_for_selector, etc.)
- Always include proper waits (wait_for_selector, wait_for_load_state)
- Handle cookie consent banners if present
- Return a list of HTML snapshots (one per page visited)
- Use try/except for error handling
- Do NOT import anything — the function receives a configured `page` object

You MUST respond with ONLY the Python function code — no markdown fences, no explanation."""


def build_user_message(
    *,
    url: str,
    pagination: dict[str, Any] | None = None,
    page_structure: str,
    max_pages: int = 5,
) -> str:
    parts = [
        f"URL: {url}",
        f"Max pages to visit: {max_pages}",
        "",
        "=== Page Structure ===",
        page_structure[:4000],
    ]

    if pagination:
        parts.extend([
            "",
            "=== Pagination Pattern ===",
            f"Type: {pagination.get('type', 'unknown')}",
            f"Selector: {pagination.get('selector', 'N/A')}",
            f"URL param: {pagination.get('param', 'N/A')}",
        ])
    else:
        parts.extend([
            "",
            "No pagination detected — single page navigation only.",
        ])

    parts.extend([
        "",
        "Generate an async Python function with this signature:",
        "",
        "async def navigate(page, config: dict) -> list[str]:",
        '    """Navigate to data pages and return HTML snapshots."""',
        "    ...",
        "",
        "The `config` dict has keys: 'url' (str), 'max_pages' (int).",
        "Return a list of HTML strings (page.content() for each page).",
    ])

    return "\n".join(parts)
