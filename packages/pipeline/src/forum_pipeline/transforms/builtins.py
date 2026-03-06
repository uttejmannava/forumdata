"""Built-in transform functions for common trading data operations."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from forum_pipeline.transforms.registry import register

# Type mapping from schema column types to Python coercion
_TYPE_COERCIONS: dict[str, type] = {
    "STRING": str,
    "INTEGER": int,
    "FLOAT": float,
    "BOOLEAN": bool,
}


@register("cast_types")
def cast_types(
    rows: list[dict[str, Any]], schema: dict[str, Any], **_: Any
) -> list[dict[str, Any]]:
    """Coerce values to types defined in schema columns."""
    columns = {col["name"]: col for col in schema.get("columns", [])}
    result = []
    for row in rows:
        cast_row = dict(row)
        for col_name, col_def in columns.items():
            if col_name in cast_row and cast_row[col_name] is not None:
                cast_row[col_name] = _coerce(cast_row[col_name], col_def["type"])
        result.append(cast_row)
    return result


@register("strip_currency")
def strip_currency(
    rows: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
) -> list[dict[str, Any]]:
    """Remove currency symbols and thousand separators from numeric fields."""
    fields = kwargs.get("fields", [])
    if not fields:
        # Auto-detect: apply to FLOAT and INTEGER columns
        fields = [
            col["name"]
            for col in schema.get("columns", [])
            if col["type"] in ("FLOAT", "INTEGER")
        ]

    currency_pattern = re.compile(r"[$\u00a3\u20ac\u00a5,]")  # $, GBP, EUR, JPY
    result = []
    for row in rows:
        new_row = dict(row)
        for field in fields:
            if field in new_row and isinstance(new_row[field], str):
                new_row[field] = currency_pattern.sub("", new_row[field]).strip()
        result.append(new_row)
    return result


@register("normalize_dates")
def normalize_dates(
    rows: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
) -> list[dict[str, Any]]:
    """Parse various date formats into ISO 8601 (YYYY-MM-DD)."""
    fields = kwargs.get("fields", [])
    if not fields:
        fields = [
            col["name"]
            for col in schema.get("columns", [])
            if col["type"] in ("DATE", "DATETIME")
        ]

    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
        "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
        "%m-%d-%Y", "%d-%m-%Y",
    ]

    result = []
    for row in rows:
        new_row = dict(row)
        for field in fields:
            val = new_row.get(field)
            if isinstance(val, str) and val.strip():
                new_row[field] = _parse_date(val.strip(), formats)
        result.append(new_row)
    return result


@register("deduplicate")
def deduplicate(
    rows: list[dict[str, Any]], schema: dict[str, Any], **kwargs: Any
) -> list[dict[str, Any]]:
    """Remove exact duplicate rows. Uses primary_key if available."""
    key_fields = kwargs.get("fields", schema.get("primary_key", []))
    if not key_fields:
        # Full row dedup
        seen: set[str] = set()
        result = []
        for row in rows:
            row_key = str(sorted(row.items()))
            if row_key not in seen:
                seen.add(row_key)
                result.append(row)
        return result

    seen_keys: set[tuple[Any, ...]] = set()
    result = []
    for row in rows:
        key = tuple(row.get(k) for k in key_fields)
        if key not in seen_keys:
            seen_keys.add(key)
            result.append(row)
    return result


def _coerce(value: Any, target_type: str) -> Any:
    """Coerce a value to the target schema type. Returns original on failure."""
    coercion = _TYPE_COERCIONS.get(target_type)
    if coercion is None:
        return value
    try:
        if coercion is float and isinstance(value, str):
            # Handle comma-separated numbers
            return float(value.replace(",", ""))
        if coercion is int and isinstance(value, str):
            return int(float(value.replace(",", "")))
        if coercion is bool and isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return coercion(value)
    except (ValueError, TypeError):
        return value


def _parse_date(value: str, formats: list[str]) -> str:
    """Try multiple date formats, return ISO 8601 on success or original on failure."""
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value
