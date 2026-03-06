"""Data container flowing between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageData:
    """Mutable container passed through the E-C-T-V-L-N stage chain."""

    # The rows of extracted/processed data
    rows: list[dict[str, Any]] = field(default_factory=list)

    # Schema loaded from schema.json
    schema: dict[str, Any] = field(default_factory=dict)

    # Pipeline config loaded from config.json
    config: dict[str, Any] = field(default_factory=dict)

    # Per-field source grounding metadata (populated during extract, carried through)
    # Shape: list of {field: str, selector: str, tier: str, confidence: float}
    grounding: list[dict[str, Any]] = field(default_factory=list)

    # Metadata accumulated across stages
    stage_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows)
