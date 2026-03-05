"""Tests for browser action tools.

These tests mock the Playwright Page object to verify tool wrappers
return correct ToolResult structures without needing a real browser.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from forum_agents.tools.browser import (
    ToolResult,
    click,
    get_page_content,
    get_page_url,
    navigate,
    screenshot,
    scroll_down,
    type_text,
)


@pytest.fixture
def mock_page() -> MagicMock:
    """Create a mock Playwright Page."""
    page = AsyncMock()
    page.url = "https://example.com/data"
    return page


@pytest.mark.asyncio
async def test_navigate_success(mock_page: MagicMock) -> None:
    response = AsyncMock()
    response.status = 200
    mock_page.goto.return_value = response

    result = await navigate(mock_page, "https://example.com/data")
    assert result.success
    assert result.data["status"] == 200
    mock_page.goto.assert_awaited_once()


@pytest.mark.asyncio
async def test_navigate_4xx(mock_page: MagicMock) -> None:
    response = AsyncMock()
    response.status = 404
    mock_page.goto.return_value = response

    result = await navigate(mock_page, "https://example.com/missing")
    assert not result.success
    assert result.data["status"] == 404


@pytest.mark.asyncio
async def test_navigate_exception(mock_page: MagicMock) -> None:
    mock_page.goto.side_effect = TimeoutError("Navigation timeout")

    result = await navigate(mock_page, "https://example.com/slow")
    assert not result.success
    assert "timeout" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_navigate_none_response(mock_page: MagicMock) -> None:
    mock_page.goto.return_value = None

    result = await navigate(mock_page, "https://example.com")
    assert not result.success
    assert result.data["status"] is None


@pytest.mark.asyncio
async def test_click_success(mock_page: MagicMock) -> None:
    result = await click(mock_page, "button.submit")
    assert result.success
    assert result.data["selector"] == "button.submit"
    mock_page.click.assert_awaited_once_with("button.submit", timeout=5000)


@pytest.mark.asyncio
async def test_click_failure(mock_page: MagicMock) -> None:
    mock_page.click.side_effect = Exception("Element not found")

    result = await click(mock_page, "button.missing")
    assert not result.success
    assert result.error is not None


@pytest.mark.asyncio
async def test_type_text_success(mock_page: MagicMock) -> None:
    result = await type_text(mock_page, "input#search", "test query")
    assert result.success
    assert result.data["text"] == "test query"
    mock_page.fill.assert_awaited_once_with("input#search", "test query", timeout=5000)


@pytest.mark.asyncio
async def test_type_text_failure(mock_page: MagicMock) -> None:
    mock_page.fill.side_effect = Exception("Input not found")

    result = await type_text(mock_page, "input#missing", "text")
    assert not result.success


@pytest.mark.asyncio
async def test_scroll_down_success(mock_page: MagicMock) -> None:
    mock_page.evaluate.side_effect = [None, 500]

    result = await scroll_down(mock_page, pixels=500)
    assert result.success
    assert result.data["scroll_y"] == 500
    assert result.data["pixels"] == 500


@pytest.mark.asyncio
async def test_scroll_down_default_pixels(mock_page: MagicMock) -> None:
    mock_page.evaluate.side_effect = [None, 500]

    result = await scroll_down(mock_page)
    assert result.success
    mock_page.evaluate.assert_any_await("window.scrollBy(0, 500)")


@pytest.mark.asyncio
async def test_screenshot_to_memory(mock_page: MagicMock) -> None:
    mock_page.screenshot.return_value = b"\x89PNG\r\nfake"

    result = await screenshot(mock_page)
    assert result.success
    assert result.data["size_bytes"] == len(b"\x89PNG\r\nfake")
    assert result.data["base64"] is not None
    assert result.data["path"] is None


@pytest.mark.asyncio
async def test_screenshot_to_file(mock_page: MagicMock) -> None:
    mock_page.screenshot.return_value = b"\x89PNG\r\nfake"

    result = await screenshot(mock_page, path="/tmp/test.png")
    assert result.success
    assert result.data["path"] == "/tmp/test.png"
    assert result.data["base64"] is None


@pytest.mark.asyncio
async def test_screenshot_failure(mock_page: MagicMock) -> None:
    mock_page.screenshot.side_effect = Exception("Page crashed")

    result = await screenshot(mock_page)
    assert not result.success


@pytest.mark.asyncio
async def test_get_page_content_success(mock_page: MagicMock) -> None:
    mock_page.content.return_value = "<html><body>Hello</body></html>"

    result = await get_page_content(mock_page)
    assert result.success
    assert "Hello" in result.data["html"]
    assert result.data["length"] == len("<html><body>Hello</body></html>")


@pytest.mark.asyncio
async def test_get_page_content_failure(mock_page: MagicMock) -> None:
    mock_page.content.side_effect = Exception("Detached")

    result = await get_page_content(mock_page)
    assert not result.success


@pytest.mark.asyncio
async def test_get_page_url(mock_page: MagicMock) -> None:
    result = await get_page_url(mock_page)
    assert result.success
    assert result.data["url"] == "https://example.com/data"


def test_tool_result_defaults() -> None:
    r = ToolResult(success=True, data={"key": "val"})
    assert r.error is None

    r2 = ToolResult(success=False, data={}, error="boom")
    assert r2.error == "boom"
