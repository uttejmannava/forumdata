"""Integration test for paginated list extraction."""

from __future__ import annotations

import json
from pathlib import Path

from forum_agents.agents.extraction import _extract_selectors
from forum_agents.agents.navigation import _clean_code
from forum_agents.agents.search import _parse_analysis
from forum_agents.tools.data import validate_against_schema

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "paginated_list"


def test_paginated_nav_code_template() -> None:
    """Verify a typical paginated navigation code template compiles."""
    mock_code = '''
async def navigate(page, config: dict) -> list[str]:
    """Navigate through paginated results."""
    url = config["url"]
    max_pages = config.get("max_pages", 5)
    pages = []

    await page.goto(url, wait_until="networkidle", timeout=30000)
    pages.append(await page.content())

    for _ in range(max_pages - 1):
        next_btn = await page.query_selector("a.next-page")
        if not next_btn:
            break
        await next_btn.click()
        await page.wait_for_load_state("networkidle")
        pages.append(await page.content())

    return pages
'''
    cleaned = _clean_code(mock_code)
    compile(cleaned, "<test>", "exec")


def test_paginated_fixture_files_exist() -> None:
    assert (FIXTURES_DIR / "config.json").exists()
    assert (FIXTURES_DIR / "dom_initial.html").exists()
    assert (FIXTURES_DIR / "expected_schema.json").exists()
    assert (FIXTURES_DIR / "expected_data.json").exists()


def test_paginated_fixture_config() -> None:
    config = json.loads((FIXTURES_DIR / "config.json").read_text())
    assert config["expected_nav_mode"] == "PAGINATED_LIST"
    assert "page=" in config["url"]


def test_paginated_html_has_pagination() -> None:
    html = (FIXTURES_DIR / "dom_initial.html").read_text()
    assert "<table" in html
    assert "next-page" in html or "pagination" in html
    assert "Page 1" in html


def test_paginated_data_matches_schema() -> None:
    schema = json.loads((FIXTURES_DIR / "expected_schema.json").read_text())
    data = json.loads((FIXTURES_DIR / "expected_data.json").read_text())

    result = validate_against_schema(data, schema)
    assert result.success, f"Validation errors: {result.data.get('errors', [])}"
    assert result.data["row_count"] == 10


def test_paginated_analysis_response() -> None:
    mock_response = json.dumps({
        "page_type": "static_html",
        "data_regions": [{"selector": "#product-list", "description": "Product listing table"}],
        "has_pagination": True,
        "pagination": {"type": "next_button", "selector": "a.next-page"},
        "recommended_nav_mode": "PAGINATED_LIST",
        "api_endpoint": None,
        "confidence": 0.90,
    })

    result = _parse_analysis(mock_response)
    assert result["page_type"] == "static_html"
    assert result["recommended_nav_mode"] == "PAGINATED_LIST"
    assert result["has_pagination"] is True


def test_paginated_extraction_code_valid() -> None:
    mock_code = '''
SELECTORS = {
    "name": "#product-list tbody tr td:nth-child(1)",
    "category": "#product-list tbody tr td:nth-child(2)",
    "price": "#product-list tbody tr td:nth-child(3)",
    "rating": "#product-list tbody tr td:nth-child(4)",
}

async def extract(page) -> list[dict]:
    rows = await page.query_selector_all("#product-list tbody tr")
    results = []
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 4:
            results.append({
                "name": (await cells[0].text_content() or "").strip(),
                "category": (await cells[1].text_content() or "").strip(),
                "price": (await cells[2].text_content() or "").strip(),
                "rating": (await cells[3].text_content() or "").strip(),
            })
    return results
'''
    compile(mock_code, "<test>", "exec")
    selectors = _extract_selectors(mock_code)
    assert "name" in selectors
    assert "category" in selectors
    assert "price" in selectors
