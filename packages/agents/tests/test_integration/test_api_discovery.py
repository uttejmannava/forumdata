"""Integration test for API discovery extraction."""

from __future__ import annotations

import json
from pathlib import Path

from forum_agents.agents.search import _parse_analysis
from forum_agents.nav_modes.api_discovery import _pick_best_candidate
from forum_agents.tools.data import validate_against_schema

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "api_backed_spa"


def test_api_discovery_candidate_selection() -> None:
    """Verify API candidate selection prefers JSON endpoints."""
    candidates = [
        {
            "url": "https://example.com/page.html",
            "method": "GET",
            "response_status": 200,
            "response_content_type": "text/html",
        },
        {
            "url": "https://example.com/api/v1/products",
            "method": "GET",
            "response_status": 200,
            "response_content_type": "application/json",
        },
        {
            "url": "https://example.com/api/v1/analytics",
            "method": "POST",
            "response_status": 200,
            "response_content_type": "application/json",
        },
    ]

    best = _pick_best_candidate(candidates)
    assert best is not None
    assert "api/v1/products" in best["url"]


def test_api_extraction_code_template() -> None:
    """Verify a typical API extraction code template compiles."""
    mock_code = '''
SELECTORS = {
    "api_endpoint": "https://example.com/api/v1/products",
}

async def extract(page) -> list[dict]:
    """Extract data from API response."""
    from forum_browser.http import StealthHttpClient
    import json

    async with StealthHttpClient() as client:
        resp = await client.get("https://example.com/api/v1/products")
        data = json.loads(resp.text)
        rows = []
        for item in data.get("products", []):
            rows.append({
                "name": item.get("name", ""),
                "price": item.get("price", 0),
            })
    return rows
'''
    compile(mock_code, "<test>", "exec")


def test_api_fixture_files_exist() -> None:
    assert (FIXTURES_DIR / "config.json").exists()
    assert (FIXTURES_DIR / "dom_initial.html").exists()
    assert (FIXTURES_DIR / "api_response.json").exists()
    assert (FIXTURES_DIR / "expected_schema.json").exists()
    assert (FIXTURES_DIR / "expected_data.json").exists()


def test_api_fixture_config() -> None:
    config = json.loads((FIXTURES_DIR / "config.json").read_text())
    assert config["expected_nav_mode"] == "API_DISCOVERY"
    assert "api_endpoint" in config


def test_api_fixture_html_is_spa() -> None:
    html = (FIXTURES_DIR / "dom_initial.html").read_text()
    assert 'id="app"' in html
    assert "app.bundle.js" in html


def test_api_response_structure() -> None:
    api_data = json.loads((FIXTURES_DIR / "api_response.json").read_text())
    assert "data" in api_data
    assert "trades" in api_data["data"]
    assert len(api_data["data"]["trades"]) == 5
    trade = api_data["data"]["trades"][0]
    assert "symbol" in trade
    assert "price" in trade


def test_api_data_matches_schema() -> None:
    schema = json.loads((FIXTURES_DIR / "expected_schema.json").read_text())
    data = json.loads((FIXTURES_DIR / "expected_data.json").read_text())

    result = validate_against_schema(data, schema)
    assert result.success, f"Validation errors: {result.data.get('errors', [])}"
    assert result.data["row_count"] == 5


def test_api_analysis_response() -> None:
    mock_response = json.dumps({
        "page_type": "spa_with_api",
        "data_regions": [{"selector": "#trades", "description": "Trade data table"}],
        "has_pagination": False,
        "pagination": None,
        "recommended_nav_mode": "API_DISCOVERY",
        "api_endpoint": "https://example.com/api/v2/trades",
        "confidence": 0.88,
    })

    result = _parse_analysis(mock_response)
    assert result["page_type"] == "spa_with_api"
    assert result["recommended_nav_mode"] == "API_DISCOVERY"
