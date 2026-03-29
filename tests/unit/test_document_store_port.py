"""
Unit tests for DocumentStorePort contract using DocumentStoreStub.

All tests run in-memory — no external services required.
"""

import pytest

from memoria.adapters.stubs.document_store_stub import DocumentStoreStub


@pytest.fixture()
def store() -> DocumentStoreStub:
    return DocumentStoreStub()


class TestStore:
    def test_insert_new_document(self, store):
        doc = store.store("docs/guide", "Guide", "Hello world")
        assert doc.source_id == "docs/guide"
        assert doc.title == "Guide"
        assert doc.content == "Hello world"
        assert doc.version == 1

    def test_upsert_changed_content(self, store):
        store.store("docs/guide", "Guide", "Hello world")
        doc = store.store("docs/guide", "Guide", "Hello updated")
        assert doc.version == 2
        assert doc.content == "Hello updated"

    def test_fingerprint_no_op(self, store):
        first = store.store("docs/guide", "Guide", "Hello world")
        second = store.store("docs/guide", "Guide", "Hello world")
        assert first.id == second.id
        assert second.version == 1

    def test_multiple_documents_independent(self, store):
        store.store("docs/a", "A", "Content A")
        store.store("docs/b", "B", "Content B")
        assert store.count() == 2


class TestGet:
    def test_found(self, store):
        store.store("docs/guide", "Guide", "Content")
        doc = store.get("docs/guide")
        assert doc is not None
        assert doc.content == "Content"

    def test_not_found(self, store):
        assert store.get("nonexistent") is None


class TestDelete:
    def test_delete_existing(self, store):
        store.store("docs/guide", "Guide", "Content")
        result = store.delete("docs/guide")
        assert result is True
        assert store.get("docs/guide") is None

    def test_delete_absent(self, store):
        result = store.delete("nonexistent")
        assert result is False

    def test_count_decrements_after_delete(self, store):
        store.store("docs/a", "A", "Content A")
        store.store("docs/b", "B", "Content B")
        store.delete("docs/a")
        assert store.count() == 1


class TestGetFingerprint:
    def test_returns_fingerprint_for_existing(self, store):
        store.store("docs/guide", "Guide", "Content")
        fp = store.get_fingerprint("docs/guide")
        assert fp is not None
        assert len(fp) == 64  # SHA-256 hex

    def test_returns_none_for_missing(self, store):
        assert store.get_fingerprint("nonexistent") is None


class TestExportAll:
    def test_yields_all_documents(self, store):
        store.store("docs/a", "A", "Content A")
        store.store("docs/b", "B", "Content B")
        docs = list(store.export_all())
        assert len(docs) == 2
        source_ids = {d.source_id for d in docs}
        assert source_ids == {"docs/a", "docs/b"}

    def test_empty_store_yields_nothing(self, store):
        assert list(store.export_all()) == []


class TestListAll:
    def test_returns_sorted_by_source_id(self, store):
        store.store("docs/z", "Z", "Content Z")
        store.store("docs/a", "A", "Content A")
        docs = store.list_all()
        assert [d.source_id for d in docs] == ["docs/a", "docs/z"]


class TestCount:
    def test_empty(self, store):
        assert store.count() == 0

    def test_after_inserts(self, store):
        store.store("docs/a", "A", "Content A")
        store.store("docs/b", "B", "Content B")
        assert store.count() == 2


class TestHealthCheck:
    def test_always_true(self, store):
        assert store.health_check() is True
