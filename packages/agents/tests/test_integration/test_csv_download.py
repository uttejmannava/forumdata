"""Integration test for CSV download page extraction using fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from forum_agents.agents.extraction import _extract_selectors
from forum_agents.agents.search import _parse_analysis
from forum_agents.tools.data import validate_against_schema

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "csv_download"


def test_csv_fixture_files_exist() -> None:
    assert (FIXTURES_DIR / "config.json").exists()
    assert (FIXTURES_DIR / "dom_initial.html").exists()
    assert (FIXTURES_DIR / "expected_schema.json").exists()
    assert (FIXTURES_DIR / "expected_data.json").exists()


def test_csv_fixture_config() -> None:
    config = json.loads((FIXTURES_DIR / "config.json").read_text())
    assert config["expected_nav_mode"] == "SINGLE_PAGE"
    assert "economic" in config["description"].lower()


def test_csv_html_has_download_links() -> None:
    html = (FIXTURES_DIR / "dom_initial.html").read_text()
    assert "download-link" in html
    assert ".csv" in html
    assert "indicator-preview" in html


def test_csv_html_has_preview_table() -> None:
    html = (FIXTURES_DIR / "dom_initial.html").read_text()
    assert "GDP Growth Rate" in html
    assert "Unemployment Rate" in html
    assert "CPI" in html


def test_csv_data_matches_schema() -> None:
    schema = json.loads((FIXTURES_DIR / "expected_schema.json").read_text())
    data = json.loads((FIXTURES_DIR / "expected_data.json").read_text())

    result = validate_against_schema(data, schema)
    assert result.success, f"Validation errors: {result.data.get('errors', [])}"
    assert result.data["row_count"] == 6


def test_csv_analysis_response() -> None:
    mock_response = json.dumps({
        "page_type": "static_html",
        "data_regions": [
            {"selector": "#indicator-preview", "description": "Economic indicators preview"},
            {"selector": ".download-section", "description": "CSV/Excel download links"},
        ],
        "has_pagination": False,
        "pagination": None,
        "recommended_nav_mode": "SINGLE_PAGE",
        "api_endpoint": None,
        "confidence": 0.92,
    })

    result = _parse_analysis(mock_response)
    assert result["page_type"] == "static_html"
    assert len(result["data_regions"]) == 2


def test_csv_extraction_code_valid() -> None:
    mock_code = '''
SELECTORS = {
    "indicator": "#indicator-preview tbody tr td:nth-child(1)",
    "period": "#indicator-preview tbody tr td:nth-child(2)",
    "value": "#indicator-preview tbody tr td:nth-child(3)",
    "unit": "#indicator-preview tbody tr td:nth-child(4)",
    "change_pct": "#indicator-preview tbody tr td:nth-child(5)",
}

async def extract(page) -> list[dict]:
    rows = await page.query_selector_all("#indicator-preview tbody tr")
    results = []
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 5:
            results.append({
                "indicator": (await cells[0].text_content() or "").strip(),
                "period": (await cells[1].text_content() or "").strip(),
                "value": float((await cells[2].text_content() or "0").strip()),
                "unit": (await cells[3].text_content() or "").strip(),
                "change_pct": (await cells[4].text_content() or "").strip(),
            })
    return results
'''
    compile(mock_code, "<test>", "exec")
    selectors = _extract_selectors(mock_code)
    assert "indicator" in selectors
    assert "value" in selectors
    assert "change_pct" in selectors
