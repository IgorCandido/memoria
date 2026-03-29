"""
Unit tests for new public functions added to skill_helpers.py.

Uses injected stubs for DocumentStorePort, EmbeddingGeneratorPort, and
VectorStorePort — no external services required.
"""

import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from memoria.adapters.stubs.document_store_stub import DocumentStoreStub
from memoria.adapters.stubs.embedding_generator_stub import EmbeddingGeneratorStub
from memoria.adapters.stubs.vector_store_stub import VectorStoreStub


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_vector_store_stub():
    """VectorStoreStub wired with a mock _collection for ChromaDB-style queries."""
    stub = VectorStoreStub()
    collection_mock = MagicMock()
    collection_mock.get.return_value = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
    stub._collection = collection_mock
    return stub


def _make_doc_processor_stub():
    """Minimal document processor stub that chunk_text returns one chunk per 10 chars."""
    from memoria.adapters.stubs.document_processor_stub import DocumentProcessorStub
    return DocumentProcessorStub()


@pytest.fixture()
def doc_store():
    return DocumentStoreStub()


@pytest.fixture()
def embedder():
    return EmbeddingGeneratorStub(dimensions=1024)


@pytest.fixture()
def vector_store():
    return _make_vector_store_stub()


@pytest.fixture()
def doc_processor():
    return _make_doc_processor_stub()


# ---------------------------------------------------------------------------
# store_document
# ---------------------------------------------------------------------------

class TestStoreDocument:
    def test_returns_summary_string(self, doc_store, embedder, vector_store, doc_processor):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, embedder, MagicMock(), doc_processor)):
            from memoria.skill_helpers import store_document
            result = store_document("# Hello\nContent here", "test/doc", "Test Doc")
        assert isinstance(result, str)
        assert "test/doc" in result

    def test_document_persisted_in_store(self, doc_store, embedder, vector_store, doc_processor):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, embedder, MagicMock(), doc_processor)):
            from memoria.skill_helpers import store_document
            store_document("My content", "docs/guide", "Guide")
        assert doc_store.get("docs/guide") is not None
        assert doc_store.get("docs/guide").content == "My content"

    def test_no_op_on_unchanged_content(self, doc_store, embedder, vector_store, doc_processor):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, embedder, MagicMock(), doc_processor)):
            from memoria.skill_helpers import store_document
            store_document("My content", "docs/guide", "Guide")
            store_document("My content", "docs/guide", "Guide")
        assert doc_store.get("docs/guide").version == 1


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------

class TestGetDocument:
    def test_returns_content_for_existing(self, doc_store):
        doc_store.store("docs/guide", "Guide", "The content")
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import get_document
            result = get_document("docs/guide")
        assert result == "The content"

    def test_raises_for_missing(self, doc_store):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import get_document
            with pytest.raises(ValueError, match="not found"):
                get_document("nonexistent")


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    def test_returns_success_message(self, doc_store, vector_store):
        doc_store.store("docs/guide", "Guide", "Content")
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, MagicMock(), MagicMock(), MagicMock())):
            from memoria.skill_helpers import delete_document
            result = delete_document("docs/guide")
        assert "docs/guide" in result
        assert doc_store.get("docs/guide") is None

    def test_returns_not_found_for_missing(self, doc_store, vector_store):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, MagicMock(), MagicMock(), MagicMock())):
            from memoria.skill_helpers import delete_document
            result = delete_document("nonexistent")
        assert "not found" in result


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------

class TestListDocuments:
    def test_returns_all_documents(self, doc_store):
        doc_store.store("docs/a", "A", "Content A")
        doc_store.store("docs/b", "B", "Content B")
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import list_documents
            result = list_documents()
        assert len(result) == 2
        source_ids = {d.source_id for d in result}
        assert source_ids == {"docs/a", "docs/b"}

    def test_empty_when_no_documents(self, doc_store):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import list_documents
            result = list_documents()
        assert result == []


# ---------------------------------------------------------------------------
# export_corpus
# ---------------------------------------------------------------------------

class TestExportCorpus:
    def test_creates_valid_jsonl_file(self, doc_store):
        doc_store.store("docs/a", "A", "Content A")
        doc_store.store("docs/b", "B", "Content B")
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import export_corpus
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
                output_path = f.name
            result = export_corpus(output_path)

        with open(output_path) as f:
            lines = [l.strip() for l in f if l.strip()]

        assert len(lines) == 3  # manifest + 2 docs
        manifest = json.loads(lines[0])
        assert "format_version" in manifest
        assert manifest["document_count"] == 2

        doc_line = json.loads(lines[1])
        assert "source_id" in doc_line
        assert "content" in doc_line

        assert isinstance(result, str)
        assert "2" in result  # doc count in summary

    def test_returns_summary_string(self, doc_store):
        doc_store.store("docs/x", "X", "Content X")
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import export_corpus
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
                output_path = f.name
            result = export_corpus(output_path)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# import_corpus
# ---------------------------------------------------------------------------

class TestImportCorpus:
    def _write_jsonl(self, path: str, docs: list[dict]) -> None:
        manifest = {"format_version": "1.0", "document_count": len(docs), "exported_at": "2026-01-01T00:00:00Z", "system_version": "test"}
        with open(path, "w") as f:
            f.write(json.dumps(manifest) + "\n")
            for doc in docs:
                f.write(json.dumps(doc) + "\n")

    def test_imports_new_documents(self, doc_store, embedder, vector_store, doc_processor):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        self._write_jsonl(path, [
            {"source_id": "docs/a", "title": "A", "content": "Content A"},
            {"source_id": "docs/b", "title": "B", "content": "Content B"},
        ])

        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, embedder, MagicMock(), doc_processor)), \
             patch("memoria.skill_helpers.store_document"):
            from memoria.skill_helpers import import_corpus
            result = import_corpus(path)

        assert result.documents_added == 2
        assert result.documents_skipped == 0

    def test_skips_unchanged_documents(self, doc_store, embedder, vector_store, doc_processor):
        doc_store.store("docs/a", "A", "Content A")
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        self._write_jsonl(path, [
            {"source_id": "docs/a", "title": "A", "content": "Content A"},
        ])

        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store), \
             patch("memoria.skill_helpers._get_adapters", return_value=(vector_store, embedder, MagicMock(), doc_processor)):
            from memoria.skill_helpers import import_corpus
            result = import_corpus(path)

        assert result.documents_skipped == 1
        assert result.documents_added == 0

    def test_raises_on_missing_file(self, doc_store):
        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import import_corpus
            with pytest.raises(ValueError, match="not found"):
                import_corpus("/tmp/nonexistent-12345.jsonl")

    def test_raises_on_invalid_manifest(self, doc_store):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            f.write("not valid json\n")
            path = f.name

        with patch("memoria.skill_helpers._get_document_store", return_value=doc_store):
            from memoria.skill_helpers import import_corpus
            with pytest.raises(ValueError):
                import_corpus(path)
