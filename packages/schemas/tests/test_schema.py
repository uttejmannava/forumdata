"""Tests for extraction schema models."""

from uuid import uuid4

from forum_schemas.models.schema import (
    ChangeType,
    ColumnConstraints,
    ColumnDefinition,
    ColumnType,
    ExtractionSchema,
    SchemaStatus,
    SchemaTemplate,
)


class TestColumnDefinition:
    def test_create(self) -> None:
        col = ColumnDefinition(name="price", type=ColumnType.FLOAT, nullable=False)
        assert col.name == "price"
        assert col.type == ColumnType.FLOAT

    def test_with_constraints(self) -> None:
        col = ColumnDefinition(
            name="price",
            type=ColumnType.FLOAT,
            constraints=ColumnConstraints(min=0),
        )
        assert col.constraints is not None
        assert col.constraints.min == 0


class TestExtractionSchema:
    def test_create(self, sample_columns: list[ColumnDefinition]) -> None:
        schema = ExtractionSchema(
            pipeline_id=uuid4(),
            version=1,
            columns=sample_columns,
            change_type=ChangeType.INITIAL,
            created_by="test",
        )
        assert schema.version == 1
        assert schema.status == SchemaStatus.DRAFT
        assert schema.breaking is False
        assert len(schema.columns) == 3


class TestSchemaTemplate:
    def test_create(self, sample_columns: list[ColumnDefinition]) -> None:
        template = SchemaTemplate(
            tenant_id=uuid4(),
            name="CME Settlement Schema",
            columns=sample_columns,
            primary_key=["contract"],
            created_by="test",
        )
        assert template.name == "CME Settlement Schema"
