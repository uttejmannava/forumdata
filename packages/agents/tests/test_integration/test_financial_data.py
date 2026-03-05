"""Integration test for financial data extraction using fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from forum_agents.agents.extraction import _extract_selectors
from forum_agents.agents.search import _parse_analysis
from forum_agents.tools.data import validate_against_schema

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "financial_data"


def test_financial_fixture_files_exist() -> None:
    assert (FIXTURES_DIR / "config.json").exists()
    assert (FIXTURES_DIR / "dom_initial.html").exists()
    assert (FIXTURES_DIR / "expected_schema.json").exists()
    assert (FIXTURES_DIR / "expected_data.json").exists()


def test_financial_fixture_config() -> None:
    config = json.loads((FIXTURES_DIR / "config.json").read_text())
    assert config["expected_nav_mode"] == "SINGLE_PAGE"
    assert "settlement" in config["url"]


def test_financial_html_has_settlement_table() -> None:
    html = (FIXTURES_DIR / "dom_initial.html").read_text()
    assert "settlement-table" in html
    assert "Settlement Price" in html
    assert "CL" in html
    assert "72.45" in html


def test_financial_data_matches_schema() -> None:
    schema = json.loads((FIXTURES_DIR / "expected_schema.json").read_text())
    data = json.loads((FIXTURES_DIR / "expected_data.json").read_text())

    result = validate_against_schema(data, schema)
    assert result.success, f"Validation errors: {result.data.get('errors', [])}"
    assert result.data["row_count"] == 8


def test_financial_data_has_multiple_contracts() -> None:
    data = json.loads((FIXTURES_DIR / "expected_data.json").read_text())
    contracts = {row["contract"] for row in data}
    assert contracts == {"CL", "NG", "GC", "SI"}


def test_financial_analysis_response() -> None:
    mock_response = json.dumps({
        "page_type": "static_html",
        "data_regions": [{"selector": "#settlement-table", "description": "Settlement prices"}],
        "has_pagination": False,
        "pagination": None,
        "recommended_nav_mode": "SINGLE_PAGE",
        "api_endpoint": None,
        "confidence": 0.95,
    })

    result = _parse_analysis(mock_response)
    assert result["page_type"] == "static_html"
    assert result["recommended_nav_mode"] == "SINGLE_PAGE"


def test_financial_extraction_code_valid() -> None:
    mock_code = '''
SELECTORS = {
    "contract": "#settlement-table tbody tr td:nth-child(1)",
    "month": "#settlement-table tbody tr td:nth-child(2)",
    "settlement_price": "#settlement-table tbody tr td:nth-child(3)",
    "change": "#settlement-table tbody tr td:nth-child(4)",
    "volume": "#settlement-table tbody tr td:nth-child(5)",
    "open_interest": "#settlement-table tbody tr td:nth-child(6)",
}

async def extract(page) -> list[dict]:
    rows = await page.query_selector_all("#settlement-table tbody tr")
    results = []
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 6:
            results.append({
                "contract": (await cells[0].text_content() or "").strip(),
                "month": (await cells[1].text_content() or "").strip(),
                "settlement_price": float((await cells[2].text_content() or "0").strip()),
                "change": (await cells[3].text_content() or "").strip(),
                "volume": int((await cells[4].text_content() or "0").strip()),
                "open_interest": int((await cells[5].text_content() or "0").strip()),
            })
    return results
'''
    compile(mock_code, "<test>", "exec")
    selectors = _extract_selectors(mock_code)
    assert "contract" in selectors
    assert "settlement_price" in selectors
