# Memoria MCP - General-Purpose RAG System

**Version**: 1.0.0
**Status**: Ready for Testing (requires Claude Code restart)

Memoria MCP is the evolution of the raggy.py script into a full-fledged MCP server, providing general-purpose RAG (Retrieval-Augmented Generation) capabilities for Claude Code.

## Architecture

```
Claude Code → Facade (STDIO) → Memoria MCP Server (STDIO) → raggy.py
               ↓
         Audit Log (~/.claude/logs/memoria-mcp-audit.log)
```

### Components

1. **Memoria MCP Server** (`src/server.py`)
   - FastMCP server with STDIO transport
   - 5 MCP tools for RAG operations
   - Calls raggy.py via subprocess for now

2. **Security Facade** (`src/facade.py`)
   - Security wrapper between Claude Code and Memoria
   - Validates tool names and arguments
   - Prevents path traversal attacks
   - Logs all operations to audit log

3. **Document Storage** (`docs/`)
   - Hardcoded document location
   - Symlinked to `~/.claude/raggy/docs` for backwards compatibility

## Tools Available

### 1. `search_knowledge`
Search the indexed knowledge base with hybrid semantic + keyword search.

**Parameters:**
- `query` (string): Search query
- `n_results` (number, optional): Number of results (default: 5)

**Example:**
```json
{
  "query": "chronos task scheduling",
  "n_results": 10
}
```

### 2. `index_documents`
Index new documents into the RAG system.

**IMPORTANT**: First copy your document files to the docs folder, then call this tool.

**Parameters:**
- `file_patterns` (array): File patterns to index (files must be in docs folder)

**Example:**
```json
{
  "file_patterns": ["*.md", "*.txt"]
}
```

**Document Path:**
```
/Users/igorcandido/Github/thinker/claude_infra/apps/memoria-mcp/docs/
```

### 3. `list_indexed_documents`
List all documents currently indexed in the knowledge base.

**No parameters required**

### 4. `get_stats`
Get statistics about the RAG system (document count, chunk count, etc.).

**No parameters required**

### 5. `query_with_context`
Advanced query with expanded context retrieval.

**Parameters:**
- `query` (string): Search query
- `n_results` (number, optional): Number of results (default: 5)
- `expand_context` (boolean, optional): Expand surrounding context (default: true)

## Configuration

Memoria is configured in `~/.claude/.claude.json`:

```json
{
  "mcpServers": {
    "memoria": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "/Users/igorcandido/Github/thinker/claude_infra/apps/memoria-mcp/src/facade.py"
      ],
      "env": {}
    }
  }
}
```

## Backwards Compatibility

**For non-restarted Claude instances:**
- Old raggy.py script remains at `~/.claude/raggy/raggy.py`
- Symlink: `~/.claude/raggy/docs` → `apps/memoria-mcp/docs/`
- Documents are shared between old and new systems

**For new Claude instances (after restart):**
- Use Memoria MCP via Claude Code's MCP tools
- Tools available as `mcp__memoria__*`

## Installation

### Prerequisites

```bash
cd /Users/igorcandido/Github/thinker/claude_infra/apps/memoria-mcp
pip install -r requirements.txt
```

**Dependencies:**
- `fastmcp>=0.1.0`
- `chromadb>=0.4.0`
- `sentence-transformers>=2.2.0`

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create symlinks (for backwards compatibility):**
   ```bash
   bash scripts/create_symlinks.sh
   ```

3. **Configure Claude Code:**
   ```bash
   # Add Memoria to ~/.claude/.claude.json (already done)
   ```

4. **Restart Claude Code:**
   ```bash
   # Close and reopen Claude Code terminal
   # Memoria MCP will be available after restart
   ```

## Security Features

The facade provides several security layers:

### Tool Whitelisting
Only allowed tools can be executed:
- `search_knowledge`
- `index_documents`
- `list_indexed_documents`
- `get_stats`
- `query_with_context`

### Path Traversal Protection
For `index_documents`, validates file patterns:
- Rejects patterns with `..` (parent directory traversal)
- Rejects absolute paths starting with `/`

