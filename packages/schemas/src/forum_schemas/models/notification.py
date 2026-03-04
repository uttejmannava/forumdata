"""Notification subscription and condition models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Channel(enum.StrEnum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    WEBSOCKET = "websocket"


class ConditionOperator(enum.StrEnum):
    """Condition operators for notification filtering. Per bible.md §12.6."""

    FIELD_CHANGED = "field_changed"
    THRESHOLD_GT = "threshold_gt"
    THRESHOLD_LT = "threshold_lt"
    PCT_CHANGE_GT = "pct_change_gt"
    NEW_ROWS = "new_rows"
    REMOVED_ROWS = "removed_rows"
    KEYWORD_MATCH = "keyword_match"
    IN = "in"


class Condition(BaseModel):
    """A single notification condition."""

    field: str | None = Field(None, description="Target field name (null for row-level conditions)")
    operator: ConditionOperator
    value: float | str | list[str] | None = None


class NotificationSubscription(BaseModel):
    """Notification subscription for pipeline events. Per bible.md §12.6."""

    id: UUID = Field(default_factory=uuid4)
    pipeline_id: UUID
    tenant_id: UUID
    channel: Channel
    endpoint: str = Field(..., description="Email address, Slack webhook URL, or HTTP endpoint")
    events: list[str] = Field(default_factory=lambda: ["run_completed"])
    conditions: list[Condition] = Field(default_factory=list)
    is_active: bool = Field(True)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
