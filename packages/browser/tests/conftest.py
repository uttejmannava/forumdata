"""Shared test fixtures for forum-browser tests."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest

from forum_browser.browser import BrowserConfig, ForumBrowser
from forum_browser.http import HttpClientConfig, StealthHttpClient
from forum_browser.resolution.storage import SqliteFingerprintStorage
from forum_schemas.models.pipeline import StealthLevel


@pytest.fixture
def browser_config() -> BrowserConfig:
    """Default browser config for testing."""
    return BrowserConfig(stealth_level=StealthLevel.BASIC, headless=True, trace_enabled=False)


@pytest.fixture
async def browser(browser_config: BrowserConfig) -> AsyncGenerator[ForumBrowser, None]:
    """A launched browser instance."""
    async with ForumBrowser(browser_config) as b:
        yield b


@pytest.fixture
def http_config() -> HttpClientConfig:
    """Default HTTP client config for testing."""
    return HttpClientConfig()


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_storage(tmp_path: Path) -> SqliteFingerprintStorage:
    """Temporary SQLite fingerprint storage."""
    return SqliteFingerprintStorage(db_path=tmp_path / "fingerprints.db")


@pytest.fixture
def simple_table_html() -> str:
    """Simple HTML table for testing element resolution."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Settlement Prices</h1>
        <table id="settlements">
            <thead><tr><th>Contract</th><th>Price</th><th>Volume</th></tr></thead>
            <tbody>
                <tr class="row"><td>CLZ25</td><td class="price">72.45</td><td>15234</td></tr>
                <tr class="row"><td>CLF26</td><td class="price">73.10</td><td>8921</td></tr>
                <tr class="row"><td>CLG26</td><td class="price">73.55</td><td>4512</td></tr>
            </tbody>
        </table>
    </body>
    </html>
    """
