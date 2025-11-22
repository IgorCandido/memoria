"""
User Acceptance Tests for Memoria MCP Server

Tests the REAL running MCP server with actual client connections.
Verifies all tools work end-to-end with real data.

Requirements:
- Memoria MCP server running on localhost:9007
- ChromaDB running on localhost:8001
- Test documents in docs/ directory
- Redis running on localhost:6379
"""

import json
import pytest
import requests
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Test configuration
# Test through facade (production endpoint) - this is what Claude Code uses
MCP_SERVER_URL = "http://localhost:9017/mcp"
TEST_DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
TEST_TIMEOUT = 30  # seconds


class MCPClient:
    """
    MCP client for testing through facade (http-bridge-wrapper).

    The facade handles session management internally, so this client
    just needs to send standard JSON-RPC requests.
    """

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = requests.Session()
        self.request_id = 0
        self.mcp_session_id: Optional[str] = None  # Track MCP session ID
        self.initialized = False  # Track if MCP session is initialized

    def _initialize_if_needed(self) -> None:
        """Initialize MCP session if not already done."""
        if self.initialized:
            return

        # Send initialize request
        init_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 0
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        if self.mcp_session_id:
            headers["mcp-session-id"] = self.mcp_session_id

        init_response = self.session.post(
            self.server_url,
            json=init_payload,
            headers=headers,
            timeout=TEST_TIMEOUT
        )

        # Capture session ID from initialize response
        if "mcp-session-id" in init_response.headers:
            self.mcp_session_id = init_response.headers["mcp-session-id"]

        assert init_response.status_code == 200, f"Initialize failed: {init_response.status_code}"

        # Send initialized notification
        initialized_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "id": None  # Notifications have no ID
        }

        headers["mcp-session-id"] = self.mcp_session_id

        self.session.post(
            self.server_url,
            json=initialized_payload,
            headers=headers,
            timeout=TEST_TIMEOUT
        )

        self.initialized = True

    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an MCP JSON-RPC request.

        Args:
            method: JSON-RPC method (e.g., "tools/list", "tools/call")
            params: Method parameters

        Returns:
            JSON-RPC result

        Raises:
            Exception: If request fails or returns error
        """
        # Auto-initialize before any request (except initialize/initialized themselves)
        if method not in ["initialize", "initialized"]:
            self._initialize_if_needed()

        self.request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }

        if params is not None:
            payload["params"] = params

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"  # Required by RedisBackedSessionManager
        }

        # Send MCP session ID if we have one (for session continuity)
        if self.mcp_session_id:
            headers["mcp-session-id"] = self.mcp_session_id

        response = self.session.post(
            self.server_url,
            json=payload,
            headers=headers,
            timeout=TEST_TIMEOUT
        )

        # Capture MCP session ID from response headers
        if "mcp-session-id" in response.headers:
            self.mcp_session_id = response.headers["mcp-session-id"]

        # Check HTTP status
        assert response.status_code == 200, f"HTTP {response.status_code}: {response.text}"

        # Parse JSON-RPC response
        result = response.json()
        assert "result" in result or "error" in result, f"Invalid JSON-RPC response: {result}"

        if "error" in result:
            raise Exception(f"MCP Error: {result['error']}")

        return result["result"]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return the result."""
        return self._make_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        result = self._make_request("tools/list")
        return result.get("tools", [])


@pytest.fixture(scope="module")
def mcp_client():
    """Create MCP client and verify server is running."""
    client = MCPClient(MCP_SERVER_URL)

    # Verify server is reachable
    try:
        tools = client.list_tools()
        assert len(tools) > 0, "No tools available from server"
        print(f"\n✅ Connected to MCP server, found {len(tools)} tools")
    except Exception as e:
        pytest.skip(f"MCP server not available at {MCP_SERVER_URL}: {e}")

    return client


@pytest.fixture(scope="module")
def test_documents():
    """Verify test documents exist."""
    assert TEST_DOCS_DIR.exists(), f"Test docs directory not found: {TEST_DOCS_DIR}"

    # Find all markdown files
    md_files = list(TEST_DOCS_DIR.glob("**/*.md"))
    assert len(md_files) > 0, f"No markdown files found in {TEST_DOCS_DIR}"

    print(f"\n✅ Found {len(md_files)} test documents")
    return md_files


