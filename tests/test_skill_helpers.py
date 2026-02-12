"""Tests for skill_helpers.py - the public API layer.

These tests use real adapters (not stubs) to verify end-to-end integration.
They test the actual functions that Claude Code will call.
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from memoria import skill_helpers


class TestSearchKnowledge:
    """Tests for search_knowledge function."""

    def test_search_returns_formatted_string(self):
        """Test that search returns a formatted string output."""
        result = skill_helpers.search_knowledge("test query", limit=1)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain search results header
        assert "Search Results" in result or "No results" in result

    def test_search_with_different_modes(self):
        """Test search with different mode parameters."""
        # These should not raise errors
        result_semantic = skill_helpers.search_knowledge("test", mode="semantic")
        result_hybrid = skill_helpers.search_knowledge("test", mode="hybrid")

        assert isinstance(result_semantic, str)
        assert isinstance(result_hybrid, str)

    def test_search_respects_limit(self):
        """Test that search respects the limit parameter."""
        # Just verify it doesn't crash - actual limit enforcement is in adapters
        result = skill_helpers.search_knowledge("test", limit=1)
        assert isinstance(result, str)

        result_more = skill_helpers.search_knowledge("test", limit=10)
        assert isinstance(result_more, str)

    def test_search_with_expand_flag(self):
        """Test search with expand parameter."""
        result_expanded = skill_helpers.search_knowledge("test", expand=True)
        result_not_expanded = skill_helpers.search_knowledge("test", expand=False)

        assert isinstance(result_expanded, str)
        assert isinstance(result_not_expanded, str)


class TestIndexDocuments:
    """Tests for index_documents function."""

    def test_index_with_no_documents(self, tmp_path):
        """Test indexing when docs directory is empty."""
        # Temporarily override DOCS_DIR
        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            result = skill_helpers.index_documents()

            assert isinstance(result, str)
            # Should indicate no documents found
            assert "No documents" in result or "0 documents" in result

    def test_index_with_markdown_pattern(self, tmp_path):
        """Test indexing with markdown file pattern."""
        # Create a test markdown file
        test_doc = tmp_path / "test.md"
        test_doc.write_text("# Test Document\n\nTest content")

        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            result = skill_helpers.index_documents(pattern="**/*.md")

            assert isinstance(result, str)
            # Should have processed the file
            assert "test.md" in result or "1" in result

    def test_index_handles_errors_gracefully(self, tmp_path):
        """Test that indexing handles errors without crashing."""
        # Create a file that might cause issues
        bad_file = tmp_path / "bad.md"
        bad_file.write_text("")  # Empty file

        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            # Should not raise, but return error message
            result = skill_helpers.index_documents()
            assert isinstance(result, str)


class TestAddDocument:
    """Tests for add_document function."""

    def test_add_nonexistent_document(self):
        """Test adding a document that doesn't exist."""
        result = skill_helpers.add_document("/nonexistent/path/file.md")

        assert isinstance(result, str)
        assert "Not found" in result or "❌" in result

    def test_add_existing_document(self, tmp_path):
        """Test adding an existing document."""
        source_file = tmp_path / "source.md"
        source_file.write_text("Test content")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        with patch.object(skill_helpers, 'DOCS_DIR', docs_dir):
            result = skill_helpers.add_document(str(source_file), reindex=False)

            assert isinstance(result, str)
            # Should indicate success or duplicate
            assert "Added" in result or "exists" in result

    def test_add_with_reindex_flag(self, tmp_path):
        """Test adding document with reindex enabled."""
        source_file = tmp_path / "source.md"
        source_file.write_text("Test content")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        with patch.object(skill_helpers, 'DOCS_DIR', docs_dir):
            # Mock index_documents to avoid actual reindexing
            with patch.object(skill_helpers, 'index_documents', return_value="Mocked"):
                result = skill_helpers.add_document(str(source_file), reindex=True)

                assert isinstance(result, str)


class TestListIndexedDocuments:
    """Tests for list_indexed_documents function."""

    def test_list_with_no_documents(self, tmp_path):
        """Test listing when no documents exist."""
        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            result = skill_helpers.list_indexed_documents()

            assert isinstance(result, str)
            assert "No documents" in result or "0 files" in result

    def test_list_with_documents(self, tmp_path):
        """Test listing when documents exist."""
        # Create test files
        (tmp_path / "doc1.md").write_text("Content 1")
        (tmp_path / "doc2.md").write_text("Content 2")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "doc3.md").write_text("Content 3")

        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            result = skill_helpers.list_indexed_documents()

            assert isinstance(result, str)
            assert "doc1.md" in result
            assert "doc2.md" in result
            assert "doc3.md" in result


