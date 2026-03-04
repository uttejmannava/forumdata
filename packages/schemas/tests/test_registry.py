"""Tests for schema registry logic (breaking change detection)."""

from forum_schemas.models.schema import (
    ColumnConstraints,
    ColumnDefinition,
    ColumnType,
    ExtractionSchema,
)
from forum_schemas.registry import detect_breaking_changes, is_auto_promotable


class TestDetectBreakingChanges:
    def test_no_changes(self, sample_columns: list[ColumnDefinition]) -> None:
        assert detect_breaking_changes(sample_columns, sample_columns) == []

    def test_add_nullable_column(self, sample_columns: list[ColumnDefinition]) -> None:
        new = sample_columns + [ColumnDefinition(name="open_interest", type=ColumnType.INTEGER, nullable=True)]
        assert detect_breaking_changes(sample_columns, new) == []

    def test_add_non_nullable_column(self, sample_columns: list[ColumnDefinition]) -> None:
        new = sample_columns + [ColumnDefinition(name="open_interest", type=ColumnType.INTEGER, nullable=False)]
        changes = detect_breaking_changes(sample_columns, new)
        assert len(changes) == 1
        assert "Non-nullable" in changes[0]

    def test_remove_column(self, sample_columns: list[ColumnDefinition]) -> None:
        new = sample_columns[:2]  # Remove 'volume'
        changes = detect_breaking_changes(sample_columns, new)
        assert len(changes) == 1
        assert "'volume' removed" in changes[0]

    def test_type_change(self, sample_columns: list[ColumnDefinition]) -> None:
        new = [
            sample_columns[0],
            ColumnDefinition(name="settlement_price", type=ColumnType.STRING, nullable=False),  # was FLOAT
            sample_columns[2],
        ]
        changes = detect_breaking_changes(sample_columns, new)
        assert len(changes) == 1
        assert "type changed" in changes[0]

    def test_nullable_to_non_nullable(self, sample_columns: list[ColumnDefinition]) -> None:
        new = [
            sample_columns[0],
            sample_columns[1],
            ColumnDefinition(name="volume", type=ColumnType.INTEGER, nullable=False),  # was True
        ]
        changes = detect_breaking_changes(sample_columns, new)
        assert len(changes) == 1
        assert "non-nullable" in changes[0]

    def test_constraint_narrowing(self) -> None:
        old = [ColumnDefinition(name="price", type=ColumnType.FLOAT, constraints=ColumnConstraints(min=0, max=10000))]
        new = [ColumnDefinition(name="price", type=ColumnType.FLOAT, constraints=ColumnConstraints(min=10, max=10000))]
        changes = detect_breaking_changes(old, new)
        assert len(changes) == 1
        assert "narrowed" in changes[0]

    def test_constraint_widening_is_not_breaking(self) -> None:
        old = [ColumnDefinition(name="price", type=ColumnType.FLOAT, constraints=ColumnConstraints(min=10, max=100))]
        new = [ColumnDefinition(name="price", type=ColumnType.FLOAT, constraints=ColumnConstraints(min=0, max=1000))]
        assert detect_breaking_changes(old, new) == []

    def test_reorder_is_not_breaking(self, sample_columns: list[ColumnDefinition]) -> None:
        reordered = list(reversed(sample_columns))
        assert detect_breaking_changes(sample_columns, reordered) == []


class TestIsAutoPromotable:
    def test_non_breaking_is_promotable(self, sample_schema: ExtractionSchema) -> None:
        new_schema = sample_schema.model_copy(deep=True)
        new_schema.columns.append(ColumnDefinition(name="extra", type=ColumnType.STRING, nullable=True))
        new_schema.version = 2
        assert is_auto_promotable(sample_schema, new_schema) is True

    def test_breaking_is_not_promotable(self, sample_schema: ExtractionSchema) -> None:
        new_schema = sample_schema.model_copy(deep=True)
        new_schema.columns = new_schema.columns[:1]  # Remove columns
        new_schema.version = 2
        assert is_auto_promotable(sample_schema, new_schema) is False
