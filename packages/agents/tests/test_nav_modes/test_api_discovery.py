"""Tests for API discovery navigation mode."""

from __future__ import annotations

from forum_agents.nav_modes.api_discovery import _pick_best_candidate


def test_pick_best_candidate_json_preferred() -> None:
    candidates = [
        {"url": "https://example.com/page", "response_content_type": "text/html"},
        {"url": "https://example.com/api/data", "response_content_type": "application/json"},
    ]
    best = _pick_best_candidate(candidates)
    assert best is not None
    assert best["url"] == "https://example.com/api/data"


def test_pick_best_candidate_fallback() -> None:
    candidates = [
        {"url": "https://example.com/page", "response_content_type": "text/html"},
    ]
    best = _pick_best_candidate(candidates)
    assert best is not None
    assert best["url"] == "https://example.com/page"


def test_pick_best_candidate_empty() -> None:
    assert _pick_best_candidate([]) is None
