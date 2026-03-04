"""Tenant, workspace, user, and role models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class TenantTier(enum.StrEnum):
    """Pricing tiers per bible.md §6.2."""

    FREE = "free"
    SELF_SERVICE = "self_service"
    ENTERPRISE_BASE = "enterprise_base"
    ENTERPRISE_DEDICATED = "enterprise_dedicated"


class Role(enum.StrEnum):
    """RBAC roles per bible.md §10.1."""

    ADMIN = "admin"
    ANALYST = "analyst"
    COMPLIANCE_OFFICER = "compliance_officer"
    VIEWER = "viewer"


class Tenant(BaseModel):
    """A tenant organization."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=63, pattern=r"^[a-z0-9-]+$")
    tier: TenantTier = Field(TenantTier.FREE)
    credits_remaining: int = Field(500, ge=0)
    credits_monthly_limit: int = Field(500, ge=0)
    active_pipeline_limit: int = Field(5, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Workspace(BaseModel):
    """Sub-organizational unit within a tenant (Enterprise feature)."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class User(BaseModel):
    """Platform user."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    workspace_id: UUID | None = None
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    role: Role = Field(Role.ANALYST)
    is_active: bool = Field(True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None
