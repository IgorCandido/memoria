"""
Compatibility error mapper for raggy.py interface.

⚠️ THIS IS A HACK LAYER ⚠️

This module exists SOLELY to match the broken error handling in raggy.py.
The legacy raggy.py has inconsistent error handling:
- Sometimes returns {"error": "message"} dicts
- Sometimes raises exceptions
- Sometimes silently fails

This mapper translates clean, typed domain errors from the new implementation
into raggy.py's messy format for backward compatibility.

DO NOT USE THIS PATTERN IN NEW CODE.

This layer will be removed in v4.0.0 when raggy.py compatibility is dropped.
"""

from typing import Any, Dict, Optional

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
    MemoriaError,
)


class CompatibilityErrorMapper:
    """
    Maps domain errors to raggy.py's inconsistent error formats.

    This class is heavily documented because we're intentionally matching
    BAD patterns for backward compatibility.
    """

    @staticmethod
    def map_get_stats_error(error: Exception) -> Dict[str, Any]:
        """
        Map errors from get_stats() to raggy.py format.

        RAGGY QUIRK: get_stats() returns {"error": "message"} instead of raising.

        Why: Legacy raggy.py users expect error dicts, not exceptions.
        When: Only for get_stats() - other methods raise normally.
        Remove: v4.0.0 when raggy.py is dropped.

        Args:
            error: The domain error that occurred

        Returns:
            Error dict in raggy.py format: {"error": "message"}

        Examples:
            >>> mapper.map_get_stats_error(DatabaseNotBuiltError())
            {"error": "Database not built. Call build() first."}

            >>> mapper.map_get_stats_error(VectorStoreQueryError("DB corrupt"))
            {"error": "Failed to get stats: DB corrupt"}
        """
        if isinstance(error, DatabaseNotBuiltError):
            # RAGGY QUIRK: Return error dict instead of raising
            # Use the actual error message (preserves custom messages)
            return {"error": str(error)}

        elif isinstance(error, DatabaseCorruptedError):
            return {"error": f"Database corrupted: {str(error)}"}

        elif isinstance(error, VectorStoreError):
            return {"error": f"Failed to get stats: {str(error)}"}

        else:
            # Unexpected error - include type for debugging
            return {"error": f"Unexpected error ({type(error).__name__}): {str(error)}"}

    @staticmethod
    def map_search_error(error: Exception) -> list:
        """
        Map errors from search() to raggy.py format.

        RAGGY QUIRK: search() returns empty list [] for failures, not error dicts.

        Why: Inconsistent with get_stats(), but that's how raggy.py works.
        When: Only when search fails (not when results are empty naturally).
        Remove: v4.0.0 when raggy.py is dropped.

        Args:
            error: The domain error that occurred

        Returns:
            Empty list (raggy.py's way of indicating search failure)

        Examples:
            >>> mapper.map_search_error(EmptyQueryError())
            []

            >>> mapper.map_search_error(EmbeddingGenerationError())
            []

        Note:
            This silently swallows errors, which is terrible practice.
            We do this ONLY for raggy.py compatibility.
            The new implementation should raise these errors properly.
        """
        # RAGGY QUIRK: All search errors return empty list
        # This loses error context, but matches legacy behavior
        return []

    @staticmethod
    def map_build_error(error: Exception) -> None:
        """
        Map errors from build() to raggy.py format.

        RAGGY QUIRK: build() silently fails and prints warnings.

        Why: Legacy raggy.py doesn't raise on build failures.
        When: Document extraction errors, missing files, etc.
        Remove: v4.0.0 when raggy.py is dropped.

        Args:
            error: The domain error that occurred

        Returns:
            None (build() returns None in raggy.py, even on failure)

        Side Effects:
            Prints warning message to stdout (raggy.py behavior)

        Examples:
            >>> mapper.map_build_error(DocumentNotFoundError("file.txt"))
            # Prints: "Warning: file.txt not found"
            # Returns: None

            >>> mapper.map_build_error(UnsupportedFormatError(".xyz"))
            # Prints: "Warning: Unsupported file format: .xyz"
            # Returns: None

        Note:
            This silently swallows build errors, which is terrible.
            Users don't know if build() succeeded or failed.
            We do this ONLY for raggy.py compatibility.
        """
        if isinstance(error, DocumentNotFoundError):
            print(f"Warning: {str(error)}")

        elif isinstance(error, UnsupportedFormatError):
            print(f"Warning: {str(error)}")

        elif isinstance(error, DocumentExtractionError):
            print(f"Warning: Failed to extract text - {str(error)}")

        else:
            print(f"Warning: Build error - {str(error)}")

        # RAGGY QUIRK: Return None even on failure
        return None

    @staticmethod
    def should_filter_error(error: Exception) -> bool:
        """
        Determine if an error should be filtered (not raised).

        Some errors in raggy.py are silently ignored during operations.
        This method identifies which errors to swallow.

        Args:
            error: The exception to check

        Returns:
            True if error should be filtered, False if it should propagate

        Examples:
            >>> mapper.should_filter_error(DocumentExtractionError())
            True  # raggy.py continues on extraction failures

            >>> mapper.should_filter_error(DatabaseCorruptedError())
            False  # This should stop execution
        """
        # Errors that raggy.py silently ignores:
        # - Individual document extraction failures (continues with other docs)
        # - Unsupported file formats (skips the file)
        filterable_errors = (
            DocumentExtractionError,
            UnsupportedFormatError,
        )

        return isinstance(error, filterable_errors)
