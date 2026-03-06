"""Per-run context. Local mode: filesystem. Production: S3 + Secrets Manager."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class RunContext:
    """Pipeline run context populated from environment or CLI args."""

    # Identity
    tenant_id: str = "local"
    pipeline_id: str = "local"
    run_id: str = ""
    code_version: str = "latest"

    # Environment
    forum_env: str = "local"  # local | staging | prod

    # Paths (local mode)
    code_dir: Path | None = None
    output_dir: Path | None = None

    # Run tracking
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        if self.output_dir is None and self.code_dir is not None:
            self.output_dir = self.code_dir / "runs" / self.run_id

    @classmethod
    def from_env(cls, code_dir: Path | None = None) -> RunContext:
        """Create context from environment variables with CLI override for code_dir."""
        forum_env = os.environ.get("FORUM_ENV", "local")
        tenant_id = os.environ.get("TENANT_ID", "local")
        pipeline_id = os.environ.get("PIPELINE_ID", "local")
        run_id = os.environ.get("RUN_ID", "")
        code_version = os.environ.get("CODE_VERSION", "latest")

        return cls(
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            run_id=run_id,
            code_version=code_version,
            forum_env=forum_env,
            code_dir=code_dir,
        )

    @property
    def is_local(self) -> bool:
        return self.forum_env == "local"

    def s3_data_prefix(self) -> str:
        """S3 key prefix for this run's output data."""
        return (
            f"tenants/{self.tenant_id}/pipelines/{self.pipeline_id}"
            f"/runs/{self.run_id}"
        )

    def s3_code_prefix(self) -> str:
        """S3 key prefix for code artifacts."""
        return (
            f"tenants/{self.tenant_id}/pipelines/{self.pipeline_id}"
            f"/code/{self.code_version}"
        )

    def add_error(self, code: str, message: str, **extra: Any) -> None:
        """Record a structured error using ForumError shape."""
        from forum_schemas.models.errors import ErrorCode, ForumError

        self.errors.append(
            ForumError(
                code=ErrorCode(code),
                message=message,
                context=extra,
            ).model_dump(mode="json")
        )

    def add_warning(self, code: str, message: str, **extra: Any) -> None:
        """Record a structured warning using ForumError shape."""
        from forum_schemas.models.errors import ForumError, WarningCode

        self.warnings.append(
            ForumError(
                code=WarningCode(code),
                message=message,
                context=extra,
            ).model_dump(mode="json")
        )
