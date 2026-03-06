"""Tests for the extract stage module loading."""

from __future__ import annotations

from pathlib import Path

from forum_pipeline.stages.extract import _load_module


def test_load_module_exists(tmp_path: Path) -> None:
    extract_code = '''
SELECTORS = {"name": "td"}

async def extract(page):
    return [{"name": "Widget"}]
'''
    (tmp_path / "extract.py").write_text(extract_code)
    mod = _load_module(tmp_path, "extract")
    assert mod is not None
    assert hasattr(mod, "extract")
    assert hasattr(mod, "SELECTORS")
    assert mod.SELECTORS == {"name": "td"}


def test_load_module_missing(tmp_path: Path) -> None:
    mod = _load_module(tmp_path, "extract")
    assert mod is None


def test_load_navigate_module_exists(tmp_path: Path) -> None:
    nav_code = '''
async def navigate(page, config):
    return ["<html></html>"]
'''
    (tmp_path / "navigate.py").write_text(nav_code)
    mod = _load_module(tmp_path, "navigate")
    assert mod is not None
    assert hasattr(mod, "navigate")


def test_load_navigate_module_missing(tmp_path: Path) -> None:
    mod = _load_module(tmp_path, "navigate")
    assert mod is None
