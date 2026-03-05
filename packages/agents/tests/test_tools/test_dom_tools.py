"""Tests for DOM analysis tools.

Async tools that call page.evaluate are tested with mocked Playwright Page.
The pure-Python _walk_a11y helper is tested directly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from forum_agents.tools.dom import (
    _walk_a11y,
    extract_text,
    find_elements,
    get_accessibility_tree,
    get_page_structure,
    get_tables,
)


@pytest.fixture
def mock_page() -> MagicMock:
    page = AsyncMock()
    return page


# --- _walk_a11y (pure Python helper) ---

def test_walk_a11y_simple_tree() -> None:
    tree = {
        "role": "main",
        "name": "Main content",
        "children": [
            {"role": "heading", "name": "Title", "children": []},
            {"role": "link", "name": "Click me", "children": []},
        ],
    }
    lines: list[str] = []
    _walk_a11y(tree, lines, depth=0, max_depth=5)
    assert len(lines) == 3
    assert "[main]" in lines[0]
    assert '"Main content"' in lines[0]
    assert "[heading]" in lines[1]
    assert "[link]" in lines[2]


def test_walk_a11y_depth_limit() -> None:
    tree = {
        "role": "main",
        "name": "",
        "children": [
            {
                "role": "list",
                "name": "",
                "children": [
                    {"role": "listitem", "name": "Item", "children": []},
                ],
            },
        ],
    }
    lines: list[str] = []
    _walk_a11y(tree, lines, depth=0, max_depth=1)
    assert any("[main]" in line for line in lines)
    assert any("[list]" in line for line in lines)
    # listitem is at depth 2, exceeding max_depth=1
    assert not any("[listitem]" in line for line in lines)


def test_walk_a11y_skips_empty_nodes() -> None:
    tree = {
        "role": "",
        "name": "",
        "children": [
            {"role": "button", "name": "Submit", "children": []},
        ],
    }
    lines: list[str] = []
    _walk_a11y(tree, lines, depth=0, max_depth=5)
    # The empty root is skipped, only the button appears
    assert len(lines) == 1
    assert "[button]" in lines[0]


def test_walk_a11y_truncates_long_names() -> None:
    tree = {"role": "link", "name": "A" * 200, "children": []}
    lines: list[str] = []
    _walk_a11y(tree, lines, depth=0, max_depth=5)
    assert len(lines) == 1
    # Name should be truncated to 80 chars
    assert '"' + "A" * 80 + '"' in lines[0]


def test_walk_a11y_indentation() -> None:
    tree = {
        "role": "navigation",
        "name": "",
        "children": [
            {"role": "link", "name": "Home", "children": []},
        ],
    }
    lines: list[str] = []
    _walk_a11y(tree, lines, depth=0, max_depth=5)
    assert lines[0].startswith("[navigation]")
    assert lines[1].startswith("  [link]")


# --- get_accessibility_tree ---

@pytest.mark.asyncio
async def test_get_accessibility_tree_success(mock_page: MagicMock) -> None:
    mock_page.evaluate.return_value = {
        "role": "main",
        "name": "",
        "children": [
            {"role": "heading", "name": "Products", "children": []},
        ],
    }

    result = await get_accessibility_tree(mock_page, max_depth=3)
    assert result.success
    assert "heading" in result.data["tree"]
    assert result.data["node_count"] >= 1


@pytest.mark.asyncio
async def test_get_accessibility_tree_empty(mock_page: MagicMock) -> None:
    mock_page.evaluate.return_value = None

    result = await get_accessibility_tree(mock_page)
    assert result.success
    assert result.data["tree"] == "(empty page)"
    assert result.data["node_count"] == 0


@pytest.mark.asyncio
async def test_get_accessibility_tree_error(mock_page: MagicMock) -> None:
    mock_page.evaluate.side_effect = Exception("Page crashed")

    result = await get_accessibility_tree(mock_page)
    assert not result.success
    assert result.error is not None


# --- extract_text ---

@pytest.mark.asyncio
async def test_extract_text_success(mock_page: MagicMock) -> None:
    mock_page.text_content.return_value = "Hello World"

    result = await extract_text(mock_page, "h1")
    assert result.success
    assert result.data["text"] == "Hello World"
    assert result.data["selector"] == "h1"


@pytest.mark.asyncio
async def test_extract_text_empty(mock_page: MagicMock) -> None:
    mock_page.text_content.return_value = None

    result = await extract_text(mock_page, ".empty")
    assert result.success
    assert result.data["text"] == ""


@pytest.mark.asyncio
async def test_extract_text_error(mock_page: MagicMock) -> None:
    mock_page.text_content.side_effect = Exception("Timeout")

    result = await extract_text(mock_page, ".missing")
    assert not result.success


# --- find_elements ---

@pytest.mark.asyncio
async def test_find_elements_success(mock_page: MagicMock) -> None:
    el1 = AsyncMock()
    el1.evaluate.side_effect = [
        "tr",  # tag
        {"class": "row", "id": "r1"},  # attrs
    ]
    el1.text_content.return_value = "Row 1 content"

    el2 = AsyncMock()
    el2.evaluate.side_effect = [
        "tr",
        {"class": "row", "id": "r2"},
    ]
    el2.text_content.return_value = "Row 2 content"

    mock_page.query_selector_all.return_value = [el1, el2]

    result = await find_elements(mock_page, "table tr")
    assert result.success
    assert result.data["count"] == 2
    assert len(result.data["elements"]) == 2
    assert result.data["elements"][0]["tag"] == "tr"


@pytest.mark.asyncio
async def test_find_elements_empty(mock_page: MagicMock) -> None:
    mock_page.query_selector_all.return_value = []

    result = await find_elements(mock_page, ".nonexistent")
    assert result.success
    assert result.data["count"] == 0


@pytest.mark.asyncio
async def test_find_elements_error(mock_page: MagicMock) -> None:
    mock_page.query_selector_all.side_effect = Exception("Invalid selector")

    result = await find_elements(mock_page, ">>>bad")
    assert not result.success


# --- get_page_structure ---

@pytest.mark.asyncio
async def test_get_page_structure_success(mock_page: MagicMock) -> None:
    skeleton = "<body>\n  <div#main>\n    <table.data>\n"
    mock_page.evaluate.return_value = skeleton

    result = await get_page_structure(mock_page)
    assert result.success
    assert result.data["skeleton"] == skeleton
    assert result.data["length"] == len(skeleton)


@pytest.mark.asyncio
async def test_get_page_structure_error(mock_page: MagicMock) -> None:
    mock_page.evaluate.side_effect = Exception("Detached")

    result = await get_page_structure(mock_page)
    assert not result.success


# --- get_tables ---

@pytest.mark.asyncio
async def test_get_tables_success(mock_page: MagicMock) -> None:
    mock_page.evaluate.return_value = [
        {
            "index": 0,
            "headers": ["Name", "Price"],
            "row_count": 3,
            "sample_rows": [["Widget", "9.99"], ["Gadget", "19.99"]],
            "id": "price-table",
            "classes": "data-table",
        },
    ]

    result = await get_tables(mock_page)
    assert result.success
    assert result.data["count"] == 1
    assert result.data["tables"][0]["headers"] == ["Name", "Price"]
    assert result.data["tables"][0]["row_count"] == 3


@pytest.mark.asyncio
async def test_get_tables_empty(mock_page: MagicMock) -> None:
    mock_page.evaluate.return_value = []

    result = await get_tables(mock_page)
    assert result.success
    assert result.data["count"] == 0


@pytest.mark.asyncio
async def test_get_tables_error(mock_page: MagicMock) -> None:
    mock_page.evaluate.side_effect = Exception("JS error")

    result = await get_tables(mock_page)
    assert not result.success
