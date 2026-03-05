"""Data parsing and validation tools."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from forum_agents.tools.browser import ToolResult


def parse_json(text: str) -> ToolResult:
    """Parse a JSON string into structured data."""
    try:
        data = json.loads(text)
        return ToolResult(success=True, data={"parsed": data})
    except json.JSONDecodeError as e:
        return ToolResult(success=False, data={}, error=f"Invalid JSON: {e}")


def parse_csv(text: str) -> ToolResult:
    """Parse CSV text into a list of dicts."""
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return ToolResult(
            success=True,
            data={"rows": rows, "row_count": len(rows), "columns": reader.fieldnames or []},
        )
    except Exception as e:
        return ToolResult(success=False, data={}, error=f"CSV parse error: {e}")


def validate_against_schema(data: list[dict[str, Any]], schema: dict[str, Any]) -> ToolResult:
    """Validate extracted data against an ExtractionSchema-compatible dict."""
    columns = {col["name"]: col for col in schema.get("columns", [])}
    errors: list[str] = []

    for i, row in enumerate(data[:100]):  # Validate first 100 rows
        for col_name, col_def in columns.items():
            value = row.get(col_name)
            if value is None and not col_def.get("nullable", True):
                errors.append(f"Row {i}: missing required field '{col_name}'")

    return ToolResult(
        success=len(errors) == 0,
        data={"row_count": len(data), "errors": errors[:20], "error_count": len(errors)},
    )


_PII_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone_us": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}


def detect_pii(text: str) -> ToolResult:
    """Detect common PII patterns in text."""
    findings: list[dict[str, Any]] = []
    for pii_type, pattern in _PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            findings.append({"type": pii_type, "count": len(matches), "sample": matches[0]})

    return ToolResult(
        success=True,
        data={"has_pii": len(findings) > 0, "findings": findings},
    )


def extract_table_data(html: str) -> ToolResult:
    """Parse HTML table to list of dicts using basic regex parsing.

    For production use, prefer the DOM-based get_tables tool which runs in-browser.
    This is a fallback for processing raw HTML strings.
    """
    # Extract headers
    header_match = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
    if header_match:
        headers = re.findall(r"<th[^>]*>(.*?)</th>", header_match.group(1), re.DOTALL)
    else:
        first_row = re.search(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        if first_row:
            headers = re.findall(r"<th[^>]*>(.*?)</th>", first_row.group(1), re.DOTALL)
        else:
            headers = []

    # Clean headers
    headers = [re.sub(r"<[^>]+>", "", h).strip() for h in headers]

    # Extract rows
    rows_html = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    rows: list[dict[str, str]] = []
    for row_html in rows_html:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if cells and headers:
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            row_dict = dict(zip(headers, cells))
            rows.append(row_dict)

    return ToolResult(
        success=len(rows) > 0,
        data={"rows": rows, "row_count": len(rows), "headers": headers},
    )
