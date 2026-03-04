"""Shared test fixtures for forum-schemas tests."""

from uuid import uuid4

import pytest

from forum_schemas.models.schema import ChangeType, ColumnDefinition, ColumnType, ExtractionSchema, SchemaStatus


@pytest.fixture
def sample_columns() -> list[ColumnDefinition]:
    return [
        ColumnDefinition(name="contract", type=ColumnType.STRING, nullable=False, example="CLZ25"),
        ColumnDefinition(name="settlement_price", type=ColumnType.FLOAT, nullable=False),
        ColumnDefinition(name="volume", type=ColumnType.INTEGER, nullable=True),
    ]


@pytest.fixture
def sample_schema(sample_columns: list[ColumnDefinition]) -> ExtractionSchema:
    return ExtractionSchema(
        pipeline_id=uuid4(),
        version=1,
        columns=sample_columns,
        primary_key=["contract"],
        change_type=ChangeType.INITIAL,
        created_by="test",
        status=SchemaStatus.ACTIVE,
    )
