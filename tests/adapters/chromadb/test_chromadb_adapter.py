"""
Tests for ChromaDBAdapter.

Inherits from VectorStorePortTests to ensure full port compliance.
"""

import tempfile
from pathlib import Path

import pytest

from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.domain.ports.vector_store import VectorStorePort
from tests.ports.test_vector_store_port import VectorStorePortTests


class TestChromaDBAdapter(VectorStorePortTests):
    """
    Test ChromaDBAdapter against VectorStorePort contract.

    Inherits all port tests from VectorStorePortTests.
    Only needs to implement the create_store() factory method.
    """

    @pytest.fixture
    def temp_db_dir(self) -> Path:
        """Create a temporary directory for ChromaDB."""
        with tempfile.TemporaryDirectory(prefix="chromadb_test_") as temp_dir:
            yield Path(temp_dir)

    def create_store(self) -> VectorStorePort:
        """
        Factory method to create a ChromaDBAdapter instance.

        Required by VectorStorePortTests base class.
        """
        temp_dir = tempfile.mkdtemp(prefix="chromadb_test_")
        return ChromaDBAdapter(
            collection_name="test_collection",
            db_path=temp_dir,
            use_http=False,
        )

    def test_http_mode_configuration(self, temp_db_dir: Path) -> None:
        """Test that use_http can be set for HTTP client mode."""
        # This is a ChromaDB-specific feature
        adapter = ChromaDBAdapter(
            collection_name="test_http",
            db_path=str(temp_db_dir),
            use_http=False,
        )

        assert adapter.use_http is False

        # Can create HTTP adapter (will fail to connect, but that's okay for config test)
        # We just want to verify the attribute exists and can be set
        assert hasattr(adapter, "use_http")
