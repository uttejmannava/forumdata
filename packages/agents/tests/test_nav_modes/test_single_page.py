"""Tests for single page navigation mode."""

from __future__ import annotations

from forum_agents.nav_modes.single_page import SetupResult


def test_setup_result_defaults() -> None:
    r = SetupResult(success=False)
    assert r.search is None
    assert r.navigation is None
    assert r.extraction is None
    assert r.errors == []
