"""Tests for the Navigation Agent."""

from __future__ import annotations

from forum_agents.agents.navigation import NavigationResult, _clean_code, _SINGLE_PAGE_TEMPLATE


def test_clean_code_strips_markdown() -> None:
    raw = '```python\nasync def navigate(page, config):\n    pass\n```'
    cleaned = _clean_code(raw)
    assert cleaned.startswith("async def navigate")
    assert "```" not in cleaned


def test_clean_code_no_fences() -> None:
    raw = "async def navigate(page, config):\n    pass"
    assert _clean_code(raw) == raw


def test_single_page_template_valid_python() -> None:
    compile(_SINGLE_PAGE_TEMPLATE, "<test>", "exec")


def test_navigation_result_defaults() -> None:
    r = NavigationResult(success=True)
    assert r.navigation_code == ""
    assert r.pages_found == 0
    assert r.sample_html == []
