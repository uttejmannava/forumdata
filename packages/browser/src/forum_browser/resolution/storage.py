"""Pluggable fingerprint storage adapter."""

from __future__ import annotations

import abc
import json
import sqlite3
from typing import TYPE_CHECKING

from forum_browser.resolution.fingerprints import ElementFingerprint

if TYPE_CHECKING:
    from pathlib import Path


class FingerprintStorage(abc.ABC):
    """Abstract interface for fingerprint storage."""

    @abc.abstractmethod
    async def save(self, tenant_id: str, pipeline_id: str, identifier: str, fingerprint: ElementFingerprint) -> None:
        ...

    @abc.abstractmethod
    async def load(self, tenant_id: str, pipeline_id: str, identifier: str) -> ElementFingerprint | None:
        ...

    @abc.abstractmethod
    async def delete(self, tenant_id: str, pipeline_id: str, identifier: str) -> None:
        ...


class SqliteFingerprintStorage(FingerprintStorage):
    """SQLite-based fingerprint storage for local development."""

    def __init__(self, db_path: Path | None = None) -> None:
        from pathlib import Path as _Path

        self._db_path = db_path or _Path.home() / ".forum" / "fingerprints.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS fingerprints (
                tenant_id TEXT NOT NULL,
                pipeline_id TEXT NOT NULL,
                identifier TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (tenant_id, pipeline_id, identifier)
            )
        """)
        self._conn.commit()

    async def save(self, tenant_id: str, pipeline_id: str, identifier: str, fingerprint: ElementFingerprint) -> None:
        data = json.dumps({
            "identifier": fingerprint.identifier,
            "tag_name": fingerprint.tag_name,
            "text_content": fingerprint.text_content,
            "attributes": fingerprint.attributes,
            "sibling_tags": fingerprint.sibling_tags,
            "ancestor_path": fingerprint.ancestor_path,
            "parent_tag": fingerprint.parent_tag,
            "parent_attributes": fingerprint.parent_attributes,
            "css_selector": fingerprint.css_selector,
            "xpath": fingerprint.xpath,
        })
        self._conn.execute(
            "INSERT OR REPLACE INTO fingerprints (tenant_id, pipeline_id, identifier, data) VALUES (?, ?, ?, ?)",
            (tenant_id, pipeline_id, identifier, data),
        )
        self._conn.commit()

    async def load(self, tenant_id: str, pipeline_id: str, identifier: str) -> ElementFingerprint | None:
        cursor = self._conn.execute(
            "SELECT data FROM fingerprints WHERE tenant_id = ? AND pipeline_id = ? AND identifier = ?",
            (tenant_id, pipeline_id, identifier),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        return ElementFingerprint(**data)

    async def delete(self, tenant_id: str, pipeline_id: str, identifier: str) -> None:
        self._conn.execute(
            "DELETE FROM fingerprints WHERE tenant_id = ? AND pipeline_id = ? AND identifier = ?",
            (tenant_id, pipeline_id, identifier),
        )
        self._conn.commit()
