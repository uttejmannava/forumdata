"""Extraction schema models — versioning, templates, breaking change detection."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ColumnType(enum.StrEnum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    JSON = "json"


class SchemaStatus(enum.StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class ChangeType(enum.StrEnum):
    INITIAL = "initial"
    USER_EDIT = "user_edit"
    AUTO_HEAL = "auto_heal"
    SOURCE_CHANGE = "source_change"


class ColumnConstraints(BaseModel):
    """Constraints on a column value."""

    min: float | None = None
    max: float | None = None
    pattern: str | None = Field(None, description="Regex pattern for string validation")
    allowed_values: list[str] | None = None


class ColumnDefinition(BaseModel):
    """A single column in an extraction schema."""

    name: str = Field(..., min_length=1, max_length=255)
    type: ColumnType
    description: str = Field("", max_length=500)
    nullable: bool = Field(True)
    constraints: ColumnConstraints | None = None
    example: str | None = None


class ExtractionSchema(BaseModel):
    """Versioned extraction schema for a pipeline. Per bible.md §9.2."""

    id: UUID = Field(default_factory=uuid4)
    pipeline_id: UUID
    version: int = Field(..., ge=1)
    columns: list[ColumnDefinition]
    primary_key: list[str] = Field(default_factory=list)
    dedup_key: list[str] = Field(default_factory=list)
    parent_version: int | None = None
    change_type: ChangeType = Field(ChangeType.INITIAL)
    change_summary: str | None = None
    breaking: bool = Field(False)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    promoted_at: datetime | None = None
    status: SchemaStatus = Field(SchemaStatus.DRAFT)


class SchemaTemplate(BaseModel):
    """Reusable schema template shared across pipelines. Per bible.md §9.6."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=2000)
    columns: list[ColumnDefinition]
    primary_key: list[str] = Field(default_factory=list)
    dedup_key: list[str] = Field(default_factory=list)
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
