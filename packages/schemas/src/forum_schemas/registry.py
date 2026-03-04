"""Schema versioning logic — breaking change detection and auto-promotion rules.

This is pure domain logic. It does not interact with databases or APIs.
The API service layer calls these functions when schemas are created/updated.
"""

from __future__ import annotations

from forum_schemas.models.schema import ColumnDefinition, ExtractionSchema  # noqa: TCH001


def detect_breaking_changes(
    old_columns: list[ColumnDefinition],
    new_columns: list[ColumnDefinition],
) -> list[str]:
    """Compare two column lists and return descriptions of breaking changes.

    Breaking changes per bible.md §9.3:
    - Add non-nullable column
    - Remove column
    - Rename column (detected as remove + add)
    - Change column type
    - Narrow constraints

    Non-breaking (auto-promotable):
    - Add nullable column
    - Widen constraints
    - Reorder columns
    """
    breaking: list[str] = []
    old_by_name = {col.name: col for col in old_columns}
    new_by_name = {col.name: col for col in new_columns}

    # Removed columns
    for name in old_by_name:
        if name not in new_by_name:
            breaking.append(f"Column '{name}' removed")

    # New or changed columns
    for name, new_col in new_by_name.items():
        if name not in old_by_name:
            if not new_col.nullable:
                breaking.append(f"Non-nullable column '{name}' added")
            continue

        old_col = old_by_name[name]

        # Type change
        if old_col.type != new_col.type:
            breaking.append(f"Column '{name}' type changed from {old_col.type.value} to {new_col.type.value}")

        # Nullable narrowed (was nullable, now not)
        if old_col.nullable and not new_col.nullable:
            breaking.append(f"Column '{name}' changed from nullable to non-nullable")

        # Constraint narrowing
        if old_col.constraints and new_col.constraints:
            old_c = old_col.constraints
            new_c = new_col.constraints
            if new_c.min is not None and (old_c.min is None or new_c.min > old_c.min):
                breaking.append(f"Column '{name}' min constraint narrowed")
            if new_c.max is not None and (old_c.max is None or new_c.max < old_c.max):
                breaking.append(f"Column '{name}' max constraint narrowed")
        elif not old_col.constraints and new_col.constraints:
            # Adding constraints where there were none is narrowing
            if new_col.constraints.min is not None or new_col.constraints.max is not None:
                breaking.append(f"Column '{name}' constraints added (narrowing)")

    return breaking


def is_auto_promotable(old_schema: ExtractionSchema, new_schema: ExtractionSchema) -> bool:
    """Determine if a schema change can be auto-promoted without approval.

    Auto-promotable if there are zero breaking changes. Per bible.md §9.3.
    """
    changes = detect_breaking_changes(old_schema.columns, new_schema.columns)
    return len(changes) == 0
