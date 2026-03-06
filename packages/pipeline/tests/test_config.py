"""Tests for config loading utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forum_pipeline.config import get_navigation_mode, get_stealth_level, load_config, load_schema
from forum_schemas.models.pipeline import NavigationMode, StealthLevel


def test_load_config(tmp_path: Path) -> None:
    config = {"source_url": "https://example.com", "stealth_level": "basic"}
    (tmp_path / "config.json").write_text(json.dumps(config))
    result = load_config(tmp_path)
    assert result["source_url"] == "https://example.com"


def test_load_config_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path)


def test_load_config_no_url(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"stealth_level": "basic"}))
    with pytest.raises(ValueError, match="source_url"):
        load_config(tmp_path)


def test_load_schema(tmp_path: Path) -> None:
    schema = {"columns": [{"name": "x", "type": "STRING"}]}
    (tmp_path / "schema.json").write_text(json.dumps(schema))
    result = load_schema(tmp_path)
    assert result["columns"][0]["name"] == "x"


def test_load_schema_missing(tmp_path: Path) -> None:
    result = load_schema(tmp_path)
    assert result == {}


def test_get_stealth_level_valid() -> None:
    assert get_stealth_level({"stealth_level": "basic"}) == StealthLevel.BASIC
    assert get_stealth_level({"stealth_level": "aggressive"}) == StealthLevel.AGGRESSIVE


def test_get_stealth_level_default() -> None:
    assert get_stealth_level({}) == StealthLevel.BASIC


def test_get_stealth_level_invalid() -> None:
    assert get_stealth_level({"stealth_level": "invalid"}) == StealthLevel.BASIC


def test_get_navigation_mode_valid() -> None:
    assert get_navigation_mode({"navigation_mode": "single_page"}) == NavigationMode.SINGLE_PAGE
    assert get_navigation_mode({"navigation_mode": "paginated_list"}) == NavigationMode.PAGINATED_LIST


def test_get_navigation_mode_default() -> None:
    assert get_navigation_mode({}) == NavigationMode.SINGLE_PAGE


def test_get_navigation_mode_invalid() -> None:
    assert get_navigation_mode({"navigation_mode": "bad"}) == NavigationMode.SINGLE_PAGE
