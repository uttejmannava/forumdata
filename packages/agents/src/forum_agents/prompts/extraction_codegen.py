"""Extraction code generation prompt template (v1).

Used by the Extraction Agent to generate Playwright Python code
that extracts structured data from a page using CSS selectors.
"""

from __future__ import annotations

from typing import Any


def build_system_prompt() -> str:
    return """You are an expert web data extraction engineer.
You generate clean, production-quality Python async functions that extract structured
data from web pages using CSS selectors.

Rules:
- Use Playwright's async API (page.query_selector_all, el.text_content, el.get_attribute)
- Define a SELECTORS dict mapping field names to CSS selectors
- Return a list of dicts, one per row of data
- Handle missing/null values gracefully
- Strip whitespace from extracted text
- Do NOT import anything — the function receives a configured `page` object

You MUST respond with ONLY the Python code — no markdown fences, no explanation.
The code must include both the SELECTORS dict and the extract function."""


def build_user_message(
    *,
    user_description: str,
    sample_html: str,
    schema: dict[str, Any],
    data_regions: list[dict[str, str]] | None = None,
) -> str:
    parts = [
        f"User wants: {user_description}",
        "",
        "=== Target Schema ===",
    ]

    for col in schema.get("columns", []):
        nullable = "nullable" if col.get("nullable", True) else "required"
        parts.append(f"  {col['name']}: {col['type']} ({nullable}) — {col.get('description', '')}")

    if data_regions:
        parts.append("")
        parts.append("=== Data Regions ===")
        for r in data_regions:
            parts.append(f"  Selector: {r.get('selector', '?')} — {r.get('description', '')}")

    parts.extend([
        "",
        "=== Sample HTML ===",
        sample_html[:12000],
        "",
        "Generate Python code with:",
        "",
        "SELECTORS = {",
        '    "field_name": "css_selector",',
        "    ...",
        "}",
        "",
        "async def extract(page) -> list[dict]:",
        '    """Extract data from page. Selectors defined in SELECTORS map."""',
        "    ...",
        "",
        "The function should extract all rows matching the schema.",
        "Return a list of dicts with keys matching the schema column names.",
    ])

    return "\n".join(parts)
