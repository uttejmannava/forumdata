"""Tests for the fluent schema builder API."""

from forum_schemas.builder import SchemaBuilder


class TestSchemaBuilder:
    def test_basic_build(self) -> None:
        result = SchemaBuilder("Test Schema").field("name", "Name field", "STRING", nullable=False).build()
        assert result["name"] == "Test Schema"
        assert len(result["columns"]) == 1
        assert result["columns"][0]["name"] == "name"
        assert result["columns"][0]["nullable"] is False

    def test_full_build(self) -> None:
        result = (
            SchemaBuilder("CME Settlement")
            .field("contract", "Contract symbol", "STRING", nullable=False, example="CLZ25")
            .field("settlement_price", "Daily settlement price", "FLOAT", nullable=False, constraints={"min": 0})
            .field("volume", "Contracts traded", "INTEGER", nullable=True)
            .field("last_updated", "Settlement date", "DATETIME", nullable=False)
            .primary_key(["contract", "last_updated"])
            .dedup_key(["contract", "last_updated"])
            .build()
        )
        assert result["name"] == "CME Settlement"
        assert len(result["columns"]) == 4
        assert result["primary_key"] == ["contract", "last_updated"]
        assert result["dedup_key"] == ["contract", "last_updated"]

    def test_chaining(self) -> None:
        builder = SchemaBuilder("test")
        result = builder.field("a", type="STRING").field("b", type="INTEGER").build()
        assert len(result["columns"]) == 2
