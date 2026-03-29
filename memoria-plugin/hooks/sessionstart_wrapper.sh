#!/bin/bash
# SessionStart hook - Prime RAG awareness
set -euo pipefail

PYTHON="/Users/igorcandido/Github/thinker/memoria/main/.venv/bin/python3"

if [[ -x "$PYTHON" ]]; then
    "$PYTHON" "${CLAUDE_PLUGIN_ROOT}/hooks/sessionstart.py" 2>/dev/null
    exit $?
fi

python3 "${CLAUDE_PLUGIN_ROOT}/hooks/sessionstart.py" 2>/dev/null
