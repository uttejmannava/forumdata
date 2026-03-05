"""Tests for the orchestrator."""

from __future__ import annotations

from forum_agents.orchestrator import PipelineSetupState, build_graph


def test_build_graph() -> None:
    """Verify the graph builds without errors."""
    graph = build_graph()
    app = graph.compile()
    assert app is not None


def test_pipeline_setup_state_shape() -> None:
    """Verify the state TypedDict can be instantiated."""
    state: PipelineSetupState = {
        "source_url": "https://example.com",
        "user_description": "Extract prices",
        "target_schema": None,
        "search_result": None,
        "compliance_result": None,
        "navigation_result": None,
        "extraction_result": None,
        "navigation_mode": "",
        "stealth_level": "",
        "output_dir": "./output",
        "errors": [],
        "status": "starting",
    }
    assert state["source_url"] == "https://example.com"
    assert state["errors"] == []
