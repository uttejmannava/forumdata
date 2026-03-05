"""Extract stage — load and execute agent-generated extraction code."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from playwright.async_api import Page

from forum_pipeline.context import RunContext


def load_extract_module(code_dir: Path) -> ModuleType:
    """Dynamically import extract.py from the code directory."""
    extract_path = code_dir / "extract.py"
    if not extract_path.exists():
        raise FileNotFoundError(f"No extract.py found in {code_dir}")

    spec = importlib.util.spec_from_file_location("extract", extract_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {extract_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["extract"] = module
    spec.loader.exec_module(module)
    return module


def load_navigate_module(code_dir: Path) -> ModuleType | None:
    """Dynamically import navigate.py if it exists."""
    navigate_path = code_dir / "navigate.py"
    if not navigate_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("navigate", navigate_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules["navigate"] = module
    spec.loader.exec_module(module)
    return module


async def run_extract(page: Page, ctx: RunContext) -> list[dict[str, Any]]:
    """Execute extraction code against a page."""
    extract_mod = load_extract_module(ctx.code_dir)

    extract_fn = getattr(extract_mod, "extract", None)
    if extract_fn is None:
        raise AttributeError("extract.py must define an `extract(page)` function")

    result = await extract_fn(page)
    if not isinstance(result, list):
        raise TypeError(f"extract() must return a list, got {type(result)}")

    return [dict(row) for row in result]


async def run_navigate(page: Page, ctx: RunContext, url: str) -> list[str]:
    """Execute navigation code if present, otherwise just goto URL."""
    nav_mod = load_navigate_module(ctx.code_dir)

    if nav_mod is not None:
        navigate_fn = getattr(nav_mod, "navigate", None)
        if navigate_fn is not None:
            config = {"url": url, "max_pages": 5}
            result = await navigate_fn(page, config)
            if isinstance(result, list):
                return [str(h) for h in result]

    # Fallback: simple navigation
    await page.goto(url, wait_until="networkidle", timeout=30000)
    html = await page.content()
    return [html]


def validate_output(
    data: list[dict[str, Any]], schema_path: Path
) -> tuple[bool, list[str]]:
    """Validate extracted data against schema.json."""
    if not schema_path.exists():
        return True, []  # No schema to validate against

    schema = json.loads(schema_path.read_text())
    columns = {col["name"]: col for col in schema.get("columns", [])}
    errors: list[str] = []

    for i, row in enumerate(data[:100]):
        for col_name, col_def in columns.items():
            if row.get(col_name) is None and not col_def.get("nullable", True):
                errors.append(f"Row {i}: missing required field '{col_name}'")

    return len(errors) == 0, errors
