"""Tests for the Notify stage."""

from __future__ import annotations

from pathlib import Path

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData
from forum_pipeline.stages.notify import run_notify


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    return RunContext(code_dir=tmp_path)


async def test_notify_no_subscriptions(ctx: RunContext) -> None:
    data = StageData(rows=[{"a": 1}], config={})
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["skipped"] is True


async def test_notify_run_completed(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"a": 1}],
        config={
            "notifications": [
                {
                    "events": ["run_completed"],
                    "channel": "webhook",
                    "endpoint": "https://example.com/notify",
                }
            ]
        },
    )
    result = await run_notify(data, ctx)
    meta = result.stage_metadata["notify"]
    assert meta["notifications_dispatched"] == 1
    assert meta["dispatched"][0]["mode"] == "local_dry_run"


async def test_notify_inactive_subscription(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"a": 1}],
        config={
            "notifications": [
                {
                    "is_active": False,
                    "events": ["run_completed"],
                    "channel": "webhook",
                    "endpoint": "https://example.com/notify",
                }
            ]
        },
    )
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 0


async def test_notify_run_failed_event(ctx: RunContext) -> None:
    ctx.add_error("EXTRACTION_FAILED", "test error")
    data = StageData(
        rows=[],
        config={
            "notifications": [
                {"events": ["run_failed"], "channel": "webhook", "endpoint": "https://example.com"}
            ]
        },
    )
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 1


async def test_notify_event_no_match(ctx: RunContext) -> None:
    """run_failed event shouldn't trigger when there are no errors."""
    data = StageData(
        rows=[{"a": 1}],
        config={
            "notifications": [
                {"events": ["run_failed"], "channel": "webhook", "endpoint": "https://example.com"}
            ]
        },
    )
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 0


async def test_notify_threshold_condition(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"price": 150.0}],
        config={
            "notifications": [
                {
                    "events": ["run_completed"],
                    "conditions": [{"operator": "threshold_gt", "field": "price", "value": 100}],
                    "channel": "webhook",
                    "endpoint": "https://example.com",
                }
            ]
        },
    )
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 1


async def test_notify_threshold_condition_not_met(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"price": 50.0}],
        config={
            "notifications": [
                {
                    "events": ["run_completed"],
                    "conditions": [{"operator": "threshold_gt", "field": "price", "value": 100}],
                    "channel": "webhook",
                    "endpoint": "https://example.com",
                }
            ]
        },
    )
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 0


async def test_notify_new_rows_plus_threshold(ctx: RunContext) -> None:
    """new_rows condition should not short-circuit; subsequent conditions must also be evaluated."""
    data = StageData(
        rows=[{"price": 50.0}],
        config={
            "notifications": [
                {
                    "events": ["run_completed"],
                    "conditions": [
                        {"operator": "new_rows"},
                        {"operator": "threshold_gt", "field": "price", "value": 100},
                    ],
                    "channel": "webhook",
                    "endpoint": "https://example.com",
                }
            ]
        },
    )
    result = await run_notify(data, ctx)
    # new_rows passes (rows exist), but threshold_gt fails (50 < 100) -> no dispatch
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 0


async def test_notify_keyword_match(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"status": "Critical Alert: server down"}],
        config={
            "notifications": [
                {
                    "events": ["run_completed"],
                    "conditions": [{"operator": "keyword_match", "field": "status", "value": "critical"}],
                    "channel": "webhook",
                    "endpoint": "https://example.com",
                }
            ]
        },
    )
    result = await run_notify(data, ctx)
    assert result.stage_metadata["notify"]["notifications_dispatched"] == 1
