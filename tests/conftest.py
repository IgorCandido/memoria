"""
Root pytest configuration.

Redirects imports from legacy raggy.py to new facade for testing.
"""

import sys
import pytest


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
