"""
DocumentStoreStub - In-memory implementation of DocumentStorePort.

Provides a fully functional in-memory document store for unit testing.
No external dependencies required — all state is in-memory dicts.
"""

import hashlib
from datetime import datetime, timezone
from typing import Iterator

from memoria.domain.entities import StoredDocument


class DocumentStoreStub:
    """
    In-memory document store implementing DocumentStorePort.

    Mirrors the upsert semantics of PostgresDocumentStoreAdapter:
    - Unchanged fingerprint → no-op, returns existing
    - Changed fingerprint → updates content, increments version

    All state is lost when the instance is garbage-collected.
    """

    def __init__(self) -> None:
        self._documents: dict[str, StoredDocument] = {}

    @staticmethod
    def _fingerprint(content: str) -> str:
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def store(self, source_id: str, title: str, content: str) -> StoredDocument:
        """Insert or upsert a document by source_id."""
        fingerprint = self._fingerprint(content)
        now = datetime.now(tz=timezone.utc)

        if source_id in self._documents:
            existing = self._documents[source_id]
            if existing.fingerprint == fingerprint:
                return existing
            # Content changed — increment version
            doc = StoredDocument(
                id=existing.id,
                source_id=source_id,
                title=title,
                content=content,
                fingerprint=fingerprint,
                version=existing.version + 1,
                created_at=existing.created_at,
                updated_at=now,
            )
        else:
            doc = StoredDocument(
                id=f"stub-{len(self._documents) + 1}",
                source_id=source_id,
                title=title,
                content=content,
                fingerprint=fingerprint,
                version=1,
                created_at=now,
                updated_at=now,
            )

        self._documents[source_id] = doc
        return doc

    def get(self, source_id: str) -> StoredDocument | None:
        return self._documents.get(source_id)

    def list_all(self) -> list[StoredDocument]:
        return sorted(self._documents.values(), key=lambda d: d.source_id)

    def delete(self, source_id: str) -> bool:
        if source_id in self._documents:
            del self._documents[source_id]
            return True
        return False

    def get_fingerprint(self, source_id: str) -> str | None:
        doc = self._documents.get(source_id)
        return doc.fingerprint if doc else None

    def export_all(self) -> Iterator[StoredDocument]:
        for doc in sorted(self._documents.values(), key=lambda d: d.source_id):
            yield doc

    def count(self) -> int:
        return len(self._documents)

    def health_check(self) -> bool:
        return True
