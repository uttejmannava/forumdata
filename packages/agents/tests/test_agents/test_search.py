"""Tests for the Search Agent."""

from __future__ import annotations

from forum_agents.agents.base import AgentContext
from forum_agents.agents.search import SearchResult, _parse_analysis
from forum_agents.llm_gateway import LlmGateway

from forum_schemas.models.pipeline import NavigationMode


def test_parse_analysis_valid_json() -> None:
    content = '{"page_type": "static_html", "data_regions": [{"selector": "table", "description": "main table"}], "recommended_nav_mode": "SINGLE_PAGE"}'
    result = _parse_analysis(content)
    assert result["page_type"] == "static_html"
    assert len(result["data_regions"]) == 1


def test_parse_analysis_markdown_wrapped() -> None:
    content = '```json\n{"page_type": "spa_with_api", "data_regions": []}\n```'
    result = _parse_analysis(content)
    assert result["page_type"] == "spa_with_api"


def test_parse_analysis_invalid_json() -> None:
    result = _parse_analysis("not json at all")
    assert result["page_type"] == "static_html"


def test_search_result_defaults() -> None:
    r = SearchResult(success=True)
    assert r.recommended_nav_mode == NavigationMode.SINGLE_PAGE
    assert r.page_type == ""
    assert r.api_candidates == []
    assert r.robots_allowed is True


def test_agent_context_defaults() -> None:
    llm = LlmGateway(mock_responses=[])
    ctx = AgentContext(
        source_url="https://example.com",
        user_description="test",
        llm=llm,
    )
    assert ctx.tenant_id == "local"
    assert ctx.pipeline_id == "local"
