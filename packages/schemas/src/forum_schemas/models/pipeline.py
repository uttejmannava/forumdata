"""Pipeline, run, and configuration models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PipelineStatus(enum.StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class PipelineType(enum.StrEnum):
    """Pipeline types per bible.md §12.5."""

    EXTRACTION = "extraction"  # Full E-C-T-V-L-N cycle
    MONITOR = "monitor"  # Lightweight change detection only
    HYBRID = "hybrid"  # Monitor + extraction on change


class NavigationMode(enum.StrEnum):
    """Navigation mode tiers per bible.md §5.4."""

    SINGLE_PAGE = "single_page"
    PAGINATED_LIST = "paginated_list"
    LIST_DETAIL = "list_detail"
    MULTI_STEP = "multi_step"
    API_DISCOVERY = "api_discovery"
    AGENTIC = "agentic"


class StealthLevel(enum.StrEnum):
    """Adaptive stealth levels per bible.md §4.3."""

    NONE = "none"  # curl_cffi with TLS impersonation, no browser
    BASIC = "basic"  # Headless browser, datacenter proxy, resource blocking
    STANDARD = "standard"  # TLS spoofing, device profiles, behavioral patterns, residential proxy
    AGGRESSIVE = "aggressive"  # All 4 layers active


class RunStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineConfig(BaseModel):
    """Pipeline configuration stored alongside the pipeline definition."""

    schedule: str | None = Field(None, description="Cron expression for scheduled runs")
    navigation_mode: NavigationMode = Field(NavigationMode.SINGLE_PAGE, description="Navigation mode tier")
    stealth_level: StealthLevel = Field(StealthLevel.NONE, description="Minimum stealth level")
    proxy_region: str | None = Field(None, description="Geo-targeted proxy region")
    max_tabs: int = Field(5, description="Tab pool size for multi-page modes", ge=1, le=20)
    resource_blocking_enabled: bool = Field(True, description="Block fonts/images/stylesheets/tracking")
    blocked_domains: list[str] = Field(default_factory=list, description="Domains to block at browser level")
    schedule_jitter_minutes: int = Field(0, description="Random jitter ±N minutes on schedule", ge=0, le=15)
    timeout_seconds: int = Field(300, description="Max execution time per run", ge=30, le=3600)


class Pipeline(BaseModel):
    """Core pipeline model."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=2000)
    source_url: str = Field(..., min_length=1)
    pipeline_type: PipelineType = Field(PipelineType.EXTRACTION)
    status: PipelineStatus = Field(PipelineStatus.DRAFT)
    config: PipelineConfig = Field(default_factory=lambda: PipelineConfig())
    schema_id: UUID | None = Field(None, description="Active extraction schema ID")
    code_version: int | None = Field(None, description="Active code artifact version")
    tags: list[str] = Field(default_factory=list)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineRun(BaseModel):
    """Record of a single pipeline execution."""

    id: UUID = Field(default_factory=uuid4)
    pipeline_id: UUID
    tenant_id: UUID
    status: RunStatus = Field(RunStatus.PENDING)
    trigger: str = Field("scheduled", description="scheduled | manual | self_heal | backfill")
    code_version: int | None = None
    schema_version: int | None = None
    row_count: int | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
