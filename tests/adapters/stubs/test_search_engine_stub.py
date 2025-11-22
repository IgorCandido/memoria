"""Test that SearchEngineStub passes all SearchEnginePortTests."""

from memoria.adapters.stubs.search_engine_stub import SearchEngineStub
from memoria.domain.entities import Document
from memoria.domain.ports.search_engine import SearchEnginePort
from tests.ports.test_search_engine_port import SearchEnginePortTests


class TestSearchEngineStub(SearchEnginePortTests):
    """
    Test SearchEngineStub implementation.

    By inheriting from SearchEnginePortTests, this stub automatically
    runs all 11 port tests to ensure it behaves correctly.
    """

    def create_engine(self) -> SearchEnginePort:
        """Create a SearchEngineStub instance for testing."""
        return SearchEngineStub()

    def index_test_documents(self, engine: SearchEnginePort) -> None:
        """Index some test documents for the stub to search."""
        # Downcast to access stub-specific method
        if isinstance(engine, SearchEngineStub):
            test_docs = [
                Document(
                    id="doc1",
                    content="Python programming language tutorial",
                    metadata={"topic": "programming"},
                    embedding=[0.1] * 4,
                ),
                Document(
                    id="doc2",
                    content="Java programming basics",
                    metadata={"topic": "programming"},
                    embedding=[0.2] * 4,
                ),
                Document(
                    id="doc3",
                    content="Machine learning algorithms",
                    metadata={"topic": "ml"},
                    embedding=[0.3] * 4,
                ),
            ]
            engine.index_documents(test_docs)
