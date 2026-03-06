"""Tests for RunContext."""

from __future__ import annotations

from pathlib import Path

from forum_pipeline.context import RunContext


def test_run_context_defaults() -> None:
    ctx = RunContext()
    assert ctx.tenant_id == "local"
    assert ctx.pipeline_id == "local"
    assert ctx.run_id.startswith("run_")
    assert len(ctx.run_id) == 16  # "run_" + 12 hex chars
    assert ctx.forum_env == "local"
    assert ctx.is_local is True
    assert ctx.code_dir is None
    assert ctx.output_dir is None


def test_run_context_with_code_dir(tmp_path: Path) -> None:
    ctx = RunContext(code_dir=tmp_path)
    assert ctx.output_dir is not None
    assert str(tmp_path) in str(ctx.output_dir)
    assert ctx.run_id in str(ctx.output_dir)


def test_run_context_custom_values(tmp_path: Path) -> None:
    ctx = RunContext(
        code_dir=tmp_path,
        tenant_id="acme",
        pipeline_id="pip_123",
        run_id="run_custom",
    )
    assert ctx.tenant_id == "acme"
    assert ctx.run_id == "run_custom"


def test_from_env(tmp_path: Path, monkeypatch: object) -> None:
    mp = monkeypatch  # type: ignore[assignment]
    mp.setenv("FORUM_ENV", "staging")
    mp.setenv("TENANT_ID", "acme")
    mp.setenv("PIPELINE_ID", "pip_test")
    mp.setenv("RUN_ID", "run_abc")
    mp.setenv("CODE_VERSION", "v3")

    ctx = RunContext.from_env(code_dir=tmp_path)
    assert ctx.forum_env == "staging"
    assert ctx.tenant_id == "acme"
    assert ctx.pipeline_id == "pip_test"
    assert ctx.run_id == "run_abc"
    assert ctx.code_version == "v3"
    assert ctx.is_local is False


def test_s3_data_prefix() -> None:
    ctx = RunContext(tenant_id="acme", pipeline_id="pip_1", run_id="run_x")
    assert ctx.s3_data_prefix() == "tenants/acme/pipelines/pip_1/runs/run_x"


def test_s3_code_prefix() -> None:
    ctx = RunContext(tenant_id="acme", pipeline_id="pip_1", code_version="v5")
    assert ctx.s3_code_prefix() == "tenants/acme/pipelines/pip_1/code/v5"


def test_add_error() -> None:
    ctx = RunContext()
    ctx.add_error("EXTRACTION_FAILED", "something broke", detail="test")
    assert len(ctx.errors) == 1
    assert ctx.errors[0]["code"] == "EXTRACTION_FAILED"
    assert ctx.errors[0]["message"] == "something broke"
    assert ctx.errors[0]["context"]["detail"] == "test"


def test_add_warning() -> None:
    ctx = RunContext()
    ctx.add_warning("EMPTY_RESULTS", "no rows found")
    assert len(ctx.warnings) == 1
    assert ctx.warnings[0]["code"] == "EMPTY_RESULTS"
    assert ctx.warnings[0]["message"] == "no rows found"
