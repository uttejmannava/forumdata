"""Tests for the extract stage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forum_pipeline.stages.extract import (
    load_extract_module,
    load_navigate_module,
    validate_output,
)


def test_load_extract_module(tmp_path: Path) -> None:
    extract_code = '''
SELECTORS = {"name": "td"}

async def extract(page):
    return [{"name": "Widget"}]
'''
    (tmp_path / "extract.py").write_text(extract_code)
    mod = load_extract_module(tmp_path)
    assert hasattr(mod, "extract")
    assert hasattr(mod, "SELECTORS")
    assert mod.SELECTORS == {"name": "td"}


def test_load_extract_module_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_extract_module(tmp_path)


def test_load_navigate_module_exists(tmp_path: Path) -> None:
    nav_code = '''
async def navigate(page, config):
    return ["<html></html>"]
'''
    (tmp_path / "navigate.py").write_text(nav_code)
    mod = load_navigate_module(tmp_path)
    assert mod is not None
    assert hasattr(mod, "navigate")


def test_load_navigate_module_missing(tmp_path: Path) -> None:
    mod = load_navigate_module(tmp_path)
    assert mod is None


def test_validate_output_pass(tmp_path: Path) -> None:
    schema = {
        "columns": [
            {"name": "price", "type": "float", "nullable": True},
        ]
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))

    data = [{"price": "9.99"}, {"price": None}]
    valid, errors = validate_output(data, schema_path)
    assert valid
    assert errors == []


def test_validate_output_fail(tmp_path: Path) -> None:
    schema = {
        "columns": [
            {"name": "price", "type": "float", "nullable": False},
        ]
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))

    data = [{"price": None}]
    valid, errors = validate_output(data, schema_path)
    assert not valid
    assert len(errors) == 1


def test_validate_output_no_schema(tmp_path: Path) -> None:
    valid, errors = validate_output([{"x": 1}], tmp_path / "nonexistent.json")
    assert valid
    assert errors == []
