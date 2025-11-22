#!/bin/bash
# Wrapper script to run memoria skill with venv activated
# This ensures all dependencies (chromadb, sentence-transformers, rich) are available

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $SCRIPT_DIR/.venv" >&2
    echo "Please run: cd $SCRIPT_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
    exit 1
fi

# Run Python code from stdin using venv python
exec "$VENV_PYTHON" "$@"
