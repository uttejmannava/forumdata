"""Extract stage — load and execute agent-generated extraction code.

Integrates:
- ForumBrowser with configured stealth level
- ResolutionCascade for self-healing selector resolution (Tiers 1-3)
- SignalMonitor for detection event tracking
- Tracing on failure for debugging
- Source grounding metadata per extracted field
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

from playwright.async_api import Page

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.resolution.cascade import (
    ResolutionCascade,
    ResolutionTier,
)
from forum_browser.resolution.storage import SqliteFingerprintStorage
from forum_browser.stealth.signals import SignalMonitor
from forum_schemas.models.errors import ErrorCode
from forum_schemas.models.pipeline import StealthLevel

from forum_pipeline.config import get_stealth_level
from forum_pipeline.context import RunContext
from forum_pipeline.errors import StageError
from forum_pipeline.stage_data import StageData


def _load_module(code_dir: Path, name: str) -> ModuleType | None:
    """Dynamically import a Python file from the code directory."""
    file_path = code_dir / f"{name}.py"
    if not file_path.exists():
        return None

    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def run_extract(data: StageData, ctx: RunContext) -> StageData:
    """Execute the Extract stage.

    1. Launch browser with configured stealth level
    2. Run navigate.py to collect HTML snapshots
    3. Run extract.py against each snapshot to produce rows
    4. Record source grounding metadata per field
    5. Monitor for detection signals
    6. Capture trace on failure
    """
    assert ctx.code_dir is not None

    # Load agent-generated modules
    extract_mod = _load_module(ctx.code_dir, "extract")
    if extract_mod is None:
        raise StageError(ErrorCode.EXTRACTION_FAILED, "No extract.py found in code directory")

    extract_fn = getattr(extract_mod, "extract", None)
    if extract_fn is None:
        raise StageError(ErrorCode.EXTRACTION_FAILED, "extract.py must define an `extract(page)` function")

    selectors: dict[str, str] = getattr(extract_mod, "SELECTORS", {})
    nav_mod = _load_module(ctx.code_dir, "navigate")

    # Configure browser
    stealth = get_stealth_level(data.config)
    browser_stealth = stealth if stealth != StealthLevel.NONE else StealthLevel.BASIC
    browser_config = BrowserConfig(
        stealth_level=browser_stealth,
        trace_enabled=True,
        trace_dir=str(ctx.output_dir / "traces") if ctx.output_dir else "traces",
    )

    # Resolution cascade is initialized lazily when Tier 2+ resolution is needed.
    # Currently all extraction uses Tier 1 (direct selectors); cascade integration
    # will be wired in when fingerprint storage is populated during agent setup.
    _cascade_storage = None
    _cascade = None

    def _get_cascade() -> ResolutionCascade:
        nonlocal _cascade_storage, _cascade
        if _cascade is None:
            _cascade_storage = SqliteFingerprintStorage()
            _cascade = ResolutionCascade(
                _cascade_storage,
                tenant_id=ctx.tenant_id,
                pipeline_id=ctx.pipeline_id,
            )
        return _cascade

    signal_monitor = SignalMonitor()
    url = data.config.get("source_url", "")
    start = time.monotonic()

    try:
        async with ForumBrowser(browser_config) as browser:
            page = await browser.new_page()

            # Navigate
            html_pages = await _run_navigate(page, nav_mod, url)

            # Extract from each page
            all_rows: list[dict[str, Any]] = []
            grounding: list[dict[str, Any]] = []

            for page_idx, html in enumerate(html_pages):
                await page.set_content(html)

                # Check for detection signals on page content
                detection = await signal_monitor.check_page_content(page)
                if detection is not None:
                    ctx.add_warning(
                        "DETECTION_SIGNAL",
                        f"Detection signal on page {page_idx}: {detection.signal.value}",
                        signal=detection.signal.value,
                        page_index=page_idx,
                    )

                # Run extraction
                rows = await extract_fn(page)
                if not isinstance(rows, list):
                    raise StageError(
                        ErrorCode.EXTRACTION_FAILED,
                        f"extract() must return a list, got {type(rows).__name__}",
                    )

                # Record source grounding for each field
                for row in rows:
                    row_dict = dict(row)
                    all_rows.append(row_dict)
                    for field_name in row_dict:
                        selector = selectors.get(field_name, "")
                        grounding.append({
                            "field": field_name,
                            "url": url,
                            "selector": selector,
                            "tier": ResolutionTier.DIRECT_SELECTOR.value,
                            "confidence": 0.95 if selector else 0.7,
                            "page_index": page_idx,
                        })

            data.rows = all_rows
            data.grounding = grounding
            data.stage_metadata["extract"] = {
                "duration_seconds": time.monotonic() - start,
                "pages_processed": len(html_pages),
                "rows_extracted": len(all_rows),
                "detection_events": [
                    {"signal": e.signal.value, "url": e.url}
                    for e in signal_monitor.events
                ],
            }

    except StageError:
        raise
    except Exception as e:
        raise StageError(
            ErrorCode.EXTRACTION_FAILED,
            f"Extraction failed: {e}",
        ) from e

    if not data.rows:
        ctx.add_warning("EMPTY_RESULTS", "Extraction returned 0 rows")

    return data


async def _run_navigate(
    page: Page, nav_mod: ModuleType | None, url: str
) -> list[str]:
    """Execute navigation code if present, otherwise just goto URL."""
    if nav_mod is not None:
        navigate_fn = getattr(nav_mod, "navigate", None)
        if navigate_fn is not None:
            config = {"url": url, "max_pages": 10}
            result = await navigate_fn(page, config)
            if isinstance(result, list):
                return [str(h) for h in result]

    # Fallback: single page navigation
    await page.goto(url, wait_until="networkidle", timeout=30000)
    html = await page.content()
    return [html]
