"""Shared test fixtures for forum_pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData


@pytest.fixture
def sample_schema() -> dict[str, Any]:
    return {
        "columns": [
            {"name": "product", "type": "STRING", "nullable": False},
            {"name": "price", "type": "FLOAT", "nullable": False, "constraints": {"min": 0}},
            {"name": "stock", "type": "STRING", "nullable": True},
        ],
        "primary_key": ["product"],
        "dedup_key": ["product"],
    }


@pytest.fixture
def sample_rows() -> list[dict[str, Any]]:
    return [
        {"product": "Widget A", "price": 9.99, "stock": "In Stock"},
        {"product": "Widget B", "price": 14.99, "stock": "Low Stock"},
        {"product": "Gadget C", "price": 24.99, "stock": None},
    ]


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "source_url": "https://example.com/data",
        "navigation_mode": "SINGLE_PAGE",
        "stealth_level": "basic",
    }


@pytest.fixture
def stage_data(
    sample_rows: list[dict[str, Any]],
    sample_schema: dict[str, Any],
    sample_config: dict[str, Any],
) -> StageData:
    return StageData(rows=sample_rows, schema=sample_schema, config=sample_config)


@pytest.fixture
def run_context(tmp_path: Path) -> RunContext:
    return RunContext(
        code_dir=tmp_path,
        tenant_id="test-tenant",
        pipeline_id="test-pipeline",
    )


@pytest.fixture
def code_dir(tmp_path: Path, sample_schema: dict[str, Any], sample_config: dict[str, Any]) -> Path:
    """Create a minimal code directory with config and schema."""
    (tmp_path / "config.json").write_text(json.dumps(sample_config))
    (tmp_path / "schema.json").write_text(json.dumps(sample_schema))
    (tmp_path / "extract.py").write_text(
        'SELECTORS = {"product": "td.name", "price": "td.price", "stock": "td.stock"}\n'
        "async def extract(page):\n"
        '    return [{"product": "Test", "price": "9.99", "stock": "In Stock"}]\n'
    )
    return tmp_path
