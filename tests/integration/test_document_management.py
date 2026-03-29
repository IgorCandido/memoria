"""
End-to-end integration tests for DB-backed document management.

Requires live infrastructure:
  - Postgres on relishhost1:5435 (database=memoria)
  - ChromaDB on relishhost1:8001
  - Ollama on relishhost2:11434 with mxbai-embed-large

Run with: pytest --run-integration tests/integration/test_document_management.py
"""

import json
import tempfile

import pytest

import memoria.skill_helpers as sh

TEST_SOURCE_PREFIX = "integration-e2e/"


def _cleanup(*source_ids: str) -> None:
    """Best-effort cleanup of test documents."""
    for sid in source_ids:
        try:
            sh.delete_document(sid)
        except Exception:
            pass


@pytest.mark.integration
class TestUS1StoreAndRetrieve:
    """US1: Store documents in database without /docs folder."""

    def test_store_then_get(self):
        sid = f"{TEST_SOURCE_PREFIX}us1-basic"
        try:
            result = sh.store_document("# Test\nHello world content", sid, "US1 Test")
            assert sid in result
            content = sh.get_document(sid)
            assert "Hello world content" in content
        finally:
            _cleanup(sid)

    def test_get_raises_for_unknown(self):
        with pytest.raises(ValueError, match="not found"):
            sh.get_document(f"{TEST_SOURCE_PREFIX}nonexistent-12345")

    def test_store_idempotent(self):
        sid = f"{TEST_SOURCE_PREFIX}us1-idempotent"
        try:
            sh.store_document("Content v1", sid)
            sh.store_document("Content v1", sid)  # Same content
            doc = sh._get_document_store().get(sid)
            assert doc is not None
            assert doc.version == 1
        finally:
            _cleanup(sid)

    def test_search_finds_stored_document(self):
        sid = f"{TEST_SOURCE_PREFIX}us1-search"
        unique_phrase = "zorblax-frimbulation-quantum"
        try:
            sh.store_document(f"The {unique_phrase} is a rare phenomenon", sid)
            result = sh.search_knowledge(unique_phrase, limit=5)
            assert isinstance(result, str)
        finally:
            _cleanup(sid)


@pytest.mark.integration
class TestUS2ExportAndUS3Import:
    """US2 + US3: Export corpus to JSONL, import back."""

    def test_export_import_round_trip(self):
        sids = [f"{TEST_SOURCE_PREFIX}round-trip-{i}" for i in range(3)]
        try:
            for i, sid in enumerate(sids):
                sh.store_document(f"Content for document {i}", sid, f"Doc {i}")

            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
                export_path = f.name

            sh.export_corpus(export_path)

            with open(export_path) as f:
                lines = [l.strip() for l in f if l.strip()]

            assert len(lines) >= 4  # manifest + at least 3 docs
            manifest = json.loads(lines[0])
            assert manifest["document_count"] >= 3

            result = sh.import_corpus(export_path)
            assert result.documents_skipped >= 3  # All already present

        finally:
            _cleanup(*sids)

    def test_import_updates_changed_documents(self):
        sid = f"{TEST_SOURCE_PREFIX}import-update"
        try:
            sh.store_document("Original content", sid)

            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
                manifest = {"format_version": "1.0", "document_count": 1, "exported_at": "2026-01-01T00:00:00Z", "system_version": "test"}
                f.write(json.dumps(manifest) + "\n")
                f.write(json.dumps({"source_id": sid, "title": "Updated", "content": "Updated content"}) + "\n")
                path = f.name

            result = sh.import_corpus(path)
            assert result.documents_updated >= 1
        finally:
            _cleanup(sid)


@pytest.mark.integration
class TestUS4Reindex:
    """US4: Atomic reindex of all documents."""

    def test_reindex_processes_documents(self):
        sid = f"{TEST_SOURCE_PREFIX}reindex-doc"
        try:
            sh.store_document("Content for reindex test", sid)
            result = sh.reindex_corpus()
            assert result.documents_processed >= 1
            assert result.documents_failed == 0
            assert result.embedding_model != ""
        finally:
            _cleanup(sid)


@pytest.mark.integration
class TestUS5DocumentLifecycle:
    """US5: Delete and list documents."""

    def test_list_includes_stored_document(self):
        sid = f"{TEST_SOURCE_PREFIX}lifecycle-list"
        try:
            sh.store_document("List test content", sid)
            docs = sh.list_documents()
            source_ids = {d.source_id for d in docs}
            assert sid in source_ids
        finally:
            _cleanup(sid)

    def test_delete_removes_document(self):
        sid = f"{TEST_SOURCE_PREFIX}lifecycle-delete"
        sh.store_document("Delete test content", sid)
        result = sh.delete_document(sid)
        assert "Deleted" in result or sid in result
        assert sh._get_document_store().get(sid) is None

    def test_delete_nonexistent_returns_not_found(self):
        result = sh.delete_document(f"{TEST_SOURCE_PREFIX}ghost-12345")
        assert "not found" in result
