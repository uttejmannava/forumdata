"""Schema inference prompt template (v1).

Used by the Extraction Agent to propose or validate an extraction schema
from sample HTML content and user description.
"""

from __future__ import annotations

from typing import Any


def build_system_prompt() -> str:
    return """You are a data schema designer specializing in financial and trading data extraction.
Given sample HTML content and a user description, you infer the optimal extraction schema.

You MUST respond with valid JSON only — no markdown, no explanation.

Column types: STRING, INTEGER, FLOAT, BOOLEAN, DATETIME, DATE, JSON
Always include a primary_key that uniquely identifies each row."""


def build_user_message(
    *,
    user_description: str,
    sample_html: str,
    tables_data: list[dict[str, Any]] | None = None,
    existing_schema: dict[str, Any] | None = None,
) -> str:
    parts = [
        f"User wants: {user_description}",
        "",
        "=== Sample HTML ===",
        sample_html[:12000],
    ]

    if tables_data:
        parts.append("")
        parts.append("=== Detected Tables ===")
        for t in tables_data[:5]:
            parts.append(f"Table {t.get('index', '?')}: headers={t.get('headers', [])}")
            for row in t.get("sample_rows", [])[:3]:
                parts.append(f"  {row}")

    if existing_schema:
        parts.append("")
        parts.append("=== Existing Schema (validate/refine) ===")
        for col in existing_schema.get("columns", []):
            parts.append(f"  {col['name']}: {col['type']} {'(nullable)' if col.get('nullable') else '(required)'}")

    parts.extend([
        "",
        "Respond with a schema definition JSON:",
        "{",
        '  "columns": [',
        '    {"name": "...", "type": "STRING|INTEGER|FLOAT|BOOLEAN|DATETIME|DATE|JSON",',
        '     "description": "...", "nullable": true/false, "example": "..."}',
        "  ],",
        '  "primary_key": ["column_name"],',
        '  "dedup_key": ["column_name"],',
        '  "confidence": 0.0-1.0',
        "}",
    ])

    return "\n".join(parts)
