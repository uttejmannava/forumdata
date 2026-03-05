"""Shared test fixtures for forum_agents tests."""

from __future__ import annotations

import pytest

from forum_agents.llm_gateway import LlmGateway, LlmResponse


@pytest.fixture
def mock_llm() -> LlmGateway:
    """LLM gateway with mock responses for testing."""
    return LlmGateway(
        mock_responses=[
            LlmResponse(
                content='{"page_type": "static_html"}',
                model="claude-haiku-4-5-20251001",
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )
