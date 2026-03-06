"""S3 connector — write extracted data as JSON to tenant-namespaced S3 paths.

Production: writes to S3 via boto3
Local (FORUM_ENV=local): writes to local filesystem mirroring S3 key structure
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forum_pipeline.connectors.base import Connector, DeliveryResult
from forum_pipeline.context import RunContext

_DEFAULT_LOCAL_ROOT = Path.home() / ".forum" / "data"


class S3Connector(Connector):
    """Delivers data as JSON to S3 (or local filesystem in local mode)."""

    @property
    def name(self) -> str:
        return "s3"

    async def deliver(
        self,
        rows: list[dict[str, Any]],
        ctx: RunContext,
        config: dict[str, Any],
    ) -> DeliveryResult:
        """Write rows as JSON to the tenant's S3 prefix.

        S3 path: tenants/{tenant_id}/pipelines/{pipeline_id}/runs/{run_id}/data.json
        Local path: ~/.forum/data/tenants/... (mirrors S3 structure)
        """
        s3_key = f"{ctx.s3_data_prefix()}/data.json"

        payload = json.dumps(
            {
                "run_id": ctx.run_id,
                "tenant_id": ctx.tenant_id,
                "pipeline_id": ctx.pipeline_id,
                "row_count": len(rows),
                "data": rows,
            },
            indent=2,
            default=str,
        )

        if ctx.is_local:
            return await self._write_local(payload, s3_key, rows, ctx, config)
        else:
            return await self._write_s3(payload, s3_key, rows, ctx, config)

    async def _write_local(
        self,
        payload: str,
        s3_key: str,
        rows: list[dict[str, Any]],
        ctx: RunContext,
        config: dict[str, Any],
    ) -> DeliveryResult:
        """Write to local filesystem, mirroring S3 key structure."""
        local_root = Path(config.get("local_data_root", str(_DEFAULT_LOCAL_ROOT)))
        local_path = local_root / s3_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(payload, encoding="utf-8")

        # Also write to output_dir if set (for convenience)
        if ctx.output_dir:
            ctx.output_dir.mkdir(parents=True, exist_ok=True)
            (ctx.output_dir / "data.json").write_text(payload, encoding="utf-8")

        return DeliveryResult(
            connector="s3",
            success=True,
            destination=f"file://{local_path}",
            rows_delivered=len(rows),
            metadata={"s3_key": s3_key, "local_path": str(local_path)},
        )

    async def _write_s3(
        self,
        payload: str,
        s3_key: str,
        rows: list[dict[str, Any]],
        ctx: RunContext,
        config: dict[str, Any],
    ) -> DeliveryResult:
        """Write to actual S3. Requires boto3 (deferred — raises NotImplementedError)."""
        raise NotImplementedError(
            "S3 production writes require boto3 and AWS credentials. "
            "Use FORUM_ENV=local for local development."
        )
