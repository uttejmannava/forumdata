"""Per-run context. Local mode: filesystem instead of S3, .env instead of Secrets Manager."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunContext:
    """Minimal run context for local pipeline execution."""

    code_dir: Path
    tenant_id: str = "local"
    pipeline_id: str = "local"
    run_id: str = ""
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = f"run_{uuid.uuid4().hex[:8]}"
        if self.output_dir is None:
            self.output_dir = self.code_dir / "runs" / self.run_id
