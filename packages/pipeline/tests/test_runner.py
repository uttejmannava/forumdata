"""Tests for the pipeline runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.runner import parse_stages, run_pipeline


def test_parse_stages_all() -> None:
    stages = parse_stages("all")
    assert stages == ["extract", "cleanse", "transform", "validate", "load", "notify"]


def test_parse_stages_single() -> None:
    assert parse_stages("extract") == ["extract"]
    assert parse_stages("cleanse") == ["cleanse"]


def test_parse_stages_multiple() -> None:
    assert parse_stages("cleanse,transform,validate") == ["cleanse", "transform", "validate"]


def test_parse_stages_invalid() -> None:
    with pytest.raises(ValueError, match="Unknown stage"):
        parse_stages("nonexistent")


def test_run_context_defaults(tmp_path: Path) -> None:
    ctx = RunContext(code_dir=tmp_path)
    assert ctx.tenant_id == "local"
    assert ctx.pipeline_id == "local"
    assert ctx.run_id.startswith("run_")
    assert ctx.output_dir is not None
    assert str(tmp_path) in str(ctx.output_dir)


def test_run_context_custom_values(tmp_path: Path) -> None:
    ctx = RunContext(
        code_dir=tmp_path,
        tenant_id="acme",
        pipeline_id="pip_123",
        run_id="run_custom",
    )
    assert ctx.tenant_id == "acme"
    assert ctx.run_id == "run_custom"


def test_runner_function_exists() -> None:
    assert callable(run_pipeline)


async def test_pipeline_missing_config(tmp_path: Path) -> None:
    result = await run_pipeline(tmp_path, stage="all")
    assert result["success"] is False
    assert len(result["errors"]) > 0


async def test_pipeline_missing_source_url(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"stealth_level": "basic"}))
    result = await run_pipeline(tmp_path, stage="all")
    assert result["success"] is False


async def test_pipeline_invalid_stage(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"source_url": "https://example.com"}))
    result = await run_pipeline(tmp_path, stage="nonexistent")
    assert result["success"] is False


async def test_pipeline_cleanse_transform_validate(tmp_path: Path) -> None:
    """Test running mid-pipeline stages with pre-loaded data."""
    config = {"source_url": "https://example.com", "stealth_level": "basic"}
    schema = {
        "columns": [
            {"name": "product", "type": "STRING", "nullable": False},
            {"name": "price", "type": "FLOAT", "nullable": False},
        ]
    }
    (tmp_path / "config.json").write_text(json.dumps(config))
    (tmp_path / "schema.json").write_text(json.dumps(schema))

    # Create a previous run's data to load from
    run_dir = tmp_path / "runs" / "run_prev"
    run_dir.mkdir(parents=True)
    (run_dir / "data.json").write_text(json.dumps({
        "data": [
            {"product": "Widget A", "price": "9.99"},
            {"product": "Widget B", "price": "14.99"},
        ]
    }))

    result = await run_pipeline(tmp_path, stage="cleanse,transform,validate")
    assert result["success"] is True
    assert result["row_count"] == 2
    # Verify price was cast to float
    assert result["data"][0]["price"] == 9.99
