"""
Root pytest configuration.

Redirects imports from legacy raggy.py to new facade for testing.
Provides --run-integration flag to enable integration tests against real services.
"""

import sys
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --run-integration flag to enable integration tests."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests requiring real services (Postgres/ChromaDB on relishhost1, Ollama on relishhost2)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless --run-integration flag is passed."""
    if not config.getoption("--run-integration"):
        skip_mark = pytest.mark.skip(
            reason="Requires --run-integration flag and running infrastructure on relishhost1/relishhost2"
        )
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip_mark)


@pytest.fixture(scope="session", autouse=True)
def redirect_raggy_imports():
    """
    Automatically redirect all 'from raggy import' statements to use the new facade.

    This ensures compatibility tests run against the new implementation
    instead of the legacy raggy.py.
    """
    # Import the facade module
    from memoria.compatibility import raggy_facade

    # Create a fake raggy module that exports the facade's classes
    import types
    fake_raggy = types.ModuleType("raggy")
    fake_raggy.UniversalRAG = raggy_facade.UniversalRAG
    fake_raggy.setup_dependencies = raggy_facade.setup_dependencies

    # Add global modules that tests check for (backward compatibility)
    try:
        import chromadb
        fake_raggy.chromadb = chromadb
    except ImportError:
        fake_raggy.chromadb = None

    try:
        from sentence_transformers import SentenceTransformer
        fake_raggy.SentenceTransformer = SentenceTransformer
    except ImportError:
        fake_raggy.SentenceTransformer = None

    try:
        import PyPDF2
        fake_raggy.PyPDF2 = PyPDF2
    except ImportError:
        fake_raggy.PyPDF2 = None

    # Insert into sys.modules BEFORE tests run
    sys.modules["raggy"] = fake_raggy

    yield

    # Cleanup (though not strictly necessary for tests)
    if "raggy" in sys.modules:
        del sys.modules["raggy"]