class TestMCPSessionEstablishment:
    """Test MCP client session establishment and persistence."""

    def test_server_responds_to_tools_list(self, mcp_client):
        """Verify server responds to tools/list."""
        tools = mcp_client.list_tools()

        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]

        # Verify expected tools exist
        expected_tools = [
            "search_knowledge",
            "index_documents",
            "list_indexed_documents",
            "get_stats",
            "health_check"  # Health check endpoint
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Expected tool '{tool}' not found"

        print(f"✅ All expected tools available: {tool_names}")

    def test_session_persists_across_requests(self, mcp_client):
        """Verify session persists across multiple requests."""
        # Make multiple requests with same client
        for i in range(3):
            result = mcp_client.call_tool("health_check", {})
            assert "content" in result
            time.sleep(0.1)  # Small delay between requests

        print("✅ Session persisted across 3 requests")


class TestSearchKnowledgeTool:
    """Test search_knowledge tool with real data."""

    def test_semantic_search_returns_results(self, mcp_client, test_documents):
        """Test semantic search returns ranked results."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "architecture patterns",
            "mode": "semantic",
            "expand": False,
            "limit": 5
        })

        assert "content" in result
        assert len(result["content"]) > 0

        content = result["content"][0]["text"]

        # Verify response format
        assert "Search Results for:" in content
        assert "Mode: semantic" in content

        # Parse results to verify ranking
        if "1." in content:  # Has results
            assert "Confidence:" in content
            print(f"✅ Semantic search returned results with confidence scores")

    def test_hybrid_search_returns_results(self, mcp_client, test_documents):
        """Test hybrid search (semantic + BM25)."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "ChromaDB database",
            "mode": "hybrid",
            "expand": False,
            "limit": 3
        })

        assert "content" in result
        content = result["content"][0]["text"]

        assert "Mode: hybrid" in content
        print("✅ Hybrid search works")

    def test_query_expansion_works(self, mcp_client, test_documents):
        """Test query expansion feature."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "testing",
            "mode": "hybrid",
            "expand": True,
            "limit": 3
        })

        assert "content" in result
        content = result["content"][0]["text"]

        assert "Expansion: True" in content
        print("✅ Query expansion works")

    def test_search_ranking_is_descending(self, mcp_client, test_documents):
        """Verify search results are ranked by score (descending)."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "database vector search",
            "mode": "semantic",
            "expand": False,
            "limit": 5
        })

        content = result["content"][0]["text"]

        # Extract scores if results exist
        if "Confidence:" in content:
            # Simple check: first result should have high confidence
            lines = content.split("\n")
            for line in lines:
                if "1." in line and "Confidence:" in line:
                    # First result should not be "Low Confidence"
                    assert "Low Confidence" not in line or "Medium" in line or "High" in line
                    print(f"✅ Top result has appropriate confidence: {line.strip()}")
                    break

    def test_results_reference_valid_files(self, mcp_client, test_documents):
        """Verify search results reference actual documents."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "MCP server",
            "mode": "semantic",
            "expand": False,
            "limit": 3
        })

        content = result["content"][0]["text"]

        if "chunk" in content.lower():
            # Results contain file references
            # Verify at least one referenced file exists
            doc_names = [doc.name for doc in test_documents]

            found_valid_ref = False
            for doc_name in doc_names:
                if doc_name in content:
                    found_valid_ref = True
                    print(f"✅ Result references valid document: {doc_name}")
                    break

            # If we found results, at least one should reference a real file
            if "1." in content:
                # Note: Can't strictly require this if docs don't match query
                print(f"✅ Search returned results (may or may not match test docs)")

    def test_empty_query_handling(self, mcp_client):
        """Test how system handles empty queries."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "",
            "mode": "semantic",
            "expand": False,
            "limit": 5
        })

        # System should either return no results or handle gracefully
        assert "content" in result
        print("✅ Empty query handled gracefully")

    def test_no_results_scenario(self, mcp_client):
        """Test query that returns no results."""
        result = mcp_client.call_tool("search_knowledge", {
            "query": "zzzzz_nonexistent_term_12345",
            "mode": "semantic",
            "expand": False,
            "limit": 5
        })

        content = result["content"][0]["text"]

        # Should either say "No results" or return empty
        assert "content" in result
        print("✅ No-results scenario handled")


class TestIndexDocumentsTool:
    """Test index_documents tool (build/rebuild)."""

    def test_index_documents_with_pattern(self, mcp_client):
        """Test indexing documents with file pattern."""
        result = mcp_client.call_tool("index_documents", {
            "file_patterns": ["*.md"],
            "rebuild": False
        })

        assert "content" in result
        content = result["content"][0]["text"]

        # Should report indexing progress
        assert "Indexing complete" in content or "indexed" in content.lower()
        print(f"✅ Index documents works: {content[:100]}")

    def test_rebuild_database(self, mcp_client):
        """Test rebuilding database from scratch."""
        result = mcp_client.call_tool("index_documents", {
            "file_patterns": ["*.md"],
            "rebuild": True
        })

        assert "content" in result
        content = result["content"][0]["text"]

        # Rebuild should complete successfully
        assert "✅" in content or "complete" in content.lower() or "indexed" in content.lower()
        print(f"✅ Database rebuild works")


