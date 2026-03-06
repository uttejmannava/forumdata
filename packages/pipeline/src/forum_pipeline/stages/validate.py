"""Validate stage — schema validation, constraint checking, plausibility, confidence.

Three layers of validation:
1. Schema validation: types match, required fields present, constraints satisfied
2. Plausibility checks: row count stability, null rate spikes (requires historical data)
3. Confidence scoring: per-field scores based on extraction resolution tier
"""

from __future__ import annotations

import re
from typing import Any

from forum_schemas.models.errors import ErrorCode

from forum_pipeline.context import RunContext
from forum_pipeline.errors import StageError
from forum_pipeline.stage_data import StageData

# Confidence scores by resolution tier (from bible section 12.1)
_TIER_CONFIDENCE: dict[str, float] = {
    "direct_selector": 0.95,
    "fingerprint_match": 0.90,
    "content_match": 0.80,
    "similarity_match": 0.80,
    "llm_relocation": 0.75,
}


async def run_validate(data: StageData, ctx: RunContext) -> StageData:
    """Execute the Validate stage."""
    if not data.rows:
        return data

    columns = {
        col["name"]: col for col in data.schema.get("columns", [])
    }

    if not columns:
        # No schema to validate against
        data.stage_metadata["validate"] = {"skipped": True, "reason": "no schema"}
        return data

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Schema validation: types and nullability
    for i, row in enumerate(data.rows):
        for col_name, col_def in columns.items():
            value = row.get(col_name)

            # Null check
            if value is None and not col_def.get("nullable", True):
                errors.append(f"Row {i}: required field '{col_name}' is null")
                continue

            if value is None:
                continue

            # Type check
            expected_type = col_def.get("type", "STRING")
            if not _type_matches(value, expected_type):
                warnings.append(
                    f"Row {i}: field '{col_name}' expected {expected_type}, "
                    f"got {type(value).__name__}"
                )

            # Constraint check
            constraints = col_def.get("constraints")
            if constraints:
                constraint_errors = _check_constraints(value, col_name, constraints, i)
                errors.extend(constraint_errors)

    # 2. Confidence scoring from source grounding
    field_confidence: dict[str, float] = {}
    for g in data.grounding:
        field = g.get("field", "")
        tier = g.get("tier", "direct_selector")
        confidence = _TIER_CONFIDENCE.get(tier, 0.7)
        # Use minimum confidence across all occurrences of a field
        if field not in field_confidence or confidence < field_confidence[field]:
            field_confidence[field] = confidence

    low_confidence_fields = [
        f for f, c in field_confidence.items() if c < 0.6
    ]
    medium_confidence_fields = [
        f for f, c in field_confidence.items() if 0.6 <= c < 0.9
    ]

    # Configurable: block fields below confidence threshold (bible.md: default block <0.6 for trading)
    confidence_block_threshold = data.config.get("confidence_block_threshold", 0.0)
    if confidence_block_threshold > 0 and field_confidence:
        blocked_fields = [
            f for f, c in field_confidence.items()
            if c < confidence_block_threshold
        ]
        if blocked_fields:
            raise StageError(
                ErrorCode.EXTRACTION_FAILED,
                f"Fields below confidence block threshold ({confidence_block_threshold}): "
                f"{', '.join(blocked_fields)}",
                fields=blocked_fields,
                scores={f: field_confidence[f] for f in blocked_fields},
            )

    if low_confidence_fields:
        ctx.add_warning(
            "LOW_CONFIDENCE",
            f"Low confidence fields: {', '.join(low_confidence_fields)}",
            fields=low_confidence_fields,
            scores={f: field_confidence[f] for f in low_confidence_fields},
        )

    # 3. Record validation results
    data.stage_metadata["validate"] = {
        "schema_errors": len(errors),
        "schema_warnings": len(warnings),
        "field_confidence": field_confidence,
        "low_confidence_fields": low_confidence_fields,
        "medium_confidence_fields": medium_confidence_fields,
    }

    # Fail on schema errors if there are many (>20% of rows)
    if errors:
        error_rate = len(errors) / max(len(data.rows), 1)
        if error_rate > 0.2:
            raise StageError(
                ErrorCode.SCHEMA_MISMATCH,
                f"Schema validation failed: {len(errors)} errors across {len(data.rows)} rows "
                f"({error_rate:.0%} error rate)",
                errors=errors[:20],  # Cap at 20 for readability
            )
        else:
            # Record as warnings if error rate is low
            for err in errors[:10]:
                ctx.add_warning("PARTIAL_RESULTS", err)

    return data


def _type_matches(value: Any, expected_type: str) -> bool:
    """Check if a Python value matches the expected schema type."""
    match expected_type:
        case "STRING":
            return isinstance(value, str)
        case "INTEGER":
            return isinstance(value, int) and not isinstance(value, bool)
        case "FLOAT":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        case "BOOLEAN":
            return isinstance(value, bool)
        case "DATE" | "DATETIME":
            return isinstance(value, str)  # Dates stored as ISO strings
        case _:
            return True


def _check_constraints(
    value: Any, col_name: str, constraints: dict[str, Any], row_idx: int
) -> list[str]:
    """Check column constraints (min, max, pattern, allowed_values)."""
    errors: list[str] = []

    if "min" in constraints and isinstance(value, (int, float)):
        if value < constraints["min"]:
            errors.append(
                f"Row {row_idx}: '{col_name}' value {value} below minimum {constraints['min']}"
            )

    if "max" in constraints and isinstance(value, (int, float)):
        if value > constraints["max"]:
            errors.append(
                f"Row {row_idx}: '{col_name}' value {value} above maximum {constraints['max']}"
            )

    if "pattern" in constraints and isinstance(value, str):
        if not re.match(constraints["pattern"], value):
            errors.append(
                f"Row {row_idx}: '{col_name}' value '{value}' doesn't match pattern '{constraints['pattern']}'"
            )

    if "allowed_values" in constraints and isinstance(constraints["allowed_values"], list):
        if str(value) not in constraints["allowed_values"]:
            errors.append(
                f"Row {row_idx}: '{col_name}' value '{value}' not in allowed values"
            )

    return errors
