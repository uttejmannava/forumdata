"""Tests for the Cleanse stage."""

from __future__ import annotations

import pytest

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData
from forum_pipeline.stages.cleanse import run_cleanse


@pytest.fixture
def ctx(tmp_path):
    return RunContext(code_dir=tmp_path)


async def test_cleanse_strips_html(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"name": "<b>Widget</b> A", "note": "normal"}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    assert result.rows[0]["name"] == "Widget A"
    assert result.rows[0]["note"] == "normal"


async def test_cleanse_decodes_html_entities(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"name": "A &amp; B &lt;C&gt;"}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    # &lt;C&gt; -> <C> after unescape (not a real HTML tag, just entity-encoded angle brackets)
    assert result.rows[0]["name"] == "A & B <C>"


async def test_cleanse_normalizes_whitespace(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"name": "  Widget   A  "}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    assert result.rows[0]["name"] == "Widget A"


async def test_cleanse_removes_zero_width_chars(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"name": "Wid\u200bget\ufeff"}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    assert result.rows[0]["name"] == "Widget"


async def test_cleanse_extracts_footnote_markers(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"price": "9.99*", "name": "Widget\u2020"}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    assert result.rows[0]["price"] == "9.99"
    assert result.rows[0]["_qualifiers"]["price"] == ["preliminary"]
    assert result.rows[0]["_qualifiers"]["name"] == ["revised"]


async def test_cleanse_dedup_rows(ctx: RunContext) -> None:
    data = StageData(
        rows=[
            {"product": "A", "price": 1.0},
            {"product": "A", "price": 2.0},
            {"product": "B", "price": 3.0},
        ],
        schema={"dedup_key": ["product"]},
        config={},
    )
    result = await run_cleanse(data, ctx)
    assert len(result.rows) == 2
    assert result.rows[0]["product"] == "A"
    assert result.rows[0]["price"] == 1.0  # Keeps first


async def test_cleanse_empty_rows(ctx: RunContext) -> None:
    data = StageData(rows=[], config={})
    result = await run_cleanse(data, ctx)
    assert result.rows == []


async def test_cleanse_non_string_values(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"count": 42, "active": True, "value": None}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    assert result.rows[0]["count"] == 42
    assert result.rows[0]["active"] is True
    assert result.rows[0]["value"] is None


async def test_cleanse_metadata(ctx: RunContext) -> None:
    data = StageData(
        rows=[{"a": "x"}, {"a": "y"}],
        config={},
    )
    result = await run_cleanse(data, ctx)
    meta = result.stage_metadata["cleanse"]
    assert meta["rows_before"] == 2
    assert meta["rows_after"] == 2
    assert meta["rows_deduped"] == 0
