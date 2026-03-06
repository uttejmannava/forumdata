"""Webhook connector — POST extracted data to a customer HTTP endpoint."""

from __future__ import annotations

import json
from typing import Any

from forum_schemas.models.errors import ErrorCode

from forum_pipeline.connectors.base import Connector, DeliveryResult
from forum_pipeline.context import RunContext
from forum_pipeline.errors import StageError


class WebhookConnector(Connector):
    """Delivers data via HTTP POST to a configured webhook URL."""

    @property
    def name(self) -> str:
        return "webhook"

    async def deliver(
        self,
        rows: list[dict[str, Any]],
        ctx: RunContext,
        config: dict[str, Any],
    ) -> DeliveryResult:
        """POST rows as JSON to the configured webhook endpoint."""
        url = config.get("webhook_url", "")
        if not url:
            raise StageError(
                ErrorCode.DELIVERY_FAILED,
                "Webhook connector requires 'webhook_url' in destination config",
            )

        headers = config.get("webhook_headers", {"Content-Type": "application/json"})
        timeout = config.get("webhook_timeout", 30)

        payload = json.dumps(
            {
                "event": "pipeline.data_ready",
                "run_id": ctx.run_id,
                "tenant_id": ctx.tenant_id,
                "pipeline_id": ctx.pipeline_id,
                "row_count": len(rows),
                "data": rows,
            },
            default=str,
        )

        if ctx.is_local:
            # In local mode, just log the payload that would be sent
            return DeliveryResult(
                connector="webhook",
                success=True,
                destination=url,
                rows_delivered=len(rows),
                metadata={"mode": "local_dry_run", "payload_size": len(payload)},
            )

        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, content=payload, headers=headers)
                response.raise_for_status()

            return DeliveryResult(
                connector="webhook",
                success=True,
                destination=url,
                rows_delivered=len(rows),
                metadata={"status_code": response.status_code},
            )
        except Exception as e:
            raise StageError(
                ErrorCode.DELIVERY_FAILED,
                f"Webhook delivery to {url} failed: {e}",
            ) from e
