"""Base class for all sub-agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forum_agents.llm_gateway import LlmGateway


@dataclass
class AgentContext:
    """Shared context passed to all agents during a setup session."""

    source_url: str
    user_description: str
    llm: LlmGateway
    tenant_id: str = "local"
    pipeline_id: str = "local"
    working_dir: str = "./output"


@dataclass
class AgentResult:
    """Result from a sub-agent execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    llm_calls: int = 0
    total_tokens: int = 0
