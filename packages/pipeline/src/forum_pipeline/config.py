"""Load pipeline config and schema from code directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forum_schemas.models.pipeline import NavigationMode, StealthLevel


def load_config(code_dir: Path) -> dict[str, Any]:
    """Load and validate config.json from code directory."""
    config_path = code_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"No config.json found in {code_dir}")
    config = json.loads(config_path.read_text())
    if not config.get("source_url"):
        raise ValueError("config.json must contain 'source_url'")
    return config


def load_schema(code_dir: Path) -> dict[str, Any]:
    """Load schema.json from code directory. Returns empty dict if not found."""
    schema_path = code_dir / "schema.json"
    if not schema_path.exists():
        return {}
    return json.loads(schema_path.read_text())


def get_stealth_level(config: dict[str, Any]) -> StealthLevel:
    """Parse stealth level from config, defaulting to BASIC."""
    raw = config.get("stealth_level", "basic")
    try:
        return StealthLevel(raw.lower() if isinstance(raw, str) else raw)
    except ValueError:
        return StealthLevel.BASIC


def get_navigation_mode(config: dict[str, Any]) -> NavigationMode:
    """Parse navigation mode from config."""
    raw = config.get("navigation_mode", "SINGLE_PAGE")
    try:
        return NavigationMode(raw.lower() if isinstance(raw, str) else raw)
    except ValueError:
        return NavigationMode.SINGLE_PAGE
