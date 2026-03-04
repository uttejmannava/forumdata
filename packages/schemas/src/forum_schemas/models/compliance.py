"""Compliance rule and audit log models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ComplianceRuleType(enum.StrEnum):
    """Rule types per bible.md §11.2."""

    SOURCE_BLACKLIST = "source_blacklist"
    ROBOTS_TXT = "robots_txt"
    TOS_SCANNER = "tos_scanner"
    CAPTCHA_BLOCK = "captcha_block"
    PII_DETECTION = "pii_detection"
    RATE_LIMITING = "rate_limiting"


class ComplianceSeverity(enum.StrEnum):
    HARD_BLOCK = "hard_block"
    SOFT_BLOCK = "soft_block"  # Requires approval
    WARNING = "warning"


class ComplianceRule(BaseModel):
    """A compliance rule that pipelines are evaluated against."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    rule_type: ComplianceRuleType
    severity: ComplianceSeverity = Field(ComplianceSeverity.HARD_BLOCK)
    config: dict[str, Any] = Field(default_factory=dict, description="Rule-specific configuration")
    is_active: bool = Field(True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditLogEntry(BaseModel):
    """Immutable audit log entry. Per bible.md §11.4."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    actor: str = Field(..., description="user:email@example.com or system:agent-name")
    action: str = Field(..., description="pipeline.created, compliance.check.passed, etc.")
    resource_type: str = Field(..., description="pipeline, schema, credential, etc.")
    resource_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    compliance_checks: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
