"""Tests for the pipeline runner."""

from __future__ import annotations

from forum_pipeline.context import RunContext
from forum_pipeline.runner import run_pipeline

from pathlib import Path


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
