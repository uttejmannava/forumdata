"""Tests for element resolution tools.

These tests mock the forum_browser.resolution functions to verify
the tool wrappers return correct ToolResult structures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forum_agents.tools.element import (
    adaptive_match,
    save_fingerprint,
    tool_find_by_regex,
    tool_find_by_text,
    tool_find_similar,
    tool_generate_selector,
)


@pytest.fixture
def mock_page() -> MagicMock:
    return AsyncMock()


@pytest.fixture
def mock_storage() -> MagicMock:
    storage = AsyncMock()
    return storage


# --- tool_find_by_text ---

@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_text")
async def test_find_by_text_success(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = ["h1.title", "span.name"]

    result = await tool_find_by_text(mock_page, "Product Name")
    assert result.success
    assert result.data["count"] == 2
    assert result.data["selectors"] == ["h1.title", "span.name"]
    mock_fn.assert_awaited_once_with(mock_page, "Product Name", exact=False, case_sensitive=False)


@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_text")
async def test_find_by_text_exact(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = ["h1.title"]

    result = await tool_find_by_text(mock_page, "Exact", exact=True, case_sensitive=True)
    assert result.success
    mock_fn.assert_awaited_once_with(mock_page, "Exact", exact=True, case_sensitive=True)


@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_text")
async def test_find_by_text_empty(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = []

    result = await tool_find_by_text(mock_page, "nonexistent")
    assert result.success
    assert result.data["count"] == 0


@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_text")
async def test_find_by_text_error(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.side_effect = Exception("Page detached")

    result = await tool_find_by_text(mock_page, "text")
    assert not result.success
    assert "detached" in (result.error or "").lower()


# --- tool_find_by_regex ---

@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_regex")
async def test_find_by_regex_success(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = ["td.price"]

    result = await tool_find_by_regex(mock_page, r"\$\d+\.\d{2}")
    assert result.success
    assert result.data["count"] == 1


@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_regex")
async def test_find_by_regex_error(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.side_effect = Exception("Invalid regex")

    result = await tool_find_by_regex(mock_page, "[bad")
    assert not result.success


# --- tool_find_similar ---

@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_similar")
async def test_find_similar_success(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = ["tr:nth-child(2)", "tr:nth-child(3)"]

    result = await tool_find_similar(mock_page, "tr:nth-child(1)", threshold=0.8)
    assert result.success
    assert result.data["count"] == 2
    mock_fn.assert_awaited_once_with(mock_page, "tr:nth-child(1)", threshold=0.8)


@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_similar")
async def test_find_similar_error(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.side_effect = Exception("No reference element")

    result = await tool_find_similar(mock_page, ".missing")
    assert not result.success


# --- tool_generate_selector ---

@pytest.mark.asyncio
@patch("forum_agents.tools.element.generate_selector")
async def test_generate_selector_found(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = "table#prices tbody tr"

    result = await tool_generate_selector(mock_page, "rows in the prices table")
    assert result.success
    assert result.data["selector"] == "table#prices tbody tr"


@pytest.mark.asyncio
@patch("forum_agents.tools.element.generate_selector")
async def test_generate_selector_not_found(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.return_value = None

    result = await tool_generate_selector(mock_page, "nonexistent widget")
    assert not result.success
    assert result.error is not None


@pytest.mark.asyncio
@patch("forum_agents.tools.element.generate_selector")
async def test_generate_selector_error(mock_fn: AsyncMock, mock_page: MagicMock) -> None:
    mock_fn.side_effect = Exception("Eval failed")

    result = await tool_generate_selector(mock_page, "something")
    assert not result.success


# --- save_fingerprint ---

@pytest.mark.asyncio
@patch("forum_agents.tools.element.capture_fingerprint")
async def test_save_fingerprint_success(
    mock_capture: AsyncMock, mock_page: MagicMock, mock_storage: MagicMock
) -> None:
    fingerprint = MagicMock()
    fingerprint.tag_name = "td"
    mock_capture.return_value = fingerprint

    result = await save_fingerprint(
        mock_page, "td.price", "price_field", mock_storage, "tenant1", "pipe1"
    )
    assert result.success
    assert result.data["identifier"] == "price_field"
    assert result.data["tag_name"] == "td"
    mock_storage.save.assert_awaited_once_with("tenant1", "pipe1", "price_field", fingerprint)


@pytest.mark.asyncio
@patch("forum_agents.tools.element.capture_fingerprint")
async def test_save_fingerprint_error(
    mock_capture: AsyncMock, mock_page: MagicMock, mock_storage: MagicMock
) -> None:
    mock_capture.side_effect = Exception("Element not found")

    result = await save_fingerprint(
        mock_page, ".missing", "ident", mock_storage, "t", "p"
    )
    assert not result.success


# --- adaptive_match ---

@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_fingerprint")
async def test_adaptive_match_success(
    mock_find: AsyncMock, mock_page: MagicMock, mock_storage: MagicMock
) -> None:
    fingerprint = MagicMock()
    mock_storage.load.return_value = fingerprint
    mock_find.return_value = [("td.price", 0.95), ("td.amount", 0.72)]

    result = await adaptive_match(mock_page, "price_field", mock_storage, "t1", "p1")
    assert result.success
    assert len(result.data["matches"]) == 2
    assert result.data["matches"][0]["score"] == 0.95


@pytest.mark.asyncio
async def test_adaptive_match_no_fingerprint(
    mock_page: MagicMock, mock_storage: MagicMock
) -> None:
    mock_storage.load.return_value = None

    result = await adaptive_match(mock_page, "unknown", mock_storage, "t1", "p1")
    assert not result.success
    assert "No stored fingerprint" in (result.error or "")


@pytest.mark.asyncio
@patch("forum_agents.tools.element.find_by_fingerprint")
async def test_adaptive_match_no_matches(
    mock_find: AsyncMock, mock_page: MagicMock, mock_storage: MagicMock
) -> None:
    mock_storage.load.return_value = MagicMock()
    mock_find.return_value = []

    result = await adaptive_match(mock_page, "stale", mock_storage, "t1", "p1")
    assert not result.success
    assert result.data["matches"] == []
