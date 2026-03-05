"""Page analysis prompt template (v1).

Used by the Search Agent to classify page type, identify data regions,
detect pagination patterns, and recommend navigation mode.
"""

from __future__ import annotations


def build_system_prompt() -> str:
    return """You are an expert web analyst specializing in data extraction.
You analyze web pages to determine their structure, data regions, and the best
approach for automated data extraction.

You MUST respond with valid JSON only — no markdown, no explanation."""


def build_user_message(
    *,
    url: str,
    user_description: str,
    accessibility_tree: str,
    page_structure: str,
    api_candidates: list[dict[str, str]] | None = None,
) -> str:
    parts = [
        f"URL: {url}",
        f"User wants: {user_description}",
        "",
        "=== Accessibility Tree ===",
        accessibility_tree[:8000],
        "",
        "=== Page Structure ===",
        page_structure[:4000],
    ]

    if api_candidates:
        parts.append("")
        parts.append("=== API Candidates (XHR/fetch traffic) ===")
        for c in api_candidates[:10]:
            parts.append(f"  {c.get('method', 'GET')} {c.get('url', '')}")
            if c.get("response_content_type"):
                parts.append(f"    Content-Type: {c['response_content_type']}")

    parts.extend([
        "",
        "Analyze this page and respond with JSON:",
        "{",
        '  "page_type": "static_html" | "spa_with_api" | "direct_api" | "pdf" | "csv",',
        '  "data_regions": [{"selector": "...", "description": "..."}],',
        '  "has_pagination": true/false,',
        '  "pagination": {"type": "next_button"|"url_param"|"infinite_scroll"|"page_numbers", "selector": "..."|null, "param": "..."|null} | null,',
        '  "recommended_nav_mode": "SINGLE_PAGE" | "PAGINATED_LIST" | "API_DISCOVERY",',
        '  "api_endpoint": "..." | null,',
        '  "confidence": 0.0-1.0',
        "}",
    ])

    return "\n".join(parts)
