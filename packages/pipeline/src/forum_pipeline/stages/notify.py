"""Notify stage — evaluate conditional notification rules and dispatch alerts.

Evaluates conditions from notification subscriptions (stored in config).
Currently supports webhook dispatch. Email/Slack/WebSocket deferred.
"""

from __future__ import annotations

import json
from typing import Any

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData


async def run_notify(data: StageData, ctx: RunContext) -> StageData:
    """Execute the Notify stage.

    Reads notification subscriptions from config, evaluates conditions,
    dispatches to matching channels.
    """
    subscriptions: list[dict[str, Any]] = data.config.get("notifications", [])
    if not subscriptions:
        data.stage_metadata["notify"] = {"skipped": True, "reason": "no subscriptions"}
        return data

    dispatched: list[dict[str, Any]] = []

    for sub in subscriptions:
        if not sub.get("is_active", True):
            continue

        conditions = sub.get("conditions", [])
        events = sub.get("events", ["run_completed"])

        # Check if this run's events match the subscription
        if not _events_match(events, ctx):
            continue

        # Evaluate data conditions (if any)
        if conditions and not _conditions_match(conditions, data.rows):
            continue

        # Build notification payload
        notification = _build_notification(data, ctx, sub)

        # Dispatch
        channel = sub.get("channel", "webhook")
        endpoint = sub.get("endpoint", "")

        if ctx.is_local:
            dispatched.append({
                "channel": channel,
                "endpoint": endpoint,
                "mode": "local_dry_run",
            })
        elif channel == "webhook" and endpoint:
            success = await _dispatch_webhook(endpoint, notification)
            dispatched.append({
                "channel": channel,
                "endpoint": endpoint,
                "success": success,
            })

    data.stage_metadata["notify"] = {
        "subscriptions_evaluated": len(subscriptions),
        "notifications_dispatched": len(dispatched),
        "dispatched": dispatched,
    }

    return data


def _events_match(events: list[str], ctx: RunContext) -> bool:
    """Check if this run's outcome matches the subscription's event filters."""
    has_errors = len(ctx.errors) > 0
    has_warnings = len(ctx.warnings) > 0

    for event in events:
        if event == "run_completed":
            return True
        if event == "run_failed" and has_errors:
            return True
        if event == "data_changed":
            return True  # Assume data changed for now; stale detection is Phase 2
        if event == "run_warning" and has_warnings:
            return True
    return False


def _conditions_match(
    conditions: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> bool:
    """Evaluate data-level conditions against extracted rows."""
    if not rows:
        return False

    for condition in conditions:
        operator = condition.get("operator", "")
        field = condition.get("field")
        value = condition.get("value")

        if operator == "new_rows":
            if len(rows) == 0:
                return False
            continue
        if operator == "threshold_gt" and field:
            if not any(
                isinstance(r.get(field), (int, float)) and r[field] > value
                for r in rows
            ):
                return False
        if operator == "threshold_lt" and field:
            if not any(
                isinstance(r.get(field), (int, float)) and r[field] < value
                for r in rows
            ):
                return False
        if operator == "keyword_match" and field and isinstance(value, str):
            if not any(value.lower() in str(r.get(field, "")).lower() for r in rows):
                return False

    return True


def _build_notification(
    data: StageData, ctx: RunContext, sub: dict[str, Any]
) -> dict[str, Any]:
    """Build the notification payload."""
    return {
        "event": "pipeline.run_completed",
        "run_id": ctx.run_id,
        "tenant_id": ctx.tenant_id,
        "pipeline_id": ctx.pipeline_id,
        "row_count": len(data.rows),
        "errors": ctx.errors,
        "warnings": ctx.warnings,
        "stage_metadata": data.stage_metadata,
    }


async def _dispatch_webhook(url: str, payload: dict[str, Any]) -> bool:
    """Send notification via HTTP POST. Returns True on success."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                content=json.dumps(payload, default=str),
                headers={"Content-Type": "application/json"},
            )
            return response.is_success
    except Exception:
        return False
