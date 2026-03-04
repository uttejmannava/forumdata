"""Fluent schema builder API for constructing extraction schemas programmatically."""

from __future__ import annotations

from typing import Any

from forum_schemas.models.schema import ColumnConstraints, ColumnDefinition, ColumnType


class SchemaBuilder:
    """Build extraction schemas with a fluent API.

    Usage:
        schema = (SchemaBuilder("CME Settlement")
            .field("contract", "Contract symbol", "STRING", nullable=False, example="CLZ25")
            .field("settlement_price", "Daily settlement price", "FLOAT", nullable=False, constraints={"min": 0})
            .field("volume", "Contracts traded", "INTEGER", nullable=True)
            .primary_key(["contract", "last_updated"])
            .build())
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._columns: list[ColumnDefinition] = []
        self._primary_key: list[str] = []
        self._dedup_key: list[str] = []

    def field(
        self,
        name: str,
        description: str = "",
        type: str = "STRING",
        *,
        nullable: bool = True,
        constraints: dict[str, Any] | None = None,
        example: str | None = None,
    ) -> SchemaBuilder:
        col_type = ColumnType(type.lower())
        col_constraints = ColumnConstraints(**constraints) if constraints else None
        self._columns.append(
            ColumnDefinition(
                name=name,
                type=col_type,
                description=description,
                nullable=nullable,
                constraints=col_constraints,
                example=example,
            )
        )
        return self

    def primary_key(self, keys: list[str]) -> SchemaBuilder:
        self._primary_key = keys
        return self

    def dedup_key(self, keys: list[str]) -> SchemaBuilder:
        self._dedup_key = keys
        return self

    def build(self) -> dict[str, Any]:
        """Return schema definition as a dict (matches bible.md §9.2 JSONB format)."""
        return {
            "name": self.name,
            "columns": [col.model_dump() for col in self._columns],
            "primary_key": self._primary_key,
            "dedup_key": self._dedup_key,
        }
