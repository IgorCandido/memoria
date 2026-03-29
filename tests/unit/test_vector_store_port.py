"""
Unit tests for VectorStorePort contract using VectorStoreStub.

All tests run in-memory — no external services required.
"""

import pytest

from memoria.adapters.stubs.vector_store_stub import VectorStoreStub
from memoria.domain.entities import Document


def _make_doc(doc_id: str, source: str = "test/doc", dim: int = 4) -> Document:
    """Helper to create a test Document with a simple embedding."""
    embedding = [1.0 / dim] * dim
    return Document(
        id=doc_id,
        content=f"Content for {doc_id}",
        metadata={"source": source},
        embedding=embedding,
    )


@pytest.fixture()
def store() -> VectorStoreStub:
    return VectorStoreStub()


class TestAddDocuments:
    def test_add_single_document(self, store):
        doc = _make_doc("doc-1")
        store.add_documents([doc])
        assert store.get_stats()["document_count"] == 1

    def test_add_multiple_documents(self, store):
        docs = [_make_doc(f"doc-{i}") for i in range(3)]
        store.add_documents(docs)
        assert store.get_stats()["document_count"] == 3

    def test_raises_on_missing_embedding(self, store):
        doc = Document(id="no-emb", content="text", metadata={}, embedding=None)
        with pytest.raises(ValueError):
            store.add_documents([doc])

    def test_overwrite_existing_doc_id(self, store):
        doc1 = _make_doc("doc-1")
        store.add_documents([doc1])
        doc2 = Document(id="doc-1", content="updated", metadata={}, embedding=[0.5, 0.5, 0.5, 0.5])
        store.add_documents([doc2])
        assert store.get_stats()["document_count"] == 1
        retrieved = store.get_by_id("doc-1")
        assert retrieved is not None
        assert retrieved.content == "updated"


class TestSearch:
    def test_returns_results(self, store):
        store.add_documents([_make_doc("doc-1"), _make_doc("doc-2")])
        query = [0.25, 0.25, 0.25, 0.25]
        results = store.search(query, k=2)
        assert len(results) == 2

    def test_respects_k_limit(self, store):
        for i in range(5):
            store.add_documents([_make_doc(f"doc-{i}")])
        query = [0.25, 0.25, 0.25, 0.25]
        results = store.search(query, k=2)
        assert len(results) <= 2

    def test_empty_store_returns_empty_list(self, store):
        results = store.search([0.1, 0.2, 0.3, 0.4], k=5)
        assert results == []

    def test_raises_on_invalid_k(self, store):
        with pytest.raises(ValueError):
            store.search([0.1, 0.2, 0.3, 0.4], k=0)


class TestDelete:
    def test_delete_existing_returns_true(self, store):
        store.add_documents([_make_doc("doc-1")])
        result = store.delete("doc-1")
        assert result is True
        assert store.get_by_id("doc-1") is None

    def test_delete_absent_returns_false(self, store):
        result = store.delete("nonexistent")
        assert result is False

    def test_count_decrements_after_delete(self, store):
        store.add_documents([_make_doc("doc-1"), _make_doc("doc-2")])
        store.delete("doc-1")
        assert store.get_stats()["document_count"] == 1


class TestGetById:
    def test_found(self, store):
        doc = _make_doc("doc-1")
        store.add_documents([doc])
        result = store.get_by_id("doc-1")
        assert result is not None
        assert result.id == "doc-1"

    def test_not_found(self, store):
        assert store.get_by_id("missing") is None


class TestClear:
    def test_clear_removes_all(self, store):
        store.add_documents([_make_doc("doc-1"), _make_doc("doc-2")])
        store.clear()
        assert store.get_stats()["document_count"] == 0


class TestStructuralConformance:
    def test_stub_has_port_methods(self, store):
        assert callable(getattr(store, "add_documents", None))
        assert callable(getattr(store, "search", None))
        assert callable(getattr(store, "delete", None))
        assert callable(getattr(store, "get_by_id", None))
