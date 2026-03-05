"""Tests for the Extraction Agent."""

from __future__ import annotations

from forum_agents.agents.extraction import (
    ExtractionResult,
    _extract_selectors,
    _parse_json_response,
)


def test_parse_json_response_valid() -> None:
    result = _parse_json_response('{"columns": [], "primary_key": ["id"]}')
    assert result["primary_key"] == ["id"]


def test_parse_json_response_markdown() -> None:
    result = _parse_json_response('```json\n{"key": "val"}\n```')
    assert result["key"] == "val"


def test_parse_json_response_invalid() -> None:
    result = _parse_json_response("not json")
    assert result == {}


def test_extract_selectors_from_code() -> None:
    code = '''
SELECTORS = {
    "name": "td:nth-child(1)",
    "price": "td:nth-child(2)",
}

async def extract(page):
    return []
'''
    selectors = _extract_selectors(code)
    assert selectors == {"name": "td:nth-child(1)", "price": "td:nth-child(2)"}


def test_extract_selectors_no_selectors() -> None:
    code = "async def extract(page):\n    return []\n"
    assert _extract_selectors(code) == {}


def test_extract_selectors_syntax_error() -> None:
    assert _extract_selectors("this is not python {{{") == {}


def test_extraction_result_defaults() -> None:
    r = ExtractionResult(success=True)
    assert r.extraction_code == ""
    assert r.schema == {}
    assert r.sample_data == []
    assert r.selectors == {}
    assert r.row_count == 0
