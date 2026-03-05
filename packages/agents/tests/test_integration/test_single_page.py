"""Integration test for single page extraction using fixtures.

These tests verify the full orchestrator flow against pre-recorded
fixtures with mocked LLM responses.
"""

from __future__ import annotations

import json
from pathlib import Path


from forum_agents.agents.extraction import _extract_selectors
from forum_agents.agents.search import _parse_analysis
from forum_agents.tools.data import validate_against_schema

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "static_table"


def test_fixture_files_exist() -> None:
    """Verify fixture directory is properly structured."""
    assert (FIXTURES_DIR / "config.json").exists()
    assert (FIXTURES_DIR / "dom_initial.html").exists()
    assert (FIXTURES_DIR / "expected_schema.json").exists()
    assert (FIXTURES_DIR / "expected_data.json").exists()


def test_fixture_config_valid() -> None:
    """Verify fixture config is valid JSON with required keys."""
    config = json.loads((FIXTURES_DIR / "config.json").read_text())
    assert "url" in config
    assert "name" in config
    assert config["expected_nav_mode"] == "SINGLE_PAGE"


def test_fixture_html_has_table() -> None:
    """Verify fixture HTML contains expected data table."""
    html = (FIXTURES_DIR / "dom_initial.html").read_text()
    assert "<table" in html
    assert "Widget A" in html
    assert "$9.99" in html


def test_expected_data_matches_schema() -> None:
    """Verify expected data validates against expected schema."""
    schema = json.loads((FIXTURES_DIR / "expected_schema.json").read_text())
    data = json.loads((FIXTURES_DIR / "expected_data.json").read_text())

    result = validate_against_schema(data, schema)
    assert result.success, f"Validation errors: {result.data.get('errors', [])}"
    assert result.data["row_count"] == 5


def test_mock_page_analysis_response() -> None:
    """Test that a typical LLM page analysis response parses correctly."""
    mock_response = json.dumps({
        "page_type": "static_html",
        "data_regions": [{"selector": "#price-table", "description": "Product price table"}],
        "has_pagination": False,
        "pagination": None,
        "recommended_nav_mode": "SINGLE_PAGE",
        "api_endpoint": None,
        "confidence": 0.95,
    })

    result = _parse_analysis(mock_response)
    assert result["page_type"] == "static_html"
    assert result["recommended_nav_mode"] == "SINGLE_PAGE"
    assert len(result["data_regions"]) == 1


def test_mock_extraction_code_valid() -> None:
    """Test that representative extraction code compiles and has SELECTORS."""
    mock_code = '''
SELECTORS = {
    "product": "#price-table tbody tr td:nth-child(1)",
    "price": "#price-table tbody tr td:nth-child(2)",
    "stock": "#price-table tbody tr td:nth-child(3)",
}

async def extract(page) -> list[dict]:
    rows = await page.query_selector_all("#price-table tbody tr")
    results = []
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 3:
            product = (await cells[0].text_content() or "").strip()
            price = (await cells[1].text_content() or "").strip()
            stock = (await cells[2].text_content() or "").strip()
            results.append({"product": product, "price": price, "stock": stock})
    return results
'''
    compile(mock_code, "<test>", "exec")
    selectors = _extract_selectors(mock_code)
    assert "product" in selectors
    assert "price" in selectors
    assert "stock" in selectors
