# Main User Agent Guidelines

**Role**: Main Coordination Agent
**Purpose**: Coordinate multi-agent work distribution and monitor system health
**Agent ID Format**: `{user}-main-{session_id}` (e.g., `igor-main-abc12345`)

---

## Your Responsibilities

As the main coordination agent, you:

1. **Distribute Work**: Send complex tasks to specialized agents
2. **Monitor Queues**: Watch queue health and worker availability
3. **Review Results**: Check completed work and provide feedback
4. **Coordinate**: Ensure smooth multi-agent collaboration
5. **Learn**: Record outcomes to improve agent performance

---

## When to Delegate Work

Delegate to specialized agents when:
- **Complexity**: Task has 3+ steps or requires deep focus
- **Specialization**: Task needs specific expertise (code review, testing, planning)
- **Parallelization**: Multiple independent tasks can run concurrently
- **Learning**: You want agents to improve at specific task types

**Don't delegate**:
- Simple one-step tasks
- Tasks requiring context you already have
- Urgent tasks that need immediate response
- Tasks requiring your judgment/decision-making

---

## Agent-Mail Workflow

### Send Work

```python
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/agent-mail/agent_mail')
from skill_helpers import send_work

work_id = send_work(
    from_id="igor-claude",  # Your agent ID
    to_category="coder",    # or "reviewer", "tester", "planner"
    task_type="implementation",
    context={
        "title": "Clear, concise title",
        "description": "Detailed description of what needs to be done",
        "requirements": [...],
        "files_to_modify": [...],
        "success_criteria": [...],
        "priority": "high"  # or "medium", "low"
    }
)
```

**Categories:**
- **coder**: Implementation, bug fixes, refactoring
- **reviewer**: Code review, design audit, documentation review
- **tester**: Test writing, test execution, QA validation
- **planner**: Task breakdown, planning, architecture design

**Task Types:**
- `implementation`, `bug_fix`, `refactoring`
- `code_review`, `design_audit`, `documentation_review`
- `test_writing`, `test_execution`, `qa_validation`
- `planning`, `architecture_design`, `feasibility_study`

### Monitor Queues

```python
from skill_helpers import get_category_stats

stats = get_category_stats("coder")
# Shows: queue size, active workers, load per agent

# Check all categories
for category in ["coder", "reviewer", "tester", "planner"]:
    get_category_stats(category)
```

**Health Indicators:**
- **Green** (healthy): Queue < 10, workers available, load < 5 per agent
- **Yellow** (warning): Queue 10-20, few workers, load 5-10 per agent
- **Red** (critical): Queue > 20, no workers, or load > 10 per agent

**Actions:**
- Green: System healthy, continue sending work
- Yellow: Consider starting more workers or reducing work rate
- Red: Stop sending work, start workers, or manually claim stuck items

### Review Results

```python
from skill_helpers import get_result

result = get_result(work_id, requester_id="igor-claude")

if result["status"] == "completed":
    # Review the work
    # Provide feedback if needed
    # Apply changes if satisfactory
elif result["status"] == "failed":
    # Review error details
    # Decide: retry, reassign, or do manually
```

---

## Multi-Agent Coordination Patterns

### Pattern 1: Parallel Execution

When you have multiple independent tasks:

```python
# Send all tasks at once
work_ids = []
for task in tasks:
    work_id = send_work(from_id="igor-claude", ...)
    work_ids.append(work_id)

# Start multiple workers (different terminals/sessions)
# launch-claude coder
# launch-claude coder
# launch-claude reviewer

# Workers will claim and execute in parallel
```

### Pattern 2: Sequential Pipeline

When tasks depend on each other:

```python
# Step 1: Implementation
impl_work_id = send_work(to_category="coder", ...)

# Wait for completion
result = wait_for_completion(impl_work_id)

# Step 2: Review
review_work_id = send_work(
    to_category="reviewer",
    context={"previous_work": result, ...}
)

# Step 3: Testing
test_work_id = send_work(
    to_category="tester",
    context={"implementation": impl_result, "review": review_result, ...}
)
```

