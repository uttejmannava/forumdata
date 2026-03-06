"""Load stage — deliver validated data to configured destinations.

Reads destination config, dispatches to appropriate connector(s).
Also writes source grounding metadata alongside the data.
"""

from __future__ import annotations

import json
from typing import Any

from forum_schemas.models.errors import ErrorCode

from forum_pipeline.connectors.base import Connector, DeliveryResult
from forum_pipeline.connectors.s3 import S3Connector
from forum_pipeline.connectors.webhook import WebhookConnector
from forum_pipeline.context import RunContext
from forum_pipeline.errors import StageError
from forum_pipeline.stage_data import StageData

_CONNECTORS: dict[str, type[Connector]] = {
    "s3": S3Connector,
    "webhook": WebhookConnector,
}


async def run_load(data: StageData, ctx: RunContext) -> StageData:
    """Execute the Load stage.

    1. Determine destination(s) from config
    2. Deliver data via each configured connector
    3. Write source grounding metadata
    """
    if not data.rows:
        data.stage_metadata["load"] = {"skipped": True, "reason": "no rows"}
        return data

    destinations: list[dict[str, Any]] = data.config.get("destinations", [])

    # Default: S3 if no destinations configured
    if not destinations:
        destinations = [{"type": "s3"}]

    results: list[DeliveryResult] = []
    for dest in destinations:
        dest_type = dest.get("type", "s3")
        connector_cls = _CONNECTORS.get(dest_type)
        if connector_cls is None:
            ctx.add_warning(
                "PARTIAL_RESULTS",
                f"Unknown destination type '{dest_type}', skipping",
            )
            continue

        connector = connector_cls()
        try:
            result = await connector.deliver(data.rows, ctx, dest)
            results.append(result)
        except StageError:
            raise
        except Exception as e:
            raise StageError(
                ErrorCode.DELIVERY_FAILED,
                f"Connector '{dest_type}' failed: {e}",
            ) from e

    # Write source grounding metadata alongside data
    if data.grounding and ctx.is_local and ctx.output_dir:
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        grounding_path = ctx.output_dir / "grounding.json"
        grounding_path.write_text(
            json.dumps(data.grounding, indent=2, default=str),
            encoding="utf-8",
        )

    failed = [r for r in results if not r.success]
    if failed and not any(r.success for r in results):
        raise StageError(
            ErrorCode.DELIVERY_FAILED,
            f"All destinations failed: {[r.error for r in failed]}",
        )

    data.stage_metadata["load"] = {
        "destinations": [
            {"connector": r.connector, "destination": r.destination, "rows": r.rows_delivered}
            for r in results
        ],
        "total_delivered": sum(r.rows_delivered for r in results if r.success),
    }

    return data
