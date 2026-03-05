"""Tests for the LLM gateway."""

from __future__ import annotations

import pytest

from forum_agents.llm_gateway import AgentRole, LlmGateway, LlmResponse


def test_agent_role_values() -> None:
    assert AgentRole.PAGE_ANALYSIS == "page_analysis"
    assert AgentRole.SCHEMA_INFERENCE == "schema_inference"
    assert AgentRole.NAVIGATION_CODEGEN == "navigation_codegen"
    assert AgentRole.EXTRACTION_CODEGEN == "extraction_codegen"
    assert AgentRole.CHANGE_DETECTION == "change_detection"


def test_gateway_requires_api_key() -> None:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        pytest.skip("anthropic not installed")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY required"):
        LlmGateway(api_key=None)


def test_mock_gateway_no_api_key_needed() -> None:
    gw = LlmGateway(mock_responses=[LlmResponse("test", "model", 10, 5)])
    assert gw.mock_responses is not None


@pytest.mark.asyncio
async def test_mock_gateway_returns_responses() -> None:
    responses = [
        LlmResponse("response1", "model-a", 10, 5),
        LlmResponse("response2", "model-b", 20, 10),
    ]
    gw = LlmGateway(mock_responses=responses)

    r1 = await gw.complete(AgentRole.PAGE_ANALYSIS, "sys", [{"role": "user", "content": "hi"}])
    assert r1.content == "response1"

    r2 = await gw.complete(AgentRole.SCHEMA_INFERENCE, "sys", [{"role": "user", "content": "hi"}])
    assert r2.content == "response2"


@pytest.mark.asyncio
async def test_mock_gateway_exhausted() -> None:
    gw = LlmGateway(mock_responses=[LlmResponse("only", "m", 1, 1)])
    await gw.complete(AgentRole.PAGE_ANALYSIS, "sys", [{"role": "user", "content": "hi"}])

    with pytest.raises(RuntimeError, match="No more mock responses"):
        await gw.complete(AgentRole.PAGE_ANALYSIS, "sys", [{"role": "user", "content": "hi"}])
