"""Pipeline runner — orchestrates the E-C-T-V-L-N stage chain.

Usage:
    # Full pipeline
    FORUM_ENV=local python -m forum_pipeline --code-dir ./output/ --stage all

    # Individual stages
    FORUM_ENV=local python -m forum_pipeline --code-dir ./output/ --stage extract
    FORUM_ENV=local python -m forum_pipeline --code-dir ./output/ --stage cleanse,transform,validate
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forum_schemas.models.errors import ErrorCode

from forum_pipeline.config import load_config, load_schema
from forum_pipeline.context import RunContext
from forum_pipeline.errors import StageError
from forum_pipeline.stage_data import StageData
from forum_pipeline.stages.cleanse import run_cleanse
from forum_pipeline.stages.extract import run_extract
from forum_pipeline.stages.load import run_load
from forum_pipeline.stages.notify import run_notify
from forum_pipeline.stages.transform import run_transform
from forum_pipeline.stages.validate import run_validate

# Ordered stage chain
_STAGES = [
    ("extract", run_extract),
    ("cleanse", run_cleanse),
    ("transform", run_transform),
    ("validate", run_validate),
    ("load", run_load),
    ("notify", run_notify),
]

_STAGE_NAMES = {name for name, _ in _STAGES}


def parse_stages(stage_arg: str) -> list[str]:
    """Parse the --stage argument into a list of stage names.

    Accepts: 'all', 'extract', 'cleanse,transform,validate', etc.
    """
    if stage_arg == "all":
        return [name for name, _ in _STAGES]

    requested = [s.strip().lower() for s in stage_arg.split(",")]
    for name in requested:
        if name not in _STAGE_NAMES:
            raise ValueError(
                f"Unknown stage '{name}'. Valid stages: {', '.join(_STAGE_NAMES)}, all"
            )
    return requested


async def run_pipeline(
    code_dir: Path,
    *,
    stage: str = "all",
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Run the E-C-T-V-L-N pipeline.

    Args:
        code_dir: Path to agent-generated code artifacts
        stage: Which stages to run ('all', 'extract', 'cleanse,transform', etc.)
        output_path: Optional path to write results JSON

    Returns:
        Run result dict compatible with PipelineRun shape
    """
    ctx = RunContext.from_env(code_dir=code_dir)
    start = time.monotonic()

    # Load config and schema
    try:
        config = load_config(code_dir)
        schema = load_schema(code_dir)
    except (FileNotFoundError, ValueError) as e:
        return _make_result(ctx, start, success=False, error=str(e))

    # Initialize stage data
    data = StageData(config=config, schema=schema)

    # Determine which stages to run
    try:
        stages_to_run = parse_stages(stage)
    except ValueError as e:
        return _make_result(ctx, start, success=False, error=str(e))

    # Build filtered stage chain
    stage_chain = [(name, fn) for name, fn in _STAGES if name in stages_to_run]

    # If starting after extract, load data from previous run output
    if stage_chain and stage_chain[0][0] != "extract":
        data = _load_intermediate_data(code_dir, data)

    # Execute stages sequentially
    for stage_name, stage_fn in stage_chain:
        try:
            data = await stage_fn(data, ctx)
        except StageError as e:
            ctx.add_error(e.code.value, e.message, **{str(k): v for k, v in e.context.items()})
            return _make_result(ctx, start, success=False, data=data)
        except Exception as e:
            ctx.add_error(
                ErrorCode.EXTRACTION_FAILED.value,
                f"Stage '{stage_name}' failed unexpectedly: {e}",
            )
            return _make_result(ctx, start, success=False, data=data)

    ctx.row_count = data.row_count
    result = _make_result(ctx, start, success=True, data=data)

    # Write output
    if output_path or ctx.output_dir:
        _write_result(result, output_path, ctx)

    return result


def _make_result(
    ctx: RunContext,
    start: float,
    *,
    success: bool,
    data: StageData | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a result dict matching PipelineRun shape."""
    duration = time.monotonic() - start
    result: dict[str, Any] = {
        "run_id": ctx.run_id,
        "tenant_id": ctx.tenant_id,
        "pipeline_id": ctx.pipeline_id,
        "status": "completed" if success else "failed",
        "success": success,
        "row_count": data.row_count if data else 0,
        "errors": ctx.errors,
        "warnings": ctx.warnings,
        "duration_seconds": round(duration, 2),
        "started_at": ctx.started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    if data:
        result["data"] = data.rows
        result["stage_metadata"] = data.stage_metadata
        result["grounding"] = data.grounding
    if error:
        ctx.add_error(ErrorCode.EXTRACTION_FAILED.value, error)
        result["errors"] = ctx.errors
    return result


def _write_result(
    result: dict[str, Any],
    output_path: Path | None,
    ctx: RunContext,
) -> None:
    """Write result JSON to disk."""
    # Don't include raw data in the result file (it's in data.json from Load stage)
    result_copy = {k: v for k, v in result.items() if k != "data"}

    if output_path:
        path = output_path if output_path.suffix == ".json" else output_path / "results.json"
    elif ctx.output_dir:
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        path = ctx.output_dir / "results.json"
    else:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result_copy, indent=2, default=str), encoding="utf-8")


def _load_intermediate_data(code_dir: Path, data: StageData) -> StageData:
    """Load data from a previous extract run when starting mid-pipeline."""
    # Look for the most recent run output
    runs_dir = code_dir / "runs"
    if not runs_dir.exists():
        return data

    run_dirs = sorted(runs_dir.iterdir(), reverse=True)
    for run_dir in run_dirs:
        data_file = run_dir / "data.json"
        if data_file.exists():
            loaded = json.loads(data_file.read_text())
            if isinstance(loaded, dict) and "data" in loaded:
                data.rows = loaded["data"]
            elif isinstance(loaded, list):
                data.rows = loaded
            return data

    return data
