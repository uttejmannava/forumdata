"""Tests for paginated navigation mode."""

from __future__ import annotations

from forum_agents.nav_modes.paginated import setup_paginated_list


def test_paginated_function_exists() -> None:
    """Verify the setup function is importable."""
    assert callable(setup_paginated_list)
