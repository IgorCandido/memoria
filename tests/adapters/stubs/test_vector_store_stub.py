"""Test that VectorStoreStub passes all VectorStorePortTests."""

from memoria.adapters.stubs.vector_store_stub import VectorStoreStub
from memoria.domain.ports.vector_store import VectorStorePort
from tests.ports.test_vector_store_port import VectorStorePortTests


class TestVectorStoreStub(VectorStorePortTests):
    """
    Test VectorStoreStub implementation.

    By inheriting from VectorStorePortTests, this stub automatically
    runs all 14 port tests to ensure it behaves correctly.
    """

    def create_store(self) -> VectorStorePort:
        """Create a VectorStoreStub instance for testing."""
        return VectorStoreStub()
