# Claude Supervisor Worker Prompt

This is the default prompt sent to Claude Code instances when supervised by `claude_supervisor.py`.

You can customize this prompt for specific use cases, but be careful not to remove critical instructions.

---

/speckit.implement

CRITICAL: As you complete each task, IMMEDIATELY update tasks.md to mark it done:
- Change: - [ ] T001 Task description
- To:     - [x] T001 Task description

AGENTS.md is at root of repo, create if not there.

record onto AGENTS.md learnings and realizations that are useful for the work you are doing.

Maintain AGENTS.md with relevant context and keep it clean and useful not a pigsty

read from AGENTS.md learnings to be able to do your work better

BRUCE_LEE OPTIMIZATION:
- ONLY run bruce_lee if you made CODE changes in this iteration
- Before running bruce_lee, check: git diff --stat specs/*/tasks.md
- If ONLY tasks.md changed (task marking), SKIP bruce_lee (saves 2-3 minutes)
- If code files changed, then run bruce_lee agent to verify work

bruce_lee recommendations are to be add to speckit tasks.md, all recommendations

Check off tasks as you complete them: - [ ] becomes - [x]

DEFERRAL POLICY - READ CAREFULLY:
Tasks are NOT deferrable by default. You MUST attempt every task.

Only defer a task if ALL conditions met:
1. PHYSICALLY IMPOSSIBLE (not just inconvenient or slow)
   - [BAD] "Requires Zellij setup" (you can install it!)
   - [BAD] "Integration tests are slow" (slow != impossible)
   - [GOOD] "Requires production API keys not in dev environment"

2. NON-BLOCKING (deferring doesn't prevent other work)
   - [BAD] Defer unit tests (blocks verification)
   - [GOOD] Defer optional performance benchmarks

3. MARK AS [x] WITH DETAILED JUSTIFICATION:
   - [x] T019 Integration test - DEFERRED: Requires production Stripe API keys
     not available in dev environment (acceptable - mocked in unit tests,
     validated in staging). Alternative: Unit tests with mocks cover all paths.

[WARNING] CRITICAL: Deferred tasks MUST be marked [x], NOT left as [ ].
[WARNING] If you defer without proper justification, supervisor will reject and loop.

CRITICAL: Do ALL tasks in tasks.md regardless of priority labels or task type.
- CRITICAL priority? Do it.
- HIGH priority? Do it.
- MEDIUM priority? Do it.
- LOW priority? Do it anyway.
- "Optional"? NOT optional - do it.
- "Deferred"? NOT deferred - do it now.
- Regular tasks (T001-T999)? Do them.
- Bruce Lee tasks (BR-001-BR-999)? Do them.
- Quality tasks (QA001-QA999)? Do them.
- Supervisor tasks (T074b-T074e)? Do them.

**Priority labels are IRRELEVANT. ALL unchecked tasks must be completed before saying work is done.**

When ALL tasks in tasks.md are checked [x] with NO unchecked [ ] tasks remaining, THEN AND ONLY THEN say "All work complete".

Before exiting:
1. Verify EVERY task in tasks.md is marked [x] not [ ] (including deferred tasks!)
2. Count: grep -c "^\- \[ \]" specs/*/tasks.md MUST return 0
3. If ANY unchecked tasks remain, either:
   - Complete them, OR
   - Defer with [x] + detailed justification (if truly impossible)

Exit conditions:
1. ALL tasks checked [x] in tasks.md (0 unchecked tasks), OR
2. Reaching 70% of context window (then exit with status summary)

[WARNING] SUPERVISOR WILL DETECT FUTILE DEFERRAL LOOPS:
If you claim "complete" with same unchecked tasks 2 iterations in a row,
supervisor will exit with error. Either complete the tasks or mark [x] with justification.
