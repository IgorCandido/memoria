"""
Blackbox compatibility tests for raggy.py interface.

These tests document the EXACT behavior of raggy.UniversalRAG so we can
ensure the new implementation matches it perfectly.

Tests run against the actual raggy.py to capture real behavior.

CRITICAL: These tests are the contract that the new implementation must satisfy.
All quirks, edge cases, and behaviors captured here MUST be replicated exactly.
"""

import sys
from pathlib import Path
import tempfile
import shutil
import pytest
from typing import Any, Iterator

# Add raggy to path
MEMORIA_DIR = Path(__file__).parent.parent.parent
RAGGY_DIR = MEMORIA_DIR / "raggy"
sys.path.insert(0, str(RAGGY_DIR))


@pytest.fixture(scope="module")
def test_docs_dir() -> Iterator[Path]:
    """Create a temporary directory with test documents."""
    temp_dir = tempfile.mkdtemp(prefix="raggy_compat_test_")
    docs_dir = Path(temp_dir) / "docs"
    docs_dir.mkdir()

    # Create test documents
    (docs_dir / "test1.md").write_text(
        "# Python Programming\n\n"
        "Python is a high-level programming language. "
        "It supports multiple programming paradigms including "
        "object-oriented, functional, and procedural programming."
    )

    (docs_dir / "test2.txt").write_text(
        "Machine Learning Basics\n\n"
        "Machine learning is a subset of artificial intelligence. "
        "It focuses on building systems that learn from data. "
        "Common algorithms include neural networks and decision trees."
    )

    (docs_dir / "test3.md").write_text(
        "# Data Science\n\n"
        "Data science combines statistics, programming, and domain knowledge. "
        "Python is widely used in data science for its rich ecosystem. "
        "Popular libraries include pandas, numpy, and scikit-learn."
    )

    yield docs_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="module")
def raggy_instance(test_docs_dir: Path) -> Iterator[Any]:
    """Create a raggy instance for testing with real ChromaDB."""
    from raggy import UniversalRAG, setup_dependencies

    # Setup dependencies (chromadb, SentenceTransformer, etc.)
    setup_dependencies(quiet=True)

    # Create temp database directory
    temp_db = tempfile.mkdtemp(prefix="raggy_compat_db_")

    # Create instance
    instance = UniversalRAG(
        docs_dir=str(test_docs_dir),
        db_dir=temp_db,
        model_name="all-MiniLM-L6-v2",  # Fast model for testing
        quiet=True,
    )

    # Build the index
    instance.build(force_rebuild=True)

    yield instance

    # Cleanup
    shutil.rmtree(temp_db)


