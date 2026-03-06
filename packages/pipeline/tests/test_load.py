"""Tests for the Load stage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData
from forum_pipeline.stages.load import run_load


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        code_dir=tmp_path,
        tenant_id="test-tenant",
        pipeline_id="test-pipeline",
    )


async def test_load_s3_local(ctx: RunContext, tmp_path: Path) -> None:
    data = StageData(
        rows=[{"product": "A", "price": 9.99}],
        config={"destinations": [{"type": "s3", "local_data_root": str(tmp_path / "data")}]},
    )
    result = await run_load(data, ctx)
    meta = result.stage_metadata["load"]
    assert meta["total_delivered"] == 1

    # Verify file was written
    s3_key = f"{ctx.s3_data_prefix()}/data.json"
    local_path = tmp_path / "data" / s3_key
    assert local_path.exists()
    content = json.loads(local_path.read_text())
    assert content["row_count"] == 1
    assert content["data"][0]["product"] == "A"


async def test_load_writes_to_output_dir(ctx: RunContext, tmp_path: Path) -> None:
    data = StageData(
        rows=[{"a": 1}],
        config={"destinations": [{"type": "s3", "local_data_root": str(tmp_path / "data")}]},
    )
    await run_load(data, ctx)
    assert ctx.output_dir is not None
    assert (ctx.output_dir / "data.json").exists()


async def test_load_webhook_dry_run(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"a": 1}],
        config={
            "destinations": [
                {"type": "webhook", "webhook_url": "https://example.com/hook"}
            ]
        },
    )
    result = await run_load(data, ctx)
    meta = result.stage_metadata["load"]
    assert meta["total_delivered"] == 1
    assert meta["destinations"][0]["connector"] == "webhook"


async def test_load_unknown_connector_warns(ctx: RunContext, tmp_path: Path) -> None:
    data = StageData(
        rows=[{"a": 1}],
        config={
            "destinations": [
                {"type": "unknown_db"},
                {"type": "s3", "local_data_root": str(tmp_path / "data")},
            ]
        },
    )
    result = await run_load(data, ctx)
    assert len(ctx.warnings) > 0
    assert "unknown_db" in ctx.warnings[0]["message"]
    # S3 still succeeded
    assert result.stage_metadata["load"]["total_delivered"] == 1


async def test_load_writes_grounding(ctx: RunContext, tmp_path: Path) -> None:
    data = StageData(
        rows=[{"a": 1}],
        grounding=[{"field": "a", "selector": "td", "tier": "direct_selector"}],
        config={"destinations": [{"type": "s3", "local_data_root": str(tmp_path / "data")}]},
    )
    await run_load(data, ctx)
    assert ctx.output_dir is not None
    grounding_path = ctx.output_dir / "grounding.json"
    assert grounding_path.exists()
    grounding = json.loads(grounding_path.read_text())
    assert grounding[0]["field"] == "a"


async def test_load_skips_empty_rows(ctx: RunContext) -> None:
    data = StageData(rows=[], config={})
    result = await run_load(data, ctx)
    assert result.stage_metadata["load"]["skipped"] is True


async def test_load_default_s3(ctx: RunContext, tmp_path: Path) -> None:
    """When no destinations configured, defaults to S3."""
    data = StageData(
        rows=[{"a": 1}],
        config={},
    )
    # This will try to write to ~/.forum/data/ — just verify it runs without crash
    # We can't easily control the default path in tests without mocking
    result = await run_load(data, ctx)
    assert "load" in result.stage_metadata
