"""Tests for fingerprint storage."""

from __future__ import annotations

from pathlib import Path

from forum_browser.resolution.fingerprints import ElementFingerprint
from forum_browser.resolution.storage import SqliteFingerprintStorage


class TestSqliteFingerprintStorage:
    async def test_save_and_load(self, tmp_path: Path) -> None:
        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        fp = ElementFingerprint(
            identifier="price",
            tag_name="td",
            text_content="72.45",
            attributes={"class": "price"},
            sibling_tags=["td", "td"],
            ancestor_path=["html", "body", "table", "tr"],
            parent_tag="tr",
        )
        await storage.save("tenant1", "pipe1", "price", fp)
        loaded = await storage.load("tenant1", "pipe1", "price")
        assert loaded is not None
        assert loaded.tag_name == "td"
        assert loaded.text_content == "72.45"
        assert loaded.identifier == "price"

    async def test_load_nonexistent(self, tmp_path: Path) -> None:
        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        loaded = await storage.load("t", "p", "missing")
        assert loaded is None

    async def test_delete(self, tmp_path: Path) -> None:
        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        fp = ElementFingerprint(identifier="x", tag_name="div", text_content="test")
        await storage.save("t", "p", "x", fp)
        assert await storage.load("t", "p", "x") is not None
        await storage.delete("t", "p", "x")
        assert await storage.load("t", "p", "x") is None

    async def test_upsert(self, tmp_path: Path) -> None:
        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        fp1 = ElementFingerprint(identifier="x", tag_name="div", text_content="v1")
        fp2 = ElementFingerprint(identifier="x", tag_name="span", text_content="v2")
        await storage.save("t", "p", "x", fp1)
        await storage.save("t", "p", "x", fp2)
        loaded = await storage.load("t", "p", "x")
        assert loaded is not None
        assert loaded.tag_name == "span"
        assert loaded.text_content == "v2"

    async def test_tenant_isolation(self, tmp_path: Path) -> None:
        storage = SqliteFingerprintStorage(db_path=tmp_path / "fp.db")
        fp1 = ElementFingerprint(identifier="x", tag_name="div", text_content="tenant1")
        fp2 = ElementFingerprint(identifier="x", tag_name="div", text_content="tenant2")
        await storage.save("t1", "p", "x", fp1)
        await storage.save("t2", "p", "x", fp2)
        loaded1 = await storage.load("t1", "p", "x")
        loaded2 = await storage.load("t2", "p", "x")
        assert loaded1 is not None
        assert loaded2 is not None
        assert loaded1.text_content == "tenant1"
        assert loaded2.text_content == "tenant2"