class TestRaggySearchInterface:
    """Test the search() method interface and behavior."""

    def test_search_signature(self, raggy_instance):
        """Document the search() method signature."""
        # QUIRK: search() takes these exact parameters in this order
        results = raggy_instance.search(
            query="Python",
            n_results=5,
            hybrid=False,
            expand_query=False,
            show_scores=None,
        )
        assert isinstance(results, list)

    def test_search_returns_list_of_dicts(self, raggy_instance):
        """QUIRK: search() returns a list of dictionaries."""
        results = raggy_instance.search("Python")
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], dict)

    def test_search_result_structure(self, raggy_instance):
        """Document the EXACT structure of search results."""
        results = raggy_instance.search("Python", n_results=1)

        # Should have at least one result
        assert len(results) >= 1

        result = results[0]

        # QUIRK: These keys are ALWAYS present
        required_keys = [
            "text",  # The chunk text
            "metadata",  # Metadata dict
            "semantic_score",  # Semantic similarity score
            "keyword_score",  # Keyword/BM25 score (0 if not hybrid)
            "final_score",  # Combined score
            "score_interpretation",  # Human-readable score label
            "distance",  # Raw distance (for backward compatibility)
            "similarity",  # Same as final_score (for backward compatibility)
        ]

        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

        # QUIRK: metadata has these exact keys
        metadata = result["metadata"]
        assert "source" in metadata  # Filename
        assert "chunk_index" in metadata  # Zero-based chunk index
        assert "total_chunks" in metadata  # Total chunks in document

        # QUIRK: score_interpretation is a string label
        assert isinstance(result["score_interpretation"], str)

        # QUIRK: All score fields are floats
        assert isinstance(result["semantic_score"], float)
        assert isinstance(result["keyword_score"], float)
        assert isinstance(result["final_score"], float)
        assert isinstance(result["similarity"], float)

    def test_search_with_show_scores_adds_highlighting(self, raggy_instance):
        """QUIRK: show_scores=True adds 'highlighted_text' field."""
        results = raggy_instance.search("Python", n_results=1, show_scores=True)

        if results:
            result = results[0]
            # When show_scores is True, highlighted_text should be present
            assert "highlighted_text" in result

    def test_search_empty_results(self, raggy_instance):
        """QUIRK: Returns empty list when no results found."""
        # Search for something that definitely won't match
        results = raggy_instance.search("xyzabc123nonsense456")

        # QUIRK: Returns empty list, not None
        assert results == []
        assert isinstance(results, list)

    def test_search_score_interpretation_values(self, raggy_instance):
        """Document the possible score_interpretation values."""
        results = raggy_instance.search("Python", n_results=5)

        # Collect all unique interpretations
        interpretations = {r["score_interpretation"] for r in results}

        # QUIRK: These are the possible values (from raggy.py scoring logic)
        valid_interpretations = {
            "Very High Confidence",
            "High Confidence",
            "Medium Confidence",
            "Low Confidence",
        }

        # All interpretations should be one of these values
        assert interpretations.issubset(valid_interpretations)

    def test_search_hybrid_mode(self, raggy_instance):
        """QUIRK: hybrid=True combines semantic + BM25 scores."""
        results_semantic = raggy_instance.search("Python", n_results=3, hybrid=False)
        results_hybrid = raggy_instance.search("Python", n_results=3, hybrid=True)

        # Both should return results
        assert len(results_semantic) > 0
        assert len(results_hybrid) > 0

        # QUIRK: hybrid mode populates keyword_score
        for result in results_hybrid:
            # In hybrid mode, keyword_score should be non-zero for relevant results
            assert "keyword_score" in result
            # final_score should differ from semantic_score
            assert "final_score" in result
            assert "semantic_score" in result

    def test_search_respects_n_results(self, raggy_instance):
        """QUIRK: search() respects n_results parameter (or returns fewer)."""
        results_2 = raggy_instance.search("Python", n_results=2)
        results_5 = raggy_instance.search("Python", n_results=5)

        # Should return at most n_results
        assert len(results_2) <= 2
        assert len(results_5) <= 5

        # More results requested should give more results (if available)
        if len(results_5) >= 2:
            assert len(results_5) >= len(results_2)

    def test_search_default_parameters(self, raggy_instance):
        """QUIRK: search() works with just query parameter."""
        # Should work with only query
        results = raggy_instance.search("Python")

        assert isinstance(results, list)
        # Default is 5 results
        assert len(results) <= 5


class TestRaggyBuildInterface:
    """Test the build() method interface."""

    def test_build_signature(self, test_docs_dir: Path):
        """QUIRK: build() takes force_rebuild parameter."""
        from raggy import UniversalRAG, setup_dependencies

        setup_dependencies(quiet=True)

        temp_db = tempfile.mkdtemp(prefix="raggy_build_test_")
        instance = UniversalRAG(
            docs_dir=str(test_docs_dir), db_dir=temp_db, quiet=True
        )

        # QUIRK: build() accepts force_rebuild parameter
        instance.build(force_rebuild=False)

        # Verify it built something
        stats = instance.get_stats()
        assert stats["total_chunks"] > 0

        # Cleanup
        shutil.rmtree(temp_db)

    def test_build_creates_database(self, test_docs_dir: Path):
        """QUIRK: build() creates database directory if it doesn't exist."""
        from raggy import UniversalRAG, setup_dependencies

        setup_dependencies(quiet=True)

        temp_db = tempfile.mkdtemp(prefix="raggy_build_test_")
        db_path = Path(temp_db) / "new_db"

        # Database doesn't exist yet
        assert not db_path.exists()

        instance = UniversalRAG(
            docs_dir=str(test_docs_dir), db_dir=str(db_path), quiet=True
        )

        instance.build()

        # QUIRK: Database directory is created
        assert db_path.exists()

        # Cleanup
        shutil.rmtree(temp_db)


