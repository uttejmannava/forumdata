"""LLM Gateway — direct Anthropic SDK wrapper with model routing.

Phase 0: direct SDK calls. Phase 1: extract to a gateway service with
semantic caching, budget enforcement, and usage tracking.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import anthropic  # noqa: F401


class AgentRole(StrEnum):
    """Agent roles mapped to appropriate models."""

    PAGE_ANALYSIS = "page_analysis"
    SCHEMA_INFERENCE = "schema_inference"
    NAVIGATION_CODEGEN = "navigation_codegen"
    EXTRACTION_CODEGEN = "extraction_codegen"
    CHANGE_DETECTION = "change_detection"


_MODEL_ROUTING: dict[AgentRole, str] = {
    AgentRole.PAGE_ANALYSIS: "claude-haiku-4-5-20251001",
    AgentRole.SCHEMA_INFERENCE: "claude-sonnet-4-6",
    AgentRole.NAVIGATION_CODEGEN: "claude-sonnet-4-6",
    AgentRole.EXTRACTION_CODEGEN: "claude-sonnet-4-6",
    AgentRole.CHANGE_DETECTION: "claude-haiku-4-5-20251001",
}


@dataclass
class LlmResponse:
    """Response from an LLM call."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


@dataclass
class LlmGateway:
    """Direct Anthropic SDK wrapper with model routing."""

    api_key: str | None = None
    max_tokens: int = 4096
    mock_responses: list[LlmResponse] | None = None
    _client: Any = field(init=False, repr=False)
    _mock_index: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        if self.mock_responses is not None:
            self._client = None
            return
        import anthropic as _anthropic

        key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY required")
        self._client = _anthropic.AsyncAnthropic(api_key=key)

    async def complete(
        self,
        role: AgentRole,
        system: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
    ) -> LlmResponse:
        """Send a completion request routed to the appropriate model."""
        if self.mock_responses is not None:
            if self._mock_index >= len(self.mock_responses):
                raise RuntimeError("No more mock responses available")
            resp = self.mock_responses[self._mock_index]
            self._mock_index += 1
            return resp

        model = _MODEL_ROUTING[role]
        kwargs: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LlmResponse(
            content=content,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

    async def complete_with_tools(
        self,
        role: AgentRole,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> Any:
        """Send a completion with tool use, returning raw Message for tool call parsing."""
        if self.mock_responses is not None:
            raise NotImplementedError("complete_with_tools not supported in mock mode")

        model = _MODEL_ROUTING[role]
        return await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
        )
