"""Cleanse stage — deterministic noise removal from raw extracted data.

Runs between Extract and Transform. Strips:
- HTML boilerplate and tags that leaked into values
- Leading/trailing whitespace, multiple spaces, non-breaking spaces, zero-width chars
- Encoding artifacts (HTML entities, Unicode control characters)
- Duplicate rows (exact match dedup using dedup_key from schema)
- Footnote markers (*, dagger, double-dagger) extracted into qualifier metadata
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData

# Footnote marker patterns and their common meanings
_FOOTNOTE_MARKERS = {
    "*": "preliminary",
    "**": "estimated",
    "\u2020": "revised",        # dagger
    "\u2021": "corrected",      # double-dagger
    "\u00a7": "see_note",       # section sign
}

_FOOTNOTE_PATTERN = re.compile(
    r"([*\u2020\u2021\u00a7]{1,2})\s*$"
)

# HTML tag stripping
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# Whitespace normalization
_MULTI_SPACE = re.compile(r"\s+")
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")


async def run_cleanse(data: StageData, ctx: RunContext) -> StageData:
    """Execute the Cleanse stage."""
    if not data.rows:
        return data

    # Load qualifier mapping from config (agent-generated during setup)
    qualifier_map = data.config.get("footnote_qualifiers", _FOOTNOTE_MARKERS)

    cleaned_rows: list[dict[str, Any]] = []
    qualifiers_extracted: int = 0

    for row in data.rows:
        cleaned_row: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, str):
                cleaned_value, quals = _cleanse_string(value, qualifier_map)
                cleaned_row[key] = cleaned_value
                if quals:
                    cleaned_row.setdefault("_qualifiers", {})
                    cleaned_row["_qualifiers"][key] = quals
                    qualifiers_extracted += len(quals)
            else:
                cleaned_row[key] = value
        cleaned_rows.append(cleaned_row)

    # Dedup using schema's dedup_key if available
    dedup_key = data.schema.get("dedup_key", [])
    rows_before = len(cleaned_rows)
    if dedup_key:
        cleaned_rows = _dedup_rows(cleaned_rows, dedup_key)

    rows_removed = rows_before - len(cleaned_rows)
    data.rows = cleaned_rows
    data.stage_metadata["cleanse"] = {
        "rows_before": rows_before,
        "rows_after": len(cleaned_rows),
        "rows_deduped": rows_removed,
        "qualifiers_extracted": qualifiers_extracted,
    }

    return data


def _cleanse_string(
    value: str, qualifier_map: dict[str, str]
) -> tuple[str, list[str]]:
    """Clean a single string value and extract footnote qualifiers."""
    qualifiers: list[str] = []

    # Extract footnote markers before cleaning
    match = _FOOTNOTE_PATTERN.search(value)
    if match:
        marker = match.group(1)
        qualifier = qualifier_map.get(marker)
        if qualifier:
            qualifiers.append(qualifier)
        value = value[: match.start()]

    # Strip HTML tags
    value = _HTML_TAG_PATTERN.sub("", value)

    # Decode HTML entities
    value = html.unescape(value)

    # Remove zero-width characters
    value = _ZERO_WIDTH.sub("", value)

    # Remove Unicode control characters (except newlines and tabs)
    value = "".join(
        c for c in value
        if not unicodedata.category(c).startswith("C") or c in "\n\t"
    )

    # Normalize whitespace
    value = _MULTI_SPACE.sub(" ", value).strip()

    # Replace non-breaking spaces with regular spaces
    value = value.replace("\u00a0", " ")

    return value, qualifiers


def _dedup_rows(
    rows: list[dict[str, Any]], dedup_key: list[str]
) -> list[dict[str, Any]]:
    """Remove duplicate rows based on dedup_key columns. Keeps first occurrence."""
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(row.get(k) for k in dedup_key)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result
