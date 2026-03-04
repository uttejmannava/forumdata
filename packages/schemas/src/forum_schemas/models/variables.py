"""Pipeline variable models for parameterized pipelines."""

from __future__ import annotations

import enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VariableType(enum.StrEnum):
    """Variable types per bible.md §5.5."""

    STRING = "string"
    LIST = "list"
    SECRET = "secret"


class PipelineVariable(BaseModel):
    """A pipeline variable (string or list type). Value stored in pipeline config."""

    id: UUID = Field(default_factory=uuid4)
    pipeline_id: UUID
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    variable_type: VariableType = Field(VariableType.STRING)
    value: str | list[str] | None = Field(None, description="Value for string/list types. Null for secrets.")
    description: str = Field("", max_length=500)


class SecretVariable(BaseModel):
    """A secret variable. Value stored in AWS Secrets Manager, never in DB."""

    id: UUID = Field(default_factory=uuid4)
    pipeline_id: UUID
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = Field("", max_length=500)
    secret_arn: str | None = Field(None, description="Secrets Manager ARN (set after storage)")
