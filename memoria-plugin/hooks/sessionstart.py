"""Memoria SessionStart Hook - Prime RAG awareness."""
import json

MEMORIA_DIR = "/Users/igorcandido/Github/thinker/memoria/main"


def main():
    context = f"""MEMORIA RAG: Knowledge base is available (PostgreSQL + ChromaDB).

READ — search prior knowledge before non-trivial responses:
```bash
cd {MEMORIA_DIR} && uv run memoria search "your query"
```

WRITE — store valuable knowledge discovered during the session:
```bash
cd {MEMORIA_DIR} && uv run memoria store "descriptive-name.md" "document content here" --title "Title"
```
For large content, pipe via stdin:
```bash
cat file.md | cd {MEMORIA_DIR} && uv run memoria store "source-id.md" - --title "Title"
```
Store when you encounter: architectural decisions, bug root causes, working patterns/conventions,
infrastructure details, or solutions to non-obvious problems.

RETRIEVE — get full document content by source_id:
```bash
cd {MEMORIA_DIR} && uv run memoria get "source-id.md"
```

Use /memoria for full API reference."""

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context
        }
    }))


if __name__ == "__main__":
    main()
