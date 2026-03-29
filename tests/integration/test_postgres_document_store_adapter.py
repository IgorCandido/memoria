"""
Integration tests for PostgresDocumentStoreAdapter.

Requires live Postgres on relishhost1:5435 with database=memoria.
Run with: pytest --run-integration tests/integration/test_postgres_document_store_adapter.py
"""

from typing import Iterator

import pytest

from memoria.adapters.postgres.postgres_document_store_adapter import PostgresDocumentStoreAdapter


SOURCE_ID_PREFIX = "integration-test/"


def _hard_delete_test_rows(a: PostgresDocumentStoreAdapter) -> None:
    """Hard-delete all integration-test/* rows for complete isolation."""
    try:
        with a._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM memoria_documents WHERE source_id LIKE %s",
                    (f"{SOURCE_ID_PREFIX}%",),
                )
            conn.commit()
    except Exception:
        pass


@pytest.fixture()
def adapter() -> Iterator[PostgresDocumentStoreAdapter]:  # type: ignore[override]
    """Create adapter; ensure schema; hard-delete test rows before and after each test."""
    a = PostgresDocumentStoreAdapter()
    a._ensure_schema()
    _hard_delete_test_rows(a)
    yield a
    _hard_delete_test_rows(a)


@pytest.mark.integration
class TestEnsureSchema:
    def test_schema_creation_idempotent(self, adapter):
        adapter._ensure_schema()
        adapter._schema_ensured = False  # Force re-run
        adapter._ensure_schema()  # Should not raise


@pytest.mark.integration
class TestStore:
    def test_insert_new_document(self, adapter):
        doc = adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Hello world")
        assert doc.source_id == f"{SOURCE_ID_PREFIX}doc-a"
        assert doc.title == "Doc A"
        assert doc.content == "Hello world"
        assert doc.version == 1

    def test_upsert_changed_content(self, adapter):
        adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Hello world")
        doc = adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Hello updated")
        assert doc.version == 2
        assert doc.content == "Hello updated"

    def test_fingerprint_no_op(self, adapter):
        first = adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Hello world")
        second = adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Hello world")
        assert first.id == second.id
        assert second.version == 1


@pytest.mark.integration
class TestGet:
    def test_found(self, adapter):
        adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Content")
        doc = adapter.get(f"{SOURCE_ID_PREFIX}doc-a")
        assert doc is not None
        assert doc.content == "Content"

    def test_not_found(self, adapter):
        assert adapter.get(f"{SOURCE_ID_PREFIX}nonexistent") is None


@pytest.mark.integration
class TestDelete:
    def test_soft_delete_existing(self, adapter):
        adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Content")
        result = adapter.delete(f"{SOURCE_ID_PREFIX}doc-a")
        assert result is True
        assert adapter.get(f"{SOURCE_ID_PREFIX}doc-a") is None

    def test_delete_absent_returns_false(self, adapter):
        result = adapter.delete(f"{SOURCE_ID_PREFIX}nonexistent")
        assert result is False


@pytest.mark.integration
class TestGetFingerprint:
    def test_returns_fingerprint(self, adapter):
        adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "Doc A", "Content")
        fp = adapter.get_fingerprint(f"{SOURCE_ID_PREFIX}doc-a")
        assert fp is not None
        assert len(fp) == 64

    def test_returns_none_for_missing(self, adapter):
        assert adapter.get_fingerprint(f"{SOURCE_ID_PREFIX}nonexistent") is None


@pytest.mark.integration
class TestExportAll:
    def test_yields_stored_documents(self, adapter):
        adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "A", "Content A")
        adapter.store(f"{SOURCE_ID_PREFIX}doc-b", "B", "Content B")
        docs = [d for d in adapter.export_all() if d.source_id.startswith(SOURCE_ID_PREFIX)]
        assert len(docs) >= 2
        source_ids = {d.source_id for d in docs}
        assert f"{SOURCE_ID_PREFIX}doc-a" in source_ids
        assert f"{SOURCE_ID_PREFIX}doc-b" in source_ids


@pytest.mark.integration
class TestCount:
    def test_count_increases_after_insert(self, adapter):
        before = adapter.count()
        adapter.store(f"{SOURCE_ID_PREFIX}doc-a", "A", "Content A")
        after = adapter.count()
        assert after == before + 1


@pytest.mark.integration
class TestHealthCheck:
    def test_postgres_reachable(self, adapter):
        assert adapter.health_check() is True
