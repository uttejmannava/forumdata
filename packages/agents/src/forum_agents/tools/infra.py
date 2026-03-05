"""Local filesystem artifact storage tools.

Phase 0: all operations target local filesystem.
Phase 1: extend to write to S3 at tenants/{tenant_id}/pipelines/{pipeline_id}/code/v{n}/.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forum_agents.tools.browser import ToolResult


def save_code_artifact(code: str, path: Path, *, metadata: dict[str, Any] | None = None) -> ToolResult:
    """Write extraction/navigation code to output directory."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        result_data: dict[str, Any] = {"path": str(path), "size_bytes": len(code.encode())}
        if metadata:
            result_data["metadata"] = metadata
        return ToolResult(success=True, data=result_data)
    except Exception as e:
        return ToolResult(success=False, data={"path": str(path)}, error=str(e))


def save_schema(schema: dict[str, Any], path: Path) -> ToolResult:
    """Write schema JSON to output directory."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")
        return ToolResult(success=True, data={"path": str(path), "field_count": len(schema.get("columns", []))})
    except Exception as e:
        return ToolResult(success=False, data={"path": str(path)}, error=str(e))


def save_config(config: dict[str, Any], path: Path) -> ToolResult:
    """Write pipeline config to output directory."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
        return ToolResult(success=True, data={"path": str(path)})
    except Exception as e:
        return ToolResult(success=False, data={"path": str(path)}, error=str(e))


def save_metadata(
    path: Path,
    *,
    navigation_mode: str = "single_page",
    stealth_level: str = "none",
    note: str = "Initial generation",
) -> ToolResult:
    """Write metadata.json in architecture §4 format."""
    try:
        metadata = {
            "author": "system:agent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "note": note,
            "parent": None,
            "navigation_mode": navigation_mode,
            "stealth_level": stealth_level,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return ToolResult(success=True, data={"path": str(path), "metadata": metadata})
    except Exception as e:
        return ToolResult(success=False, data={"path": str(path)}, error=str(e))