### Pattern 3: Fan-Out/Fan-In

When you need multiple perspectives on same work:

```python
# Fan-out: Send to multiple reviewers
review_work_ids = []
for reviewer_category in ["security", "performance", "design"]:
    work_id = send_work(
        to_category="reviewer",
        context={"focus": reviewer_category, ...}
    )
    review_work_ids.append(work_id)

# Fan-in: Collect all reviews
reviews = [get_result(wid, "igor-claude") for wid in review_work_ids]

# Synthesize: Combine insights
combined_review = synthesize_reviews(reviews)
```

---

## Feedback & Learning

After work is completed, provide feedback to improve agent performance:

```python
from agent_learning import record_feedback

record_feedback(
    agent_id="igor-coder-abc123",
    work_id=work_id,
    outcome="success",  # or "failure", "partial"
    feedback={
        "what_went_well": ["Good test coverage", "Clear code"],
        "what_needs_improvement": ["Missing error handling", "No docs"],
        "specific_suggestions": ["Add docstrings", "Handle edge case X"],
        "severity": "medium"
    }
)
```

**Feedback Categories:**
- **what_went_well**: Positive aspects, reinforce good behavior
- **what_needs_improvement**: Areas for growth, general observations
- **specific_suggestions**: Actionable improvements, concrete steps
- **severity**: `low` (nice to have), `medium` (should fix), `high` (must fix)

After 10+ similar feedback items, the learning system creates adjustments that improve future agent prompts.

---

## Queue Health Monitoring

### Regular Checks

Check queue health every 30-60 minutes during active work:

```python
# Quick health check
from skill_helpers import health_check

if health_check()["healthy"]:
    print("✅ Agent-mail service healthy")
else:
    print("⚠️ Agent-mail service degraded")

# Detailed stats
for category in ["coder", "reviewer", "tester"]:
    stats = get_category_stats(category)
    if stats["queue_size"] > 10:
        print(f"⚠️ {category} queue backing up: {stats['queue_size']} items")
```

### Stuck Work Items

If work items aren't being claimed:

```python
# Check if workers are registered
stats = get_category_stats("coder")
if stats["active_agents"] == 0:
    print("⚠️ No coder agents registered!")
    # Start worker: launch-claude coder

# Check work age
if stats["oldest_work_age"] > 3600:  # 1 hour
    print("⚠️ Work stuck in queue > 1 hour")
    # Consider manual claim or reassignment
```

---

## Best Practices

### Work Context Quality

Provide comprehensive context to agents:

**Good:**
```python
context={
    "title": "Fix dashboard health check false positives",
    "description": "Docker health checks use 'wget' which isn't installed. Change to 'curl'. Services are actually healthy (logs show 200 OK).",
    "files_to_modify": [
        "docker/docker-compose.yml",
        "apps/dashboard/Dockerfile"
    ],
    "current_behavior": "Health check fails, dashboard shows unhealthy",
    "expected_behavior": "Health check passes, dashboard shows healthy",
    "validation": "Run 'docker ps' and verify healthy status",
    "priority": "medium"
}
```

**Bad:**
```python
context={
    "title": "Fix dashboard",
    "description": "It's broken"
}
```

### Clear Success Criteria

Always define what "done" looks like:

```python
context={
    ...
    "success_criteria": [
        "Health check passes in docker ps",
        "Dashboard shows healthy status",
        "No changes to service functionality",
        "Validated with actual health check request"
    ]
}
```

### Priority Guidelines

- **High**: Blocking work, security issues, production bugs
- **Medium**: Important but not urgent, quality improvements
- **Low**: Nice-to-haves, tech debt, optimizations

---

## Tools & Resources

### Agent-Mail Skill

```python
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/agent-mail/agent_mail')

# All available functions:
from skill_helpers import (
    send_work,
    claim_work,
    register_agent,
    unregister_agent,
    get_category_stats,
    check_inbox,
    get_work,
    get_result,
    submit_result,
    health_check
)
```

