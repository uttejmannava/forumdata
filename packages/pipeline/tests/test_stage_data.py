"""Tests for StageData."""

from __future__ import annotations

from forum_pipeline.stage_data import StageData


def test_stage_data_defaults() -> None:
    data = StageData()
    assert data.rows == []
    assert data.schema == {}
    assert data.config == {}
    assert data.grounding == []
    assert data.stage_metadata == {}
    assert data.row_count == 0


def test_stage_data_row_count() -> None:
    data = StageData(rows=[{"a": 1}, {"a": 2}, {"a": 3}])
    assert data.row_count == 3


def test_stage_data_with_values() -> None:
    data = StageData(
        rows=[{"x": 1}],
        schema={"columns": []},
        config={"source_url": "https://example.com"},
    )
    assert data.row_count == 1
    assert data.config["source_url"] == "https://example.com"
