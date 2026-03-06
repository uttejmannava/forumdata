"""Transform stage — apply pre-built and custom transform rules to cleaned data.

Pre-built transforms for trading data:
- normalize_dates: parse various date formats into ISO 8601
- cast_types: coerce values to schema-defined types (str->float, str->int, etc.)
- strip_currency: remove currency symbols and thousand separators from numeric fields
- deduplicate: remove duplicate rows (if not already handled by Cleanse)
"""

from __future__ import annotations

from typing import Any

from forum_pipeline.context import RunContext
from forum_pipeline.stage_data import StageData
from forum_pipeline.transforms import registry


async def run_transform(data: StageData, ctx: RunContext) -> StageData:
    """Execute the Transform stage.

    Reads transform rules from config and applies them in order.
    Always applies cast_types as the final transform to match schema types.
    """
    if not data.rows:
        return data

    transform_rules: list[dict[str, Any]] = data.config.get("transforms", [])
    transforms_applied: list[str] = []

    # Apply configured transforms in order
    for rule in transform_rules:
        name = rule.get("name", "")
        params = rule.get("params", {})
        transform_fn = registry.get_transform(name)
        if transform_fn is not None:
            data.rows = transform_fn(data.rows, data.schema, **params)
            transforms_applied.append(name)

    # Always apply type casting as final step to match schema types
    columns = data.schema.get("columns", [])
    if columns:
        cast_fn = registry.get_transform("cast_types")
        if cast_fn is not None:
            data.rows = cast_fn(data.rows, data.schema)
            if "cast_types" not in transforms_applied:
                transforms_applied.append("cast_types")

    data.stage_metadata["transform"] = {
        "transforms_applied": transforms_applied,
        "row_count": len(data.rows),
    }

    return data
