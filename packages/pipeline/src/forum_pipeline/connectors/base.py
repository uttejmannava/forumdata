"""Base connector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from forum_pipeline.context import RunContext


@dataclass
class DeliveryResult:
    """Result of delivering data to a destination."""

    connector: str
    success: bool
    destination: str  # S3 URI, webhook URL, etc.
    rows_delivered: int
    error: str | None = None
    metadata: dict[str, Any] | None = None


class Connector(ABC):
    """Abstract base for destination connectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Connector identifier (e.g., 's3', 'webhook')."""
        ...

    @abstractmethod
    async def deliver(
        self,
        rows: list[dict[str, Any]],
        ctx: RunContext,
        config: dict[str, Any],
    ) -> DeliveryResult:
        """Deliver data to the destination. Returns a receipt."""
        ...
