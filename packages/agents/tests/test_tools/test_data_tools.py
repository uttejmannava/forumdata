"""Tests for data parsing and validation tools."""

from __future__ import annotations

from forum_agents.tools.data import (
    detect_pii,
    extract_table_data,
    parse_csv,
    parse_json,
    validate_against_schema,
)


def test_parse_json_valid() -> None:
    result = parse_json('{"key": "value", "num": 42}')
    assert result.success
    assert result.data["parsed"]["key"] == "value"
    assert result.data["parsed"]["num"] == 42


def test_parse_json_invalid() -> None:
    result = parse_json("{bad json")
    assert not result.success
    assert result.error is not None


def test_parse_csv() -> None:
    csv_text = "name,price\nWidget,9.99\nGadget,19.99"
    result = parse_csv(csv_text)
    assert result.success
    assert result.data["row_count"] == 2
    assert result.data["rows"][0]["name"] == "Widget"
    assert result.data["columns"] == ["name", "price"]


def test_validate_against_schema_pass() -> None:
    schema = {"columns": [{"name": "price", "type": "float", "nullable": True}]}
    data = [{"price": "9.99"}, {"price": None}]
    result = validate_against_schema(data, schema)
    assert result.success
    assert result.data["error_count"] == 0


def test_validate_against_schema_fail() -> None:
    schema = {"columns": [{"name": "price", "type": "float", "nullable": False}]}
    data = [{"price": None}]
    result = validate_against_schema(data, schema)
    assert not result.success
    assert result.data["error_count"] == 1


def test_detect_pii_email() -> None:
    result = detect_pii("Contact us at test@example.com for info")
    assert result.success
    assert result.data["has_pii"]
    assert result.data["findings"][0]["type"] == "email"


def test_detect_pii_ssn() -> None:
    result = detect_pii("SSN: 123-45-6789")
    assert result.data["has_pii"]
    assert any(f["type"] == "ssn" for f in result.data["findings"])


def test_detect_pii_none() -> None:
    result = detect_pii("No personal information here.")
    assert result.success
    assert not result.data["has_pii"]


def test_extract_table_data() -> None:
    html = """
    <table>
        <thead><tr><th>Name</th><th>Price</th></tr></thead>
        <tbody>
            <tr><td>Widget</td><td>9.99</td></tr>
            <tr><td>Gadget</td><td>19.99</td></tr>
        </tbody>
    </table>
    """
    result = extract_table_data(html)
    assert result.success
    assert result.data["row_count"] == 2
    assert result.data["headers"] == ["Name", "Price"]
    assert result.data["rows"][0]["Name"] == "Widget"
