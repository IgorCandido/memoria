"""
Unit tests for CompatibilityErrorMapper.

These tests verify that domain errors are correctly translated
to raggy.py's inconsistent error formats.

⚠️ These tests document BAD patterns that exist only for compatibility.
"""

import pytest

from memoria.compatibility.error_mapper import CompatibilityErrorMapper
from memoria.domain.errors import (
    DatabaseNotBuiltError,
    DatabaseCorruptedError,
    DocumentNotFoundError,
    UnsupportedFormatError,
    DocumentExtractionError,
    SearchError,
    EmptyQueryError,
    EmbeddingGenerationError,
    VectorStoreError,
    VectorStoreConnectionError,
    VectorStoreQueryError,
    CollectionNotFoundError,
    EmbeddingError,
    ModelLoadError,
    TextTooLongError,
)


class TestMapGetStatsError:
    """Test error mapping for get_stats() method."""

    def test_database_not_built_error(self):
        """DatabaseNotBuiltError → specific error dict."""
        error = DatabaseNotBuiltError()
        result = CompatibilityErrorMapper.map_get_stats_error(error)

        assert result == {"error": "Database not built. Call build() first."}
        assert isinstance(result, dict)
        assert "error" in result

    def test_database_not_built_custom_message(self):
        """DatabaseNotBuiltError with custom message → uses custom message."""
        error = DatabaseNotBuiltError("Custom message here")
        result = CompatibilityErrorMapper.map_get_stats_error(error)

        # Mapper uses exact error message
        assert result == {"error": "Custom message here"}

    def test_database_corrupted_error(self):
        """DatabaseCorruptedError → error dict with prefix."""
        error = DatabaseCorruptedError("Invalid SQLite header")
        result = CompatibilityErrorMapper.map_get_stats_error(error)

        assert result == {"error": "Database corrupted: Invalid SQLite header"}
        assert "corrupted" in result["error"]

    def test_vector_store_error(self):
        """VectorStoreError → error dict with prefix."""
        error = VectorStoreQueryError("ChromaDB connection failed")
        result = CompatibilityErrorMapper.map_get_stats_error(error)

        assert result == {"error": "Failed to get stats: ChromaDB connection failed"}
        assert "Failed to get stats" in result["error"]

    def test_unexpected_error_includes_type(self):
        """Unexpected error → error dict with type name."""
        error = ValueError("Something unexpected")
        result = CompatibilityErrorMapper.map_get_stats_error(error)

        assert "ValueError" in result["error"]
        assert "Something unexpected" in result["error"]
        assert result["error"].startswith("Unexpected error (ValueError)")

    def test_all_results_are_dicts(self):
        """All mapped errors return dict (never raise)."""
        errors = [
            DatabaseNotBuiltError(),
            DatabaseCorruptedError("test"),
            VectorStoreError("test"),
            ValueError("test"),
        ]

        for error in errors:
            result = CompatibilityErrorMapper.map_get_stats_error(error)
            assert isinstance(result, dict), f"Failed for {type(error).__name__}"
            assert "error" in result, f"No 'error' key for {type(error).__name__}"


class TestMapSearchError:
    """Test error mapping for search() method."""

    def test_empty_query_error(self):
        """EmptyQueryError → empty list (raggy quirk)."""
        error = EmptyQueryError("Query cannot be empty")
        result = CompatibilityErrorMapper.map_search_error(error)

        # RAGGY QUIRK: Returns empty list, not error dict
        assert result == []
        assert isinstance(result, list)

    def test_embedding_generation_error(self):
        """EmbeddingGenerationError → empty list."""
        error = EmbeddingGenerationError("Model loading failed")
        result = CompatibilityErrorMapper.map_search_error(error)

        assert result == []

    def test_vector_store_error(self):
        """VectorStoreError → empty list."""
        error = VectorStoreQueryError("Database locked")
        result = CompatibilityErrorMapper.map_search_error(error)

        assert result == []

    def test_all_errors_return_empty_list(self):
        """All search errors map to empty list (loses error context!)."""
        errors = [
            EmptyQueryError(),
            EmbeddingGenerationError("test"),
            VectorStoreError("test"),
            ModelLoadError("test"),
        ]

        for error in errors:
            result = CompatibilityErrorMapper.map_search_error(error)
            assert result == [], f"Failed for {type(error).__name__}"
            assert isinstance(result, list)