### Memoria Skill (RAG)

```python
import sys
sys.path.insert(0, '/Users/igorcandido/Github/thinker/claude_infra/skills/memoria/memoria')

from skill_helpers import search_knowledge, health_check

# Query for patterns, examples, documentation
results = search_knowledge(
    query="agent-mail workflow patterns",
    mode="hybrid",
    expand=True,
    limit=5
)
```

### MCP Tools

Use MCP tools for specialized tasks:
- `mcp__memoria__search_knowledge` - RAG queries
- `mcp__ast-grep__find_code` - Structural code search
- `mcp__workdiary__add_todo` - Task tracking
- `mcp__chronos__schedule_task` - Scheduled jobs

---

## Common Scenarios

### Scenario 1: Dashboard Implementation

```python
# Send to coder
work_id = send_work(
    from_id="igor-claude",
    to_category="coder",
    task_type="implementation",
    context={
        "title": "Build agent-mail dashboard MVP",
        "description": "Add agent-mail section to main dashboard...",
        "requirements": {...},
        "files_to_create": [...],
        "files_to_modify": [...],
        "success_criteria": [...]
    }
)

# Monitor progress
get_category_stats("coder")

# Review result
result = get_result(work_id, "igor-claude")

# Send for review
review_id = send_work(
    from_id="igor-claude",
    to_category="reviewer",
    task_type="code_review",
    context={
        "title": "Review dashboard implementation",
        "files": result["files_modified"],
        "focus": ["security", "performance", "maintainability"]
    }
)
```

### Scenario 2: Bug Investigation

```python
# Send to coder (investigations)
work_id = send_work(
    from_id="igor-claude",
    to_category="coder",
    task_type="bug_investigation",
    context={
        "title": "Investigate chronos HTTP 500 errors",
        "description": "User reports 500 errors but services show healthy...",
        "investigation_steps": [...],
        "log_locations": [...],
        "deliverables": ["Root cause", "Fix plan"]
    }
)
```

### Scenario 3: Design Planning

```python
# Send to planner
work_id = send_work(
    from_id="igor-claude",
    to_category="planner",
    task_type="architecture_planning",
    context={
        "title": "Plan memoria Phase 4 migration testing",
        "description": "Phase 3 complete, need Phase 4 plan...",
        "goals": [...],
        "constraints": [...],
        "deliverables": [...]
    }
)
```

---

## Troubleshooting

### Workers Not Claiming Work

1. Check if workers registered:
   ```python
   stats = get_category_stats("coder")
   print(f"Active agents: {stats['active_agents']}")
   ```

2. Start workers if needed:
   ```bash
   # In separate terminal
   launch-claude coder
   ```

3. Check service health:
   ```python
   health_check()
   ```

### Work Stuck in Queue

1. Check work age:
   ```python
   stats = get_category_stats("coder")
   print(f"Oldest work: {stats['oldest_work_age']}s")
   ```

2. Manually claim if stuck:
   ```python
   work = claim_work(agent_id="igor-claude", category="coder")
   # Execute manually
   submit_result(work.work_id, "igor-claude", result={...})
   ```

### Service Connection Issues

1. Check service running:
   ```bash
   lsof -i :9006  # Agent-mail port
   ```

2. Check logs:
   ```bash
   tail -f /tmp/agent-mail-server-9007.log
   ```

3. Restart if needed:
   ```bash
   cd ~/Github/thinker/claude_infra/apps/agent-mail-mcp-server
   ./start-server-http.sh
   ```

---

## Success Metrics

Track these to measure system health:

- **Queue size**: < 10 items per category (green)
- **Worker utilization**: 50-80% (optimal)
- **Completion rate**: > 90% success (no failures)
- **Response time**: < 5 minutes from claim to submit
- **Learning system**: Active adjustments after 10+ outcomes

---

**Status**: ✅ Production Guidelines
**Next Steps**: Query these guidelines on startup, refer back as needed
**Feedback**: Improve these guidelines based on your experience