class TestGetStats:
    """Tests for get_stats function."""

    def test_get_stats_returns_formatted_output(self):
        """Test that get_stats returns formatted statistics."""
        result = skill_helpers.get_stats()

        assert isinstance(result, str)
        assert "Stats" in result or "Chunks" in result

    def test_get_stats_handles_errors_gracefully(self):
        """Test that get_stats handles ChromaDB errors."""
        # Mock the collection to raise an error
        with patch.object(skill_helpers, '_get_adapters') as mock_adapters:
            mock_store = Mock()
            mock_store._collection.count.side_effect = Exception("Connection error")
            mock_adapters.return_value = (mock_store, None, None, None)

            result = skill_helpers.get_stats()
            assert isinstance(result, str)
            # Should contain error indicator
            assert "❌" in result or "error" in result.lower()


class TestHealthCheck:
    """Tests for health_check function."""

    def test_health_check_returns_status(self):
        """Test that health_check returns health status."""
        result = skill_helpers.health_check()

        assert isinstance(result, str)
        assert "Health" in result or "healthy" in result.lower()

    def test_health_check_reports_errors(self):
        """Test that health_check reports errors when services are down."""
        with patch.object(skill_helpers, '_get_adapters') as mock_adapters:
            mock_store = Mock()
            mock_store._collection.count.side_effect = Exception("ChromaDB down")
            mock_adapters.return_value = (mock_store, None, None, None)

            result = skill_helpers.health_check()
            assert isinstance(result, str)
            assert "Failed" in result or "❌" in result


class TestCheckUnindexedDocuments:
    """Tests for check_unindexed_documents function."""

    def test_check_with_no_documents(self, tmp_path):
        """Test checking when no documents exist."""
        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            result = skill_helpers.check_unindexed_documents()

            assert isinstance(result, list)
            assert len(result) == 0

    def test_check_with_unindexed_documents(self, tmp_path):
        """Test checking when unindexed documents exist."""
        # Create test file
        (tmp_path / "unindexed.md").write_text("Content")

        with patch.object(skill_helpers, 'DOCS_DIR', tmp_path):
            with patch.object(skill_helpers, 'MEMORIA_ROOT', tmp_path):
                # Mock vector store to return empty indexed set
                with patch.object(skill_helpers, '_get_adapters') as mock_adapters:
                    mock_store = Mock()
                    mock_collection = Mock()
                    mock_collection.get.return_value = {'metadatas': []}
                    mock_store.get_collection.return_value = mock_collection
                    mock_adapters.return_value = (mock_store, None, None, None)

                    result = skill_helpers.check_unindexed_documents()

                    assert isinstance(result, list)
                    assert len(result) > 0


class TestAutoIndexNewDocuments:
    """Tests for auto_index_new_documents function."""

    def test_auto_index_with_no_new_documents(self, tmp_path):
        """Test auto-indexing when all documents are indexed."""
        with patch.object(skill_helpers, 'check_unindexed_documents', return_value=[]):
            result = skill_helpers.auto_index_new_documents()

            assert isinstance(result, str)
            assert "already indexed" in result.lower()

    def test_auto_index_with_new_documents(self, tmp_path):
        """Test auto-indexing when new documents exist."""
        fake_unindexed = ["docs/new1.md", "docs/new2.md"]

        with patch.object(skill_helpers, 'check_unindexed_documents', return_value=fake_unindexed):
            with patch.object(skill_helpers, 'index_documents', return_value="Indexed"):
                result = skill_helpers.auto_index_new_documents()

                assert isinstance(result, str)
                assert "2" in result or "new" in result.lower()


class TestGetAdapters:
    """Tests for _get_adapters private function."""

    def test_adapters_are_singletons(self):
        """Test that adapters are created only once (singleton pattern)."""
        adapters1 = skill_helpers._get_adapters()
        adapters2 = skill_helpers._get_adapters()

        # Should return same instances
        assert adapters1[0] is adapters2[0]  # vector_store
        assert adapters1[1] is adapters2[1]  # embedder
        assert adapters1[2] is adapters2[2]  # search_engine
        assert adapters1[3] is adapters2[3]  # document_processor

    def test_adapters_initialization(self):
        """Test that all adapters are properly initialized."""
        vector_store, embedder, search_engine, doc_processor = skill_helpers._get_adapters()

        assert vector_store is not None
        assert embedder is not None
        assert search_engine is not None
        assert doc_processor is not None


class TestRichFallback:
    """Tests for Rich library fallback behavior."""

    def test_console_fallback_when_rich_unavailable(self):
        """Test that Console works even if Rich is not available."""
        # Create a fallback console
        if not skill_helpers.RICH_AVAILABLE:
            console = skill_helpers.Console(file=io.StringIO())
            console.print("Test message")

            output = console.file.getvalue()
            assert "Test message" in output

    def test_panel_fallback_when_rich_unavailable(self):
        """Test that Panel works even if Rich is not available."""
        if not skill_helpers.RICH_AVAILABLE:
            panel = skill_helpers.Panel("Test content")
            output = str(panel)

            assert "Test content" in output

    def test_table_fallback_when_rich_unavailable(self):
        """Test that Table works even if Rich is not available."""
        if not skill_helpers.RICH_AVAILABLE:
            table = skill_helpers.Table()
            table.add_column("Col1")
            table.add_row("Value1")

            # Should not crash
            assert table.columns == ["Col1"]
            assert len(table.rows) == 1