class TestMapBuildError:
    """Test error mapping for build() method."""

    def test_document_not_found_prints_warning(self, capsys):
        """DocumentNotFoundError → prints warning, returns None."""
        error = DocumentNotFoundError("file.txt not found")
        result = CompatibilityErrorMapper.map_build_error(error)

        # Returns None (raggy.py silent failure)
        assert result is None

        # Prints warning to stdout
        captured = capsys.readouterr()
        assert "Warning:" in captured.out
        assert "file.txt not found" in captured.out

    def test_unsupported_format_prints_warning(self, capsys):
        """UnsupportedFormatError → prints warning, returns None."""
        error = UnsupportedFormatError("Unsupported file format: .xyz")
        result = CompatibilityErrorMapper.map_build_error(error)

        assert result is None
        captured = capsys.readouterr()
        assert "Warning:" in captured.out
        assert ".xyz" in captured.out

    def test_document_extraction_error_prints_warning(self, capsys):
        """DocumentExtractionError → prints warning, returns None."""
        error = DocumentExtractionError("PDF corrupted")
        result = CompatibilityErrorMapper.map_build_error(error)

        assert result is None
        captured = capsys.readouterr()
        assert "Warning:" in captured.out
        assert "Failed to extract text" in captured.out
        assert "PDF corrupted" in captured.out

    def test_generic_error_prints_warning(self, capsys):
        """Generic error → prints generic warning."""
        error = ValueError("Something went wrong")
        result = CompatibilityErrorMapper.map_build_error(error)

        assert result is None
        captured = capsys.readouterr()
        assert "Warning: Build error" in captured.out
        assert "Something went wrong" in captured.out


class TestShouldFilterError:
    """Test error filtering logic."""

    def test_document_extraction_error_is_filterable(self):
        """DocumentExtractionError should be filtered (raggy continues on failure)."""
        error = DocumentExtractionError("PDF corrupted")
        assert CompatibilityErrorMapper.should_filter_error(error) is True

    def test_unsupported_format_is_filterable(self):
        """UnsupportedFormatError should be filtered (raggy skips file)."""
        error = UnsupportedFormatError("Bad format")
        assert CompatibilityErrorMapper.should_filter_error(error) is True

    def test_database_corrupted_not_filterable(self):
        """DatabaseCorruptedError should NOT be filtered (must stop)."""
        error = DatabaseCorruptedError("Database corrupted")
        assert CompatibilityErrorMapper.should_filter_error(error) is False

    def test_vector_store_error_not_filterable(self):
        """VectorStoreError should NOT be filtered (critical failure)."""
        error = VectorStoreConnectionError("Connection failed")
        assert CompatibilityErrorMapper.should_filter_error(error) is False

    def test_search_error_not_filterable(self):
        """SearchError should NOT be filtered (user needs to know)."""
        error = EmptyQueryError()
        assert CompatibilityErrorMapper.should_filter_error(error) is False


class TestErrorMapperContract:
    """Test the overall error mapper contract."""

    def test_get_stats_never_raises(self):
        """map_get_stats_error() must never raise - always returns dict."""
        errors = [
            DatabaseNotBuiltError(),
            DatabaseCorruptedError("test"),
            VectorStoreError("test"),
            ValueError("unexpected"),
            Exception("unknown"),
        ]

        for error in errors:
            try:
                result = CompatibilityErrorMapper.map_get_stats_error(error)
                assert isinstance(result, dict)
                assert "error" in result
            except Exception as e:
                pytest.fail(f"map_get_stats_error raised for {type(error).__name__}: {e}")

    def test_search_never_raises(self):
        """map_search_error() must never raise - always returns list."""
        errors = [
            EmptyQueryError(),
            EmbeddingGenerationError("test"),
            VectorStoreError("test"),
            ValueError("unexpected"),
        ]

        for error in errors:
            try:
                result = CompatibilityErrorMapper.map_search_error(error)
                assert isinstance(result, list)
                assert result == []
            except Exception as e:
                pytest.fail(f"map_search_error raised for {type(error).__name__}: {e}")

    def test_build_never_raises(self):
        """map_build_error() must never raise - always returns None."""
        errors = [
            DocumentNotFoundError("test"),
            UnsupportedFormatError("test"),
            DocumentExtractionError("test"),
            ValueError("unexpected"),
        ]

        for error in errors:
            try:
                result = CompatibilityErrorMapper.map_build_error(error)
                assert result is None
            except Exception as e:
                pytest.fail(f"map_build_error raised for {type(error).__name__}: {e}")

    def test_error_messages_preserved(self):
        """Error messages should be preserved in mapped output."""
        test_message = "This is a specific error message"

        # get_stats preserves message
        error1 = DatabaseNotBuiltError(test_message)
        result1 = CompatibilityErrorMapper.map_get_stats_error(error1)
        assert test_message in result1["error"]

        # build preserves message (in stdout)
        # search loses message (returns empty list) - documented quirk
