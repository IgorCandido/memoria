# Memoria Skill - Quick Start Invocation

**Updated**: 2025-11-22
**Critical**: Read this FIRST before using memoria skill

## ⚠️ The #1 Mistake That Breaks Everything

**Using bare `python3` instead of the venv python path.**

### ❌ WRONG - Will ALWAYS Fail

```bash
# This WILL FAIL with: ModuleNotFoundError: No module named 'memoria'
python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge
EOF
```

**Why it fails**: System python3 doesn't have memoria dependencies (chromadb, sentence-transformers, rich, etc.)

### ✅ CORRECT - Always Works

```bash
# This WORKS - uses shared venv with all dependencies
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge

result = search_knowledge(query="your search query", mode="hybrid", expand=True, limit=5)
print(result)
EOF
```

## Copy-Paste Examples

### Search Knowledge Base

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import search_knowledge

result = search_knowledge(
    query="agent-mail dashboard requirements",
    mode="hybrid",
    expand=True,
    limit=5
)
print(result)
EOF
```

### Health Check

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import health_check

result = health_check()
print(result)
EOF
```

### Get Stats

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import get_stats

result = get_stats()
print(result)
EOF
```

### Index Documents

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import index_documents

result = index_documents(pattern="**/*.md", rebuild=False)
print(result)
EOF
```

## The Pattern

Every invocation follows this pattern:

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')
from skill_helpers import FUNCTION_NAME

result = FUNCTION_NAME(arguments...)
print(result)
EOF
```

**Three critical parts**:
1. **Venv Python Path**: `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3`
2. **Sys Path Insert**: `sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')`
3. **Import from skill_helpers**: `from skill_helpers import FUNCTION_NAME`

## Why This Matters

**Skills vs MCP**:
- **Skills**: 98.7% token reduction, direct execution, no Docker overhead
- **MCP**: Heavy infrastructure, session management, HTTP bridges

**But skills require correct invocation**:
- System python3 = ❌ No dependencies = ModuleNotFoundError
- Venv python3 = ✅ All dependencies = Works perfectly

## Troubleshooting

### "ModuleNotFoundError: No module named 'memoria'"

**Cause**: Used `python3` instead of venv python
**Fix**: Use `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3`

### "ModuleNotFoundError: No module named 'rich'"

**Cause**: Used `python3` instead of venv python
**Fix**: Use `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3`

### "ModuleNotFoundError: No module named 'chromadb'"

**Cause**: Used `python3` instead of venv python
**Fix**: Use `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3`

### Pattern Recognition

**If you see ModuleNotFoundError for ANY module, you used the wrong python.**

## For All Claude Instances

If you're a Claude instance reading this:

1. **ALWAYS** read `~/.claude/skills/memoria/SKILL.md` BEFORE using memoria
2. **NEVER** use bare `python3` for skills
3. **ALWAYS** copy the EXACT invocation pattern from the skill definition
4. **VERIFY** you're using `/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3`

## Verification

Test if you're using the correct python:

```bash
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3 << 'EOF'
import sys
print(f"Python path: {sys.executable}")
print(f"Expected: /Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3")
print(f"Match: {sys.executable == '/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3'}")
EOF
```

Expected output:
```
Python path: /Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3
Expected: /Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3
Match: True
```

## References

- Skill definition: `~/.claude/skills/memoria/SKILL.md`
- Shared venv setup: Query RAG for "skills shared virtual environment"
- Full documentation: `skills/memoria/README.md`

## Summary

**One rule to remember**:

```bash
# ✅ Use this python
/Users/igorcandido/Github/thinker/claude_infra/skills/.venv/bin/python3

# ❌ Not this
python3
```

**That's it. That's the entire fix.**
