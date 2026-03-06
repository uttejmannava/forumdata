"""Pipeline-specific error types."""

from __future__ import annotations

from forum_schemas.models.errors import ErrorCode


class StageError(Exception):
    """Raised when a pipeline stage fails with a structured error code."""

    def __init__(self, code: ErrorCode, message: str, **context: object) -> None:
        self.code = code
        self.message = message
        self.context = context
        super().__init__(message)
