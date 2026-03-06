"""Tests for the Validate stage."""

from __future__ import annotations

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.errors import StageError
from forum_pipeline.stage_data import StageData
from forum_pipeline.stages.validate import run_validate


@pytest.fixture
def ctx(tmp_path):
    return RunContext(code_dir=tmp_path)


async def test_validate_passes_valid_data(ctx: RunContext, stage_data: StageData) -> None:
    result = await run_validate(stage_data, ctx)
    assert result.stage_metadata["validate"]["schema_errors"] == 0


async def test_validate_nullable_enforcement(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"name": None}],
        schema={"columns": [{"name": "name", "type": "STRING", "nullable": False}]},
        config={},
    )
    # Single row with error -> 100% rate -> should raise
    with pytest.raises(StageError) as exc_info:
        await run_validate(data, ctx)
    assert exc_info.value.code.value == "SCHEMA_MISMATCH"


async def test_validate_type_mismatch_warning(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"price": "not_a_number"}],
        schema={"columns": [{"name": "price", "type": "FLOAT", "nullable": False}]},
        config={},
    )
    result = await run_validate(data, ctx)
    assert result.stage_metadata["validate"]["schema_warnings"] > 0


async def test_validate_constraint_min(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"price": -5.0}],
        schema={
            "columns": [
                {"name": "price", "type": "FLOAT", "nullable": False, "constraints": {"min": 0}}
            ]
        },
        config={},
    )
    with pytest.raises(StageError):
        await run_validate(data, ctx)


async def test_validate_constraint_max(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"score": 150}],
        schema={
            "columns": [
                {"name": "score", "type": "INTEGER", "nullable": False, "constraints": {"max": 100}}
            ]
        },
        config={},
    )
    with pytest.raises(StageError):
        await run_validate(data, ctx)


async def test_validate_constraint_pattern(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"code": "ABC"}],
        schema={
            "columns": [
                {"name": "code", "type": "STRING", "nullable": False, "constraints": {"pattern": r"^\d+$"}}
            ]
        },
        config={},
    )
    with pytest.raises(StageError):
        await run_validate(data, ctx)


async def test_validate_low_error_rate_warns(ctx: RunContext) -> None:
    # 1 error out of 10 rows = 10% < 20% threshold -> warnings not error
    rows = [{"name": f"item_{i}"} for i in range(10)]
    rows[0]["name"] = None  # One null in non-nullable
    data = StageData(
        rows=rows,
        schema={"columns": [{"name": "name", "type": "STRING", "nullable": False}]},
        config={},
    )
    result = await run_validate(data, ctx)
    assert len(ctx.warnings) > 0
    assert result.stage_metadata["validate"]["schema_errors"] == 1


async def test_validate_confidence_scoring(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"a": 1}],
        schema={"columns": [{"name": "a", "type": "INTEGER", "nullable": True}]},
        grounding=[
            {"field": "a", "tier": "direct_selector"},
        ],
        config={},
    )
    result = await run_validate(data, ctx)
    confidence = result.stage_metadata["validate"]["field_confidence"]
    assert confidence["a"] == 0.95


async def test_validate_no_schema(ctx: RunContext) -> None:
    data = StageData(rows=[{"x": 1}], schema={}, config={})
    result = await run_validate(data, ctx)
    assert result.stage_metadata["validate"]["skipped"] is True


async def test_validate_confidence_block(ctx: RunContext) -> None:
    """Low confidence fields should block when threshold is configured."""
    data = StageData(
        rows=[{"a": 1}],
        schema={"columns": [{"name": "a", "type": "INTEGER", "nullable": True}]},
        grounding=[{"field": "a", "tier": "llm_relocation"}],  # 0.75 confidence
        config={"confidence_block_threshold": 0.8},
    )
    with pytest.raises(StageError) as exc_info:
        await run_validate(data, ctx)
    assert "confidence block threshold" in exc_info.value.message


async def test_validate_confidence_no_block_default(ctx: RunContext) -> None:
    """Without confidence_block_threshold, low confidence only warns."""
    data = StageData(
        rows=[{"a": 1}],
        schema={"columns": [{"name": "a", "type": "INTEGER", "nullable": True}]},
        grounding=[{"field": "a", "tier": "llm_relocation"}],  # 0.75 — below 0.9 medium
        config={},
    )
    result = await run_validate(data, ctx)
    # Should not raise, just warn
    assert "a" in result.stage_metadata["validate"]["medium_confidence_fields"]


async def test_validate_empty_rows(ctx: RunContext) -> None:
    data = StageData(rows=[], schema={"columns": [{"name": "x", "type": "STRING"}]}, config={})
    result = await run_validate(data, ctx)
    assert result.rows == []
