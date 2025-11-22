"""
Adapters layer - Infrastructure and external integrations.

This layer implements domain ports with concrete adapters:
- ChromaDB adapter (vector database)
- SentenceTransformer adapter (embeddings)
- File processor adapter (PDF, DOCX, MD extraction)
- Stub adapters (for testing)
- MCP server adapter (external API)

Dependencies: domain, application, and external libraries
"""
