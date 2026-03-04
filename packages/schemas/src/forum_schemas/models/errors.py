"""Forum error taxonomy — machine-readable error codes for API responses."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(enum.StrEnum):
    """Critical error codes per bible.md §12.3. Run marked FAILED."""

    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    COMPLIANCE_BLOCKED = "COMPLIANCE_BLOCKED"
    TIMEOUT = "TIMEOUT"
    PLAUSIBILITY_BLOCKED = "PLAUSIBILITY_BLOCKED"
    DETECTION_BLOCKED = "DETECTION_BLOCKED"


class WarningCode(enum.StrEnum):
    """Non-critical warning codes per bible.md §12.3. Run completes successfully."""

    EMPTY_RESULTS = "EMPTY_RESULTS"
    PARTIAL_RESULTS = "PARTIAL_RESULTS"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    STALE_DATA = "STALE_DATA"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    PLAUSIBILITY_WARNING = "PLAUSIBILITY_WARNING"
    DETECTION_SIGNAL = "DETECTION_SIGNAL"


class ForumError(BaseModel):
    """Structured error for API responses."""

    code: ErrorCode | WarningCode
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    context: dict[str, Any] = Field(default_factory=dict)
