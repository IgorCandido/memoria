"""
Pytest configuration for compatibility tests.

Override fixtures to test the new implementation instead of raggy.py.
"""

import tempfile
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest


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
    """
    Create a raggy instance for testing.

    This fixture uses the NEW implementation (src.compatibility.raggy_facade)
    instead of the old raggy.py to verify backward compatibility.
    """
    from memoria.compatibility.raggy_facade import UniversalRAG, setup_dependencies

    # Setup dependencies
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