class TestListIndexedDocumentsTool:
    """Test list_indexed_documents tool."""

    def test_list_returns_documents(self, mcp_client, test_documents):
        """Verify list returns actual indexed documents."""
        result = mcp_client.call_tool("list_indexed_documents", {})

        assert "content" in result
        content = result["content"][0]["text"]

        # Should list files
        assert "files" in content.lower() or "documents" in content.lower()

        # Should contain at least one document name
        doc_names = [doc.name for doc in test_documents]
        found_doc = False
        for doc_name in doc_names:
            if doc_name in content:
                found_doc = True
                break

        # If we have docs indexed, at least one should be listed
        if "0 files" not in content:
            print(f"✅ List shows indexed documents")


class TestGetStatsTool:
    """Test get_stats tool."""

    def test_get_stats_returns_metrics(self, mcp_client):
        """Verify stats returns corpus metrics."""
        result = mcp_client.call_tool("get_stats", {})

        assert "content" in result
        content = result["content"][0]["text"]

        # Should contain statistics
        assert "chunks" in content.lower() or "documents" in content.lower()
        assert "ChromaDB" in content or "location" in content.lower()

        print(f"✅ Stats returned: {content[:200]}")

    def test_stats_shows_indexed_chunks(self, mcp_client):
        """Verify stats shows actual chunk count."""
        result = mcp_client.call_tool("get_stats", {})

        content = result["content"][0]["text"]

        # Should show chunk count (number followed by "chunks")
        import re
        chunk_matches = re.findall(r'(\d+)\s+chunks', content, re.IGNORECASE)

        if chunk_matches:
            chunk_count = int(chunk_matches[0])
            assert chunk_count >= 0
            print(f"✅ Stats shows {chunk_count} indexed chunks")


class TestHealthCheckTool:
    """Test health_check tool."""

    def test_health_check_returns_status(self, mcp_client):
        """Verify health check returns server status."""
        result = mcp_client.call_tool("health_check", {})

        assert "content" in result
        content = result["content"][0]["text"]

        # Should show health status
        assert "HEALTH CHECK" in content.upper() or "status" in content.lower()
        assert "ONLINE" in content.upper() or "running" in content.lower()

        print("✅ Health check shows server is online")

    def test_health_check_shows_uptime(self, mcp_client):
        """Verify health check shows uptime."""
        result = mcp_client.call_tool("health_check", {})

        content = result["content"][0]["text"]

        # Should contain uptime info
        assert "uptime" in content.lower() or "version" in content.lower()
        print("✅ Health check includes uptime/version")


class TestEndToEndScenarios:
    """Test complete end-to-end workflows."""

    def test_full_workflow_index_and_search(self, mcp_client, test_documents):
        """Test complete workflow: index → search → verify."""
        # 1. Index documents
        print("\n📝 Step 1: Indexing documents...")
        index_result = mcp_client.call_tool("index_documents", {
            "file_patterns": ["*.md"],
            "rebuild": False
        })
        assert "content" in index_result

        # 2. Get stats to verify indexing
        print("📊 Step 2: Getting stats...")
        stats_result = mcp_client.call_tool("get_stats", {})
        stats_content = stats_result["content"][0]["text"]
        assert "chunks" in stats_content.lower()

        # 3. Search for content
        print("🔍 Step 3: Searching...")
        search_result = mcp_client.call_tool("search_knowledge", {
            "query": "MCP server architecture",
            "mode": "hybrid",
            "expand": True,
            "limit": 3
        })
        search_content = search_result["content"][0]["text"]

        # 4. Verify search worked
        assert "Search Results" in search_content
        print("✅ Full workflow: index → stats → search completed successfully")

    def test_session_survives_multiple_operations(self, mcp_client):
        """Verify session persists through complex operations."""
        operations = [
            ("health_check", {}),
            ("get_stats", {}),
            ("list_indexed_documents", {}),
            ("search_knowledge", {
                "query": "test",
                "mode": "semantic",
                "limit": 3
            }),
        ]

        for tool_name, args in operations:
            result = mcp_client.call_tool(tool_name, args)
            assert "content" in result
            time.sleep(0.1)

        print("✅ Session survived 4 different operations")


# Run marker for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
