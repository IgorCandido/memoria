#!/bin/bash
# Install Memoria Claude Code plugin
# Creates ~/.claude/memoria.env with connection config, then registers plugin
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKETPLACE_NAME="memoria-local"
PLUGIN_KEY="memoria@${MARKETPLACE_NAME}"
ENV_FILE="$HOME/.claude/memoria.env"

echo "Installing Memoria plugin..."
echo "  Plugin dir: $PLUGIN_DIR"

# --- Step 1: Configure ~/.claude/memoria.env ---
mkdir -p "$HOME/.claude"

if [ -f "$ENV_FILE" ]; then
    echo "  Found existing $ENV_FILE"
    # Validate required keys exist
    MISSING=""
    for KEY in MEMORIA_PG_HOST MEMORIA_PG_PORT MEMORIA_PG_DATABASE MEMORIA_PG_USER MEMORIA_CHROMA_HOST MEMORIA_CHROMA_PORT MEMORIA_OLLAMA_HOST MEMORIA_OLLAMA_PORT; do
        if ! grep -q "^${KEY}=" "$ENV_FILE" 2>/dev/null; then
            MISSING="$MISSING $KEY"
        fi
    done
    if [ -n "$MISSING" ]; then
        echo ""
        echo "ERROR: Missing required keys in $ENV_FILE:$MISSING"
        echo ""
        echo "Add them to $ENV_FILE or delete the file and re-run this script."
        exit 1
    fi
    echo "  All required keys present."
else
    echo ""
    echo "  No env file found. Creating $ENV_FILE..."
    echo ""
    echo "  Enter connection details (or press Enter for suggested default):"
    echo ""

    read -rp "  PostgreSQL host [192.168.1.153]: " PG_HOST
    PG_HOST="${PG_HOST:-192.168.1.153}"
    read -rp "  PostgreSQL port [5435]: " PG_PORT
    PG_PORT="${PG_PORT:-5435}"
    read -rp "  PostgreSQL database [memoria]: " PG_DB
    PG_DB="${PG_DB:-memoria}"
    read -rp "  PostgreSQL user [postgres]: " PG_USER
    PG_USER="${PG_USER:-postgres}"
    read -rp "  PostgreSQL password []: " PG_PASS
    PG_PASS="${PG_PASS:-}"

    read -rp "  ChromaDB host [${PG_HOST}]: " CHROMA_HOST
    CHROMA_HOST="${CHROMA_HOST:-$PG_HOST}"
    read -rp "  ChromaDB port [8001]: " CHROMA_PORT
    CHROMA_PORT="${CHROMA_PORT:-8001}"

    read -rp "  Ollama host [192.168.1.171]: " OLLAMA_HOST
    OLLAMA_HOST="${OLLAMA_HOST:-192.168.1.171}"
    read -rp "  Ollama port [11434]: " OLLAMA_PORT
    OLLAMA_PORT="${OLLAMA_PORT:-11434}"
    read -rp "  Embedding adapter [ollama]: " EMBED_ADAPTER
    EMBED_ADAPTER="${EMBED_ADAPTER:-ollama}"

    cat > "$ENV_FILE" << ENVEOF
MEMORIA_PG_HOST=${PG_HOST}
MEMORIA_PG_PORT=${PG_PORT}
MEMORIA_PG_DATABASE=${PG_DB}
MEMORIA_PG_USER=${PG_USER}
MEMORIA_PG_PASSWORD=${PG_PASS}
MEMORIA_CHROMA_HOST=${CHROMA_HOST}
MEMORIA_CHROMA_PORT=${CHROMA_PORT}
MEMORIA_OLLAMA_HOST=${OLLAMA_HOST}
MEMORIA_OLLAMA_PORT=${OLLAMA_PORT}
MEMORIA_EMBEDDING_ADAPTER=${EMBED_ADAPTER}
ENVEOF

    chmod 600 "$ENV_FILE"
    echo ""
    echo "  Written: $ENV_FILE"
fi

# --- Step 2: Register marketplace and install plugin ---
claude plugin marketplace add "$PLUGIN_DIR" 2>/dev/null || true
claude plugin install "$PLUGIN_KEY" 2>/dev/null || claude plugin enable "$PLUGIN_KEY" 2>/dev/null || true

echo ""
echo "Done. Run '/reload-plugins' in Claude Code to activate."
echo ""
echo "Installed:"
echo "  - memoria skill: RAG knowledge base (search_knowledge, store_document)"
echo "  - SessionStart hook: RAG awareness priming"
echo "  - Config: $ENV_FILE"