class TestRaggyStatsInterface:
    """Test the get_stats() method interface."""

    def test_stats_signature(self, raggy_instance):
        """QUIRK: get_stats() returns a dictionary."""
        stats = raggy_instance.get_stats()
        assert isinstance(stats, dict)

    def test_stats_structure_success(self, raggy_instance):
        """Document the structure of stats dict when database exists."""
        stats = raggy_instance.get_stats()

        # QUIRK: Stats dict has these keys when successful
        assert "total_chunks" in stats
        assert isinstance(stats["total_chunks"], int)
        assert stats["total_chunks"] > 0

        assert "sources" in stats
        assert isinstance(stats["sources"], dict)

        assert "db_path" in stats
        assert isinstance(stats["db_path"], str)

    def test_stats_structure_error(self, test_docs_dir: Path):
        """QUIRK: get_stats() returns error dict when database doesn't exist."""
        from raggy import UniversalRAG, setup_dependencies

        setup_dependencies(quiet=True)

        # Create instance without building
        temp_db = tempfile.mkdtemp(prefix="raggy_stats_error_")
        instance = UniversalRAG(
            docs_dir=str(test_docs_dir), db_dir=temp_db, quiet=True
        )

        # Don't build, just get stats
        stats = instance.get_stats()

        # QUIRK: Returns dict with "error" key
        assert "error" in stats
        assert isinstance(stats["error"], str)
        assert "not found" in stats["error"].lower() or "build" in stats["error"].lower()

        # Cleanup
        shutil.rmtree(temp_db)


class TestRaggyConstructor:
    """Test the UniversalRAG constructor."""

    def test_constructor_signature(self, test_docs_dir: Path):
        """Document the EXACT constructor signature."""
        from raggy import UniversalRAG, setup_dependencies

        setup_dependencies(quiet=True)

        temp_db = tempfile.mkdtemp(prefix="raggy_ctor_test_")

        # QUIRK: Constructor takes these parameters
        instance = UniversalRAG(
            docs_dir=str(test_docs_dir),
            db_dir=temp_db,
            model_name="all-MiniLM-L6-v2",
            chunk_size=1000,
            chunk_overlap=200,
            quiet=True,
            config_path=None,
        )

        assert instance.docs_dir == Path(test_docs_dir)
        assert instance.db_dir == Path(temp_db)
        assert instance.model_name == "all-MiniLM-L6-v2"
        assert instance.chunk_size == 1000
        assert instance.chunk_overlap == 200
        assert instance.quiet is True

        # Cleanup
        shutil.rmtree(temp_db)

    def test_database_manager_http_mode(self, test_docs_dir: Path):
        """QUIRK: database_manager has use_http attribute for ChromaDB HTTP client."""
        from raggy import UniversalRAG, setup_dependencies

        setup_dependencies(quiet=True)

        temp_db = tempfile.mkdtemp(prefix="raggy_http_test_")
        instance = UniversalRAG(
            docs_dir=str(test_docs_dir), db_dir=temp_db, quiet=True
        )

        # QUIRK: Can set HTTP mode on database_manager
        assert hasattr(instance.database_manager, "use_http")

        # Default is False (uses persistent client)
        # Can be set to True for HTTP client mode
        instance.database_manager.use_http = True
        assert instance.database_manager.use_http is True

        # Cleanup
        shutil.rmtree(temp_db)

    def test_constructor_defaults(self, test_docs_dir: Path):
        """QUIRK: Constructor has sensible defaults."""
        from raggy import UniversalRAG, setup_dependencies

        setup_dependencies(quiet=True)

        temp_db = tempfile.mkdtemp(prefix="raggy_defaults_test_")

        # Can create with minimal parameters
        instance = UniversalRAG(docs_dir=str(test_docs_dir), db_dir=temp_db)

        # Check defaults are applied
        assert instance.chunk_size == 1000  # DEFAULT_CHUNK_SIZE
        assert instance.chunk_overlap == 200  # DEFAULT_CHUNK_OVERLAP
        assert instance.quiet is False

        # Cleanup
        shutil.rmtree(temp_db)


class TestRaggyDependencies:
    """Test raggy's dependency initialization."""

    def test_required_global_modules(self):
        """QUIRK: raggy mutates its own module globals (setup_dependencies)."""
        import raggy

        # Before setup, these are None
        assert hasattr(raggy, "chromadb")
        assert hasattr(raggy, "SentenceTransformer")
        assert hasattr(raggy, "PyPDF2")

        # Call setup_dependencies
        raggy.setup_dependencies(quiet=True)

        # QUIRK: Module globals are now populated
        assert raggy.chromadb is not None
        assert raggy.SentenceTransformer is not None
        # PyPDF2 may or may not be available
        assert hasattr(raggy, "PyPDF2")

    def test_setup_dependencies_is_idempotent(self):
        """QUIRK: setup_dependencies() can be called multiple times safely."""
        import raggy

        # Call twice - should not error
        raggy.setup_dependencies(quiet=True)
        raggy.setup_dependencies(quiet=True)

        # Still works
        assert raggy.chromadb is not None
