"""
Memoria MCP server — FastMCP STDIO transport.

Exposes skill_helpers functions as MCP tools:
  - search_knowledge: Semantic/hybrid search over ChromaDB
  - get_document: Retrieve full document content from Postgres by source_id
"""

import fastmcp

mcp = fastmcp.FastMCP("memoria")


@mcp.tool()
def search_knowledge(query: str, mode: str = "hybrid", limit: int = 5) -> str:
    """
    Search the memoria knowledge base.

    Args:
        query: Natural language search query
        mode: Search mode — "hybrid" (default), "semantic", or "keyword"
        limit: Maximum number of results to return (default 5)

    Returns:
        Formatted search results as plain text
    """
    from memoria.skill_helpers import search_knowledge as _search
    return _search(query=query, mode=mode, limit=limit)


@mcp.tool()
def get_document(source_id: str) -> str:
    """
    Retrieve full document content from the document store.

    Args:
        source_id: Stable identifier used when the document was stored

    Returns:
        Full document content as a string

    Raises:
        ValueError: If the document is not found
    """
    from memoria.skill_helpers import get_document as _get
    return _get(source_id=source_id)


if __name__ == "__main__":
    mcp.run()
