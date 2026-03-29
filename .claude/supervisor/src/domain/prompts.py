"""Shared prompts for supervisor v0.2.

These prompts are used by various adapters for LLM-based verification
and completion checking. Keeping them centralized ensures consistency
across the codebase.
"""

# LLM verification prompt for completion checking
# Used by LLMCompletionVerifier adapter to analyze Claude's output
# Format parameter: {0} = session output to analyze
VERIFICATION_PROMPT = """You are reviewing the output from a Claude Code session that was tasked with implementing feature tasks.

Analyze the session output below and determine: Did the Claude instance clearly indicate that ALL implementation work is COMPLETE and ready?

Consider COMPLETE if:
- It states tasks are finished/complete/done
- It indicates "this is the end" or "work is complete"
- It says it's production-ready or ready for review/merge
- Has final status summary indicating completion
- Tasks are explicitly marked as "DEFERRED - ACCEPTABLE" or "NOT BLOCKING" or "FUTURE ENHANCEMENT" with justification

Do NOT consider complete if:
- It only completed SOME tasks without explanation (e.g., "completed 50 out of 70")
- It's waiting for more work or continuing
- It hit context limits and is just summarizing progress so far
- It says work is "blocked" or "paused"
- Tasks are marked TODO or incomplete without justification

IMPORTANT: Tasks marked as "DEFERRED", "FUTURE WORK", "NOT BLOCKING", "ACCEPTABLE" with clear reasoning ARE considered complete if the instance declares overall work finished.

Session output:
---
{}
---

Answer ONLY with YES or NO based on your judgment of whether this instance truly finished ALL its work."""


# Default worker prompt embedded in the supervisor
# Used when no prompt.md file exists in the project root or .claude/supervisor/
DEFAULT_WORKER_PROMPT = """/speckit.implement

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

*** ABSOLUTE REQUIREMENT - NO EXCEPTIONS ***

DO EVERY SINGLE TASK IN TASKS.MD. PERIOD.

Priority labels (CRITICAL, HIGH, MEDIUM, LOW) are DECORATIVE ONLY. They mean NOTHING.
- MEDIUM priority tasks? MANDATORY.
- LOW priority tasks? MANDATORY.
- Tasks labeled "optional"? MANDATORY.
- Tasks labeled "nice-to-have"? MANDATORY.
- Tasks labeled "polish"? MANDATORY.
- Tasks labeled "future work"? MANDATORY.

ALL tasks have IDENTICAL priority: MANDATORY.

If a task has a checkbox [ ], you MUST either:
1. Complete it and mark [x], OR
2. Defer it with [x] + 3-element justification (see DEFERRAL POLICY)

Before claiming "work complete", run this verification:
```bash
grep -c "^\- \[ \]" specs/*/tasks.md
```

If that returns anything other than 0, your work is NOT complete.

Task types that are MANDATORY (not suggestions):
- Regular tasks (T001-T999): MANDATORY
- Bruce Lee tasks (BR-001-BR-999): MANDATORY (every single one)
- Quality tasks (QA001-QA999): MANDATORY
- Supervisor tasks (T074b-T074e): MANDATORY
- Refactoring tasks: MANDATORY
- Documentation tasks: MANDATORY
- Test tasks: MANDATORY
- "Polish" tasks: MANDATORY

*** FINAL WARNING ***
If you skip ANY task because it's labeled "MEDIUM" or "LOW", you are FAILING this session.
Priority labels are MEANINGLESS. DO EVERY TASK.

When ALL tasks in tasks.md are checked [x] with NO unchecked [ ] tasks remaining, THEN AND ONLY THEN say "All work complete".

Before claiming "work complete" or exiting:

MANDATORY PRE-EXIT VERIFICATION:
```bash
# Run this command and show output
grep -c "^\- \[ \]" specs/*/tasks.md
```

Expected output: 0 (zero unchecked tasks)

If output is NOT zero:
- You CANNOT claim work is complete
- You MUST complete the remaining tasks OR defer them with [x] + justification
- Saying "work complete" with unchecked tasks will cause supervisor to loop/fail

Steps:
1. Verify EVERY task in tasks.md is marked [x] not [ ] (including deferred tasks!)
2. Run: grep -c "^\- \[ \]" specs/*/tasks.md
3. Show the output to user
4. If output = 0, then you can say "All work complete"
5. If output > 0, you MUST complete or defer those tasks first

Exit conditions:
1. ALL tasks checked [x] in tasks.md (0 unchecked tasks), OR
2. Reaching 70% of context window (then exit with status summary)

[WARNING] SUPERVISOR WILL DETECT FUTILE DEFERRAL LOOPS:
If you claim "complete" with same unchecked tasks 2 iterations in a row,
supervisor will exit with error. Either complete the tasks or mark [x] with justification."""
