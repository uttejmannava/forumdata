"""Tests for the Transform stage."""

from __future__ import annotations

from typing import Any

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData
from forum_pipeline.stages.transform import run_transform
from forum_pipeline.transforms.builtins import cast_types, normalize_dates, strip_currency, deduplicate


@pytest.fixture
def ctx(tmp_path):
    return RunContext(code_dir=tmp_path)


@pytest.fixture
def schema() -> dict[str, Any]:
    return {
        "columns": [
            {"name": "product", "type": "STRING", "nullable": False},
            {"name": "price", "type": "FLOAT", "nullable": False},
            {"name": "quantity", "type": "INTEGER", "nullable": True},
        ],
        "primary_key": ["product"],
    }


def test_cast_types_float(schema: dict[str, Any]) -> None:
    rows = [{"product": "A", "price": "9.99", "quantity": "5"}]
    result = cast_types(rows, schema)
    assert result[0]["price"] == 9.99
    assert result[0]["quantity"] == 5


def test_cast_types_comma_numbers(schema: dict[str, Any]) -> None:
    rows = [{"product": "A", "price": "1,234.56", "quantity": "1,000"}]
    result = cast_types(rows, schema)
    assert result[0]["price"] == 1234.56
    assert result[0]["quantity"] == 1000


def test_cast_types_preserves_none(schema: dict[str, Any]) -> None:
    rows = [{"product": "A", "price": 1.0, "quantity": None}]
    result = cast_types(rows, schema)
    assert result[0]["quantity"] is None


def test_strip_currency(schema: dict[str, Any]) -> None:
    rows = [{"product": "A", "price": "$9.99", "quantity": "5"}]
    result = strip_currency(rows, schema)
    assert result[0]["price"] == "9.99"


def test_strip_currency_euro() -> None:
    schema = {"columns": [{"name": "price", "type": "FLOAT"}]}
    rows = [{"price": "\u20ac1,234.56"}]
    result = strip_currency(rows, schema)
    assert result[0]["price"] == "1234.56"


def test_normalize_dates() -> None:
    schema = {"columns": [{"name": "date", "type": "DATE"}]}
    rows = [
        {"date": "March 15, 2025"},
        {"date": "03/15/2025"},
        {"date": "2025-03-15"},
    ]
    result = normalize_dates(rows, schema)
    assert result[0]["date"] == "2025-03-15"
    assert result[1]["date"] == "2025-03-15"
    assert result[2]["date"] == "2025-03-15"


def test_normalize_dates_unknown_format() -> None:
    schema = {"columns": [{"name": "date", "type": "DATE"}]}
    rows = [{"date": "not-a-date"}]
    result = normalize_dates(rows, schema)
    assert result[0]["date"] == "not-a-date"


def test_deduplicate_by_primary_key() -> None:
    schema = {"primary_key": ["id"]}
    rows = [{"id": 1, "v": "a"}, {"id": 1, "v": "b"}, {"id": 2, "v": "c"}]
    result = deduplicate(rows, schema)
    assert len(result) == 2
    assert result[0]["v"] == "a"


def test_deduplicate_full_row() -> None:
    rows = [{"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 1, "b": 3}]
    result = deduplicate(rows, {})
    assert len(result) == 2


def test_transform_registry() -> None:
    from forum_pipeline.transforms.registry import get_transform
    assert get_transform("cast_types") is not None
    assert get_transform("strip_currency") is not None
    assert get_transform("normalize_dates") is not None
    assert get_transform("deduplicate") is not None
    assert get_transform("nonexistent") is None


async def test_run_transform_applies_config(ctx: RunContext, schema: dict[str, Any]) -> None:
    data = StageData(
        rows=[{"product": "A", "price": "$9.99", "quantity": "5"}],
        schema=schema,
        config={
            "transforms": [
                {"name": "strip_currency"},
            ]
        },
    )
    result = await run_transform(data, ctx)
    # strip_currency + auto cast_types
    assert result.rows[0]["price"] == 9.99
    assert result.rows[0]["quantity"] == 5
    assert "cast_types" in result.stage_metadata["transform"]["transforms_applied"]


async def test_run_transform_empty_rows(ctx: RunContext) -> None:
    data = StageData(rows=[], schema={}, config={})
    result = await run_transform(data, ctx)
    assert result.rows == []
