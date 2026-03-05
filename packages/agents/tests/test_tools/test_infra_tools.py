"""Tests for infrastructure/artifact storage tools."""

from __future__ import annotations

import json
from pathlib import Path

from forum_agents.tools.infra import save_code_artifact, save_config, save_metadata, save_schema


def test_save_code_artifact(tmp_path: Path) -> None:
    code = "async def extract(page):\n    return []\n"
    result = save_code_artifact(code, tmp_path / "extract.py")
    assert result.success
    assert (tmp_path / "extract.py").read_text() == code


def test_save_schema(tmp_path: Path) -> None:
    schema = {"columns": [{"name": "price", "type": "float"}]}
    result = save_schema(schema, tmp_path / "schema.json")
    assert result.success
    loaded = json.loads((tmp_path / "schema.json").read_text())
    assert loaded["columns"][0]["name"] == "price"


def test_save_config(tmp_path: Path) -> None:
    config = {"navigation_mode": "single_page", "stealth_level": "none"}
    result = save_config(config, tmp_path / "config.json")
    assert result.success


def test_save_metadata(tmp_path: Path) -> None:
    result = save_metadata(
        tmp_path / "metadata.json",
        navigation_mode="paginated_list",
        stealth_level="basic",
    )
    assert result.success
    loaded = json.loads((tmp_path / "metadata.json").read_text())
    assert loaded["author"] == "system:agent"
    assert loaded["navigation_mode"] == "paginated_list"
    assert loaded["parent"] is None


def test_save_creates_directories(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "dir"
    result = save_code_artifact("code", nested / "file.py")
    assert result.success
    assert (nested / "file.py").exists()