### Audit Logging
All operations logged to `~/.claude/logs/memoria-mcp-audit.log`:
- Tool calls with arguments
- Tool responses (success/failure)
- Security violations
- Errors

**Example audit log entry:**
```json
{
  "timestamp": "2025-10-10T13:45:23.123456",
  "event_type": "tool_call",
  "details": {
    "tool": "search_knowledge",
    "arguments": {"query": "chronos", "n_results": 5},
    "message_id": "msg_123"
  }
}
```

## Usage Workflow

### Indexing New Documents

1. **Copy documents to docs folder:**
   ```bash
   cp my_document.md /Users/igorcandido/Github/thinker/claude_infra/apps/memoria-mcp/docs/
   ```

2. **Index documents via MCP tool:**
   ```
   Use the index_documents tool with file_patterns: ["my_document.md"]
   ```

3. **Verify indexing:**
   ```
   Use list_indexed_documents to confirm
   ```

### Searching Knowledge

1. **Basic search:**
   ```
   Use search_knowledge with query: "your search terms"
   ```

2. **Advanced search with context:**
   ```
   Use query_with_context with expand_context: true
   ```

## Testing

**Note**: Testing requires Claude Code restart to load MCP server.

After restart, test tools:
1. `get_stats` - Check system status
2. `list_indexed_documents` - See what's indexed
3. `search_knowledge` - Try a search query

## Monitoring

### Health Check

```bash
bash scripts/health_check.sh
```

### Audit Log

```bash
tail -f ~/.claude/logs/memoria-mcp-audit.log
```

### Process Check

```bash
ps aux | grep memoria
```

## Development

### Directory Structure

```
apps/memoria-mcp/
├── src/
│   ├── server.py        # Main MCP server
│   └── facade.py        # Security facade
├── docs/                # Document storage (indexed documents)
├── scripts/
│   ├── create_symlinks.sh
│   └── health_check.sh
├── requirements.txt
├── metadata.json        # Component metadata
├── VERSION             # Version file
└── README.md           # This file
```

### Metadata

Component metadata in `metadata.json` includes:
- System dependencies (Python >=3.9)
- Python packages (fastmcp, chromadb, sentence-transformers)
- Post-install scripts (create_symlinks.sh)
- Health check script
- MCP configuration (STDIO transport, facade required)

## Troubleshooting

### Issue: Tools not available after configuration

**Solution**: Restart Claude Code to load new MCP server configuration.

### Issue: "Tool not allowed" error

**Cause**: Tool name not in facade whitelist
**Solution**: Check facade.py line 80-86 for allowed tools

### Issue: "Invalid file pattern (security)" error

**Cause**: Path traversal attempt detected
**Solution**: Use relative paths without `..` or leading `/`

### Issue: Audit log not writing

**Check**: `~/.claude/logs/` directory exists and is writable

### Issue: Server not starting

**Debug**:
1. Check Python version: `python3 --version` (need >=3.9)
2. Check dependencies: `pip list | grep -E 'fastmcp|chromadb|sentence'`
3. Check facade permissions: `ls -l src/facade.py`

## Future Enhancements

### Phase 2 (Planned)
- Replace raggy.py subprocess calls with direct ChromaDB integration
- Implement native embedding generation
- Add document chunking strategies
- Support more file formats (PDF, DOCX, etc.)

### Phase 3 (Planned)
- Multi-index support (separate knowledge bases)
- Document versioning
- Incremental indexing (only new/changed files)
- Web UI for management

## Related Systems

### LocalAgent Long-Term Memory
**Different system** - Do not confuse with Memoria:
- Location: `apps/localAgent_longTermMemory/`
- Purpose: LocalAgent-specific isolated RAG
- Separate ChromaDB instance
- Separate document folder

**Memoria is general-purpose, localAgent memory is agent-specific.**

## Support

For issues or questions:
1. Check audit log: `~/.claude/logs/memoria-mcp-audit.log`
2. Run health check: `bash scripts/health_check.sh`
3. Query RAG: `cd ~/.claude/raggy && .venv/bin/python raggy.py search "memoria troubleshooting"`

---

**Generated**: 2025-10-10
**Memoria MCP v1.0.0** - General-Purpose RAG for Claude Code
