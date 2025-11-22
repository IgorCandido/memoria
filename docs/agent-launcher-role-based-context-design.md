# Agent Launcher: Role-Based Context Injection Design

**Date**: 2025-11-22
**Status**: Design Phase
**Problem**: Different Claude instances need different context without bloating all instances with irrelevant instructions

---

## Problem Statement

### Current Situation
- **~/.claude/CLAUDE.md**: Global instructions loaded for EVERY Claude instance
- **Token cost**: Every line in CLAUDE.md costs tokens on EVERY request
- **Current size**: ~300 lines = ~1,500 tokens per request

### Pain Points
1. **Main user (Igor)** needs:
   - Agent-mail workflow awareness
   - Multi-agent coordination patterns
   - RAG query protocols
   - Infrastructure management

2. **Coder agent** needs:
   - Coding guidelines and standards
   - Test requirements
   - Security best practices
   - NO agent-mail workflow (they receive work, don't send it)

3. **Reviewer agent** needs:
   - Review checklists and criteria
   - Code quality standards
   - Documentation requirements
   - NO multi-agent coordination (single focus)

4. **Planner agent** needs:
   - Planning methodologies
   - Task breakdown templates
   - Estimation guidelines
   - NO implementation details

**Current problem**: Everyone gets EVERYTHING → massive token waste

---

## Design Goals

1. **Zero token bloat**: Agents only get context relevant to their role
2. **Consistent agent IDs**: Automatic, stable, unique identification
3. **Easy to use**: Simple command to launch role-specific agent
4. **Safe**: No risk of corrupting global CLAUDE.md
5. **Maintainable**: Role definitions in separate files
6. **Testable**: Can validate role context before deployment

---

## Constraints

### What Claude Code Actually Reads

1. **~/.claude/CLAUDE.md** - Global instructions (ALWAYS loaded, no way to disable)
2. **<project>/.claude/CLAUDE.md** - Project-specific (if present, merged with global)
3. **~/.claude/skills/*.md** - Skill definitions (loaded on-demand when used)
4. **RAG documents** - Via memoria queries (on-demand, requires explicit query)

### What We CANNOT Do

❌ Tell Claude Code to read different global CLAUDE.md files
❌ Dynamically inject context without modifying CLAUDE.md
❌ Use environment variables for context (Claude can't read them in instructions)
❌ Conditionally load sections of CLAUDE.md based on flags

### What We CAN Do

✅ Generate ~/.claude/CLAUDE.md before launching (with backup/restore)
✅ Keep ~/.claude/CLAUDE.md minimal and rely on RAG queries
✅ Use project-specific .claude/CLAUDE.md in different directories
✅ Create launcher that manages context injection lifecycle

---

## Design Options

### Option A: Minimal Global + RAG Queries (RECOMMENDED)

**Approach**: Keep ~/.claude/CLAUDE.md minimal (50 lines = ~200 tokens), use RAG for everything else.

**~/.claude/CLAUDE.md (minimal version):**
```markdown
# Claude Infrastructure Management

## Agent Identity & Role

Check your agent ID and role on startup. Query RAG for role-specific guidelines:
- Main user: Query "main user workflow guidelines"
- Coder agent: Query "coder agent guidelines"
- Reviewer agent: Query "reviewer agent guidelines"
- Planner agent: Query "planner agent guidelines"

## Core Infrastructure Pointers

- Memoria skill: skills/memoria/ (RAG access)
- Agent-mail skill: skills/agent-mail/ (work queue)
- Infrastructure docs: Query RAG for "infrastructure overview"

## Absolute Rules

- Always query RAG before non-trivial tasks
- Use memoria MCP tool (not deprecated bash raggy.py)
- Prefer MCP tools over bash commands (ast-grep > grep)
```

**Launcher Script** (`~/bin/launch-claude`):
```bash
#!/bin/bash
# Agent Launcher with Role-Based Context

ROLE=${1:-main}
CATEGORY=${2:-$ROLE}
PROJECT_DIR=${3:-.}

# Validate role
VALID_ROLES=("main" "coder" "reviewer" "planner" "tester")
if [[ ! " ${VALID_ROLES[@]} " =~ " ${ROLE} " ]]; then
    echo "Error: Invalid role '$ROLE'"
    echo "Valid roles: ${VALID_ROLES[*]}"
    exit 1
fi

# Generate stable agent ID
SESSION_ID=$(cat /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | fold -w 8 | head -n 1)
HOSTNAME=$(hostname -s | tr '[:upper:]' '[:lower:]' | tr -d ' ')
USER=$(whoami)

AGENT_ID="${USER}-${ROLE}-${SESSION_ID}"

# Log launch
echo "🚀 Launching Claude Agent"
echo "   Role: $ROLE"
echo "   Category: $CATEGORY"
echo "   Agent ID: $AGENT_ID"
echo "   Project: $PROJECT_DIR"
echo ""

# Create role-specific welcome message
WELCOME_MSG="/tmp/claude-welcome-${SESSION_ID}.txt"
cat > "$WELCOME_MSG" << EOF
You are a ${ROLE} agent with ID: ${AGENT_ID}

Your role: ${ROLE}
Your category: ${CATEGORY}
Project directory: ${PROJECT_DIR}

IMPORTANT: Query RAG immediately for "${ROLE} agent guidelines" to get your role-specific instructions.

Role summary:
EOF

case $ROLE in
    main)
        cat >> "$WELCOME_MSG" << EOF
- You are the main user coordination agent
- Use agent-mail to distribute work to specialized agents
- Query RAG for: "agent-mail workflow for main user"
- You can send work, monitor queues, coordinate multiple agents
EOF
        ;;
    coder)
        cat >> "$WELCOME_MSG" << EOF
- You are a coder agent that implements features and fixes bugs
- Claim work from agent-mail 'coder' category
- Query RAG for: "coder agent guidelines"
- Focus: code quality, tests, security, performance
- Submit results when done
EOF
        ;;
    reviewer)
        cat >> "$WELCOME_MSG" << EOF
- You are a reviewer agent that reviews code and designs
- Claim work from agent-mail 'reviewer' category
- Query RAG for: "reviewer agent guidelines"
- Focus: code quality, design patterns, best practices, security
- Provide detailed, actionable feedback
EOF
        ;;
    planner)
        cat >> "$WELCOME_MSG" << EOF
- You are a planner agent that breaks down complex tasks
- Claim work from agent-mail 'planner' category
- Query RAG for: "planner agent guidelines"
- Focus: task breakdown, effort estimation, risk assessment
- Create actionable implementation plans
EOF
        ;;
    tester)
        cat >> "$WELCOME_MSG" << EOF
- You are a tester agent that writes and runs tests
- Claim work from agent-mail 'tester' category
- Query RAG for: "tester agent guidelines"
- Focus: test coverage, edge cases, validation
- Report test results and coverage metrics
EOF
        ;;
esac

# Export environment variables (for scripts/tools to use)
export CLAUDE_AGENT_ID="$AGENT_ID"
export CLAUDE_ROLE="$ROLE"
export CLAUDE_CATEGORY="$CATEGORY"

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Launch clauderock with welcome message
echo "Press Enter to launch Claude with role-specific context..."
read -r

# Print welcome message and launch
cat "$WELCOME_MSG"
echo ""
echo "Launching clauderock..."
echo ""

clauderock

# Cleanup
rm -f "$WELCOME_MSG"
```

**Pros:**
- ✅ Zero changes to clauderock
- ✅ ~/.claude/CLAUDE.md stays minimal (~200 tokens)
- ✅ Role-specific context loaded via RAG (on-demand)
- ✅ Agent ID automatically generated and stable
- ✅ Easy to add new roles (just add to script + RAG docs)
- ✅ Safe - no risk of corrupting global config

**Cons:**
- ⚠️ Agent must remember to query RAG for guidelines
- ⚠️ Welcome message shown once, then lost (unless agent queries RAG)

**Token savings:**
- Current: ~1,500 tokens per request (full CLAUDE.md)
- With this: ~200 tokens (minimal CLAUDE.md) + ~300 tokens (RAG query, done once)
- **Savings: ~1,300 tokens per request = 87% reduction**

---

### Option B: Dynamic CLAUDE.md Generation (COMPLEX BUT COMPLETE)

**Approach**: Launcher generates ~/.claude/CLAUDE.md from role-specific templates before launch.

**Structure:**
```
~/.claude/
├── CLAUDE.base.md          # Minimal base (everyone gets)
├── CLAUDE.main.md          # Main user additions
├── CLAUDE.coder.md         # Coder agent additions
├── CLAUDE.reviewer.md      # Reviewer agent additions
├── CLAUDE.planner.md       # Planner agent additions
└── CLAUDE.md               # Generated (never edit directly)
```

**Launcher Script:**
```bash
#!/bin/bash
# Dynamic CLAUDE.md generation

ROLE=${1:-main}

# Backup original
if [ -f ~/.claude/CLAUDE.md ]; then
    cp ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.backup
fi

# Generate from base + role-specific
cat ~/.claude/CLAUDE.base.md > ~/.claude/CLAUDE.md
cat ~/.claude/CLAUDE.${ROLE}.md >> ~/.claude/CLAUDE.md

# Trap to restore on exit
trap "mv ~/.claude/CLAUDE.md.backup ~/.claude/CLAUDE.md" EXIT

# Launch
clauderock
```

**Pros:**
- ✅ Complete control over injected context
- ✅ Agent gets role context automatically (no RAG query needed)
- ✅ Can include complex role-specific instructions

**Cons:**
- ❌ Risky - modifies global CLAUDE.md
- ❌ If script crashes, CLAUDE.md might be wrong
- ❌ Multiple simultaneous launches conflict
- ❌ Difficult to debug (which CLAUDE.md is active?)
- ❌ Still loads full role context on every request (token cost)

**Not recommended** due to risk and complexity.

---

### Option C: Project-Specific CLAUDE.md Per Role (CLEANEST)

**Approach**: Each role has its own workspace directory with role-specific .claude/CLAUDE.md.

**Structure:**
```
~/Claude-Agents/
├── main/
│   ├── .claude/CLAUDE.md   # Main user instructions
│   └── work/               # Symlink to ~/Github/thinker/claude_infra
├── coder/
│   ├── .claude/CLAUDE.md   # Coder instructions
│   └── work/               # Symlink to ~/Github/thinker/claude_infra
├── reviewer/
│   ├── .claude/CLAUDE.md   # Reviewer instructions
│   └── work/               # Symlink to ~/Github/thinker/claude_infra
```

**Launcher:**
```bash
#!/bin/bash
ROLE=${1:-main}
WORKSPACE="$HOME/Claude-Agents/${ROLE}"

if [ ! -d "$WORKSPACE" ]; then
    echo "Error: Workspace not found: $WORKSPACE"
    exit 1
fi

cd "$WORKSPACE/work" || exit 1
clauderock
```

**Pros:**
- ✅ Clean separation - each role has own config
- ✅ Safe - no risk of corrupting other roles
- ✅ Project-specific CLAUDE.md overrides global (Claude Code behavior)
- ✅ Easy to edit role-specific instructions

**Cons:**
- ⚠️ Requires setup (create workspace directories)
- ⚠️ File operations relative to workspace/work, not actual project
- ⚠️ More complex mental model (which directory am I in?)

**Could work** but requires careful path management.

---

## Recommendation: Option A (Minimal + RAG)

**Why:**
1. **Simplest**: No complex directory structures or dynamic generation
2. **Safest**: No risk of corrupting global config
3. **Lowest token cost**: ~200 tokens base + one-time RAG query
4. **Most flexible**: Easy to add roles without code changes
5. **Easy to test**: Just test launcher script + RAG documents

**Implementation Plan:**

### Phase 1: Minimal CLAUDE.md + Launcher (This Week)
1. ✅ Create minimal ~/.claude/CLAUDE.md (~50 lines)
2. ✅ Create ~/bin/launch-claude launcher script
3. ✅ Test with main role (igor-claude)
4. ✅ Validate agent ID generation (uniqueness, stability)
5. ✅ Add launcher to PATH

### Phase 2: Role-Specific RAG Documents (Next Week)
1. Create RAG documents:
   - `skills/memoria/docs/main-user-agent-guidelines.md`
   - `skills/memoria/docs/coder-agent-guidelines.md`
   - `skills/memoria/docs/reviewer-agent-guidelines.md`
   - `skills/memoria/docs/planner-agent-guidelines.md`
   - `skills/memoria/docs/tester-agent-guidelines.md`
2. Index in RAG
3. Validate queries work

### Phase 3: Dog-Food with Worker Agents (Week 2)
1. Launch coder agent: `launch-claude coder`
2. Agent queries RAG for guidelines
3. Agent claims work from agent-mail
4. Agent executes work
5. Agent submits result
6. Validate full workflow

### Phase 4: Integrate with Agent-Mail System (Week 3)
1. Update agent_worker.py to use launch-claude
2. Workers automatically get role-specific context
3. Monitor and tune based on outcomes
4. Scale to multiple concurrent workers

---

## Agent ID System Design

### ID Format
`{user}-{role}-{session_id}`

**Examples:**
- `igor-main-abc12345` - Igor's main coordination instance
- `igor-coder-def67890` - Igor's coder worker instance
- `alice-reviewer-ghi13579` - Alice's reviewer worker instance

### Properties
- **Unique**: session_id ensures no collisions
- **Stable**: Same session = same ID throughout
- **Informative**: Can identify user and role from ID
- **Safe**: No special characters that break systems

### Generation Algorithm
```bash
SESSION_ID=$(cat /dev/urandom | LC_ALL=C tr -dc 'a-z0-9' | fold -w 8 | head -n 1)
HOSTNAME=$(hostname -s | tr '[:upper:]' '[:lower:]' | tr -d ' ')
USER=$(whoami)
AGENT_ID="${USER}-${ROLE}-${SESSION_ID}"
```

### Testing Requirements
1. **Uniqueness Test**: Generate 10,000 IDs, verify no duplicates
2. **Stability Test**: Same session generates same ID
3. **Format Validation**: Regex test for allowed characters
4. **Cross-Platform**: Test on macOS and Linux
5. **Collision Probability**: Calculate birthday paradox risk

### Integration Points
- **Agent-mail**: Use AGENT_ID for from_id, agent_id parameters
- **Logs**: Include AGENT_ID in all log entries
- **Monitoring**: Track agent activity by ID
- **Learning System**: Associate outcomes with agent IDs

---

## Role-Specific Guidelines (RAG Documents)

### Main User Agent Guidelines

**File**: `skills/memoria/docs/main-user-agent-guidelines.md`

**Content:**
- Multi-agent coordination patterns
- When to delegate work vs do it yourself
- Monitoring queue health
- Interpreting agent outcomes
- Feedback mechanisms for learning system
- Agent-mail workflow (send_work, monitor, review results)

**Token cost**: ~500 tokens (loaded once via RAG query)

### Coder Agent Guidelines

**File**: `skills/memoria/docs/coder-agent-guidelines.md`

**Content:**
- Code quality standards (typing, error handling, tests)
- Security best practices (input validation, SQL injection, XSS)
- Performance considerations (n+1 queries, memory leaks)
- Testing requirements (unit tests, integration tests)
- Documentation standards (docstrings, comments)
- Git commit message format
- When to ask for clarification vs proceed
- How to submit results (status, files changed, tests added)

**Token cost**: ~600 tokens (loaded once via RAG query)

### Reviewer Agent Guidelines

**File**: `skills/memoria/docs/reviewer-agent-guidelines.md`

**Content:**
- Code review checklist (functionality, security, performance, maintainability)
- Design pattern evaluation
- Architecture consistency checks
- Documentation quality assessment
- Test coverage evaluation
- Actionable feedback format
- When to approve vs request changes vs reject
- How to submit review results

**Token cost**: ~550 tokens (loaded once via RAG query)

### Planner Agent Guidelines

**File**: `skills/memoria/docs/planner-agent-guidelines.md`

**Content:**
- Task breakdown methodology (top-down vs bottom-up)
- Effort estimation techniques (story points, hours)
- Risk assessment framework
- Dependency identification
- Milestone definition
- Success criteria specification
- Plan format and structure
- When to seek clarification vs make assumptions

**Token cost**: ~500 tokens (loaded once via RAG query)

### Tester Agent Guidelines

**File**: `skills/memoria/docs/tester-agent-guidelines.md`

**Content:**
- Test coverage requirements (unit, integration, E2E)
- Edge case identification
- Test naming conventions
- Assertion best practices
- Test data management
- Performance test requirements
- Security test considerations
- Test result reporting format

**Token cost**: ~550 tokens (loaded once via RAG query)

---

## Token Cost Analysis

### Current Approach (Everything in CLAUDE.md)
- Base instructions: 500 tokens
- Agent-mail workflow: 400 tokens
- Coder guidelines: 600 tokens
- Reviewer guidelines: 550 tokens
- Planner guidelines: 500 tokens
- Tester guidelines: 550 tokens
- **Total per request**: 3,100 tokens
- **Cost per session** (100 requests): 310,000 tokens

### Recommended Approach (Minimal + RAG)
- Minimal CLAUDE.md: 200 tokens (every request)
- Role-specific RAG query: 500-600 tokens (once per session)
- **Total per request**: 200 tokens
- **Cost per session** (100 requests): 20,000 + 600 = 20,600 tokens
- **Savings**: 289,400 tokens per session = **93.4% reduction**

### Savings at Scale
- 10 coder agents working simultaneously
- Each does 100 requests
- Current cost: 3,100,000 tokens
- New cost: 206,000 tokens
- **Savings: 2,894,000 tokens = 93.4%**

At $3/million input tokens (Claude Sonnet pricing):
- Current: $9.30 per 10-agent session
- New: $0.62 per 10-agent session
- **Savings: $8.68 per session**

With 100 sessions/month:
- **Monthly savings: $868**

---

## Integration with clauderock

### Option 1: Keep Separate (Recommended)
- `clauderock`: Unchanged, launches Claude Code
- `launch-claude`: Wrapper that sets context + calls clauderock
- Users call `launch-claude` instead of `clauderock`

**Pros:**
- Zero risk to clauderock
- Easy to test separately
- Can iterate quickly

**Cons:**
- Users need to remember to use launch-claude

### Option 2: Extend clauderock
```bash
clauderock --role=coder --category=coder
```

Add to clauderock:
```bash
# Parse --role flag
# Generate agent ID
# Set environment variables
# Print welcome message
# Launch Claude Code
```

**Pros:**
- Single command
- Integrated experience

**Cons:**
- Modifies clauderock (needs thorough testing)
- More complex to maintain

**Recommendation**: Start with Option 1 (separate launcher). After validation, consider merging into clauderock.

---

## Testing Strategy

### Phase 1: Launcher Testing
1. **ID Generation Test**:
   ```bash
   for i in {1..10000}; do launch-claude --test-id-only main; done | sort | uniq -d
   # Should output nothing (no duplicates)
   ```

2. **Role Validation Test**:
   ```bash
   launch-claude invalid_role  # Should error
   launch-claude main          # Should succeed
   ```

3. **Welcome Message Test**:
   ```bash
   launch-claude main --dry-run  # Print welcome message without launching
   ```

### Phase 2: RAG Document Testing
1. Query each role's guidelines
2. Verify content is relevant and complete
3. Measure token count
4. Test with actual agent sessions

### Phase 3: Integration Testing
1. Launch coder agent
2. Agent queries RAG for guidelines
3. Verify guidelines received correctly
4. Agent claims work from agent-mail
5. Agent executes work following guidelines
6. Agent submits result
7. Validate full workflow

### Phase 4: Multi-Agent Testing
1. Launch 3 coder agents simultaneously
2. Verify unique agent IDs
3. All claim different work items
4. No conflicts or collisions
5. All complete successfully

---

## Migration Path

### Week 1: Design & Setup
- ✅ Create minimal CLAUDE.md
- ✅ Create launch-claude script
- ✅ Create role-specific RAG documents
- ✅ Index in RAG
- ✅ Test with main role

### Week 2: Validation
- Test with coder role
- Test with reviewer role
- Measure token savings
- Collect feedback

### Week 3: Scale
- Launch multiple agents
- Dog-food with real work
- Monitor and tune
- Document best practices

### Week 4: Production
- Integrate with agent_worker.py
- Update documentation
- Train users
- Consider merging into clauderock

---

## Open Questions

1. **Should launcher be bash or Python?**
   - Bash: Faster, simpler, no dependencies
   - Python: More robust, easier to test, better error handling

2. **Where to store launcher?**
   - ~/bin/launch-claude (user-specific)
   - /usr/local/bin/launch-claude (system-wide)
   - ~/Github/thinker/claude_infra/bin/launch-claude (repo)

3. **How to handle launcher updates?**
   - Symlink from ~/bin to repo version?
   - Copy to ~/bin on updates?
   - Package manager (brew install launch-claude)?

4. **Should agent ID persist across restarts?**
   - Currently: New ID per session
   - Alternative: Save ID, reuse if session continues
   - Tradeoff: Persistence vs simplicity

5. **How to handle role switching mid-session?**
   - Currently: Restart required
   - Alternative: Dynamic role switching?
   - Tradeoff: Complexity vs flexibility

---

## Success Criteria

### Launcher
- ✅ Generates unique, stable agent IDs
- ✅ Role validation works
- ✅ Welcome message displays correctly
- ✅ Launches clauderock successfully
- ✅ Cleans up temp files on exit

### Token Savings
- ✅ Minimal CLAUDE.md < 300 tokens
- ✅ Total per-request cost < 250 tokens
- ✅ 90%+ reduction vs current approach

### User Experience
- ✅ Easy to launch: `launch-claude <role>`
- ✅ Clear feedback on role and ID
- ✅ RAG query works first time
- ✅ Guidelines are complete and useful

### Multi-Agent Coordination
- ✅ Multiple agents can run simultaneously
- ✅ No ID collisions
- ✅ Agents stay in their roles
- ✅ Work distribution functions correctly

---

## Next Steps

**Immediate (Today):**
1. Create minimal ~/.claude/CLAUDE.md
2. Create ~/bin/launch-claude script
3. Test with igor-main role
4. Validate agent ID generation

**Short-Term (This Week):**
1. Create all role-specific RAG documents
2. Index in RAG
3. Test RAG queries from each role
4. Document usage

**Medium-Term (Next Week):**
1. Launch coder agent with launcher
2. Claim work from agent-mail
3. Execute work with role guidelines
4. Validate full workflow

**Long-Term (Week 3+):**
1. Scale to multiple agents
2. Integrate with agent_worker.py
3. Measure token savings
4. Consider merging into clauderock

---

**Status**: ✅ Design Complete - Ready for Implementation
**Recommendation**: Proceed with Option A (Minimal + RAG) approach
**Next Action**: Create minimal CLAUDE.md and launcher script for validation
