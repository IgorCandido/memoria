# Claude Supervisor

Automated supervision system for long-running Claude Code tasks with context limit recovery, progress monitoring, and intelligent failure detection.

## Overview

Claude Supervisor automatically manages Claude Code execution across multiple iterations, handling context limits, monitoring progress, and detecting failures. When Claude hits token limits mid-task, the supervisor restarts it seamlessly, preserving work and continuing from where it left off.

**Key capabilities:**
- **Automatic context recovery**: Restarts Claude when context limits hit
- **Progress tracking**: Monitors `tasks.md` completion via checkbox detection
- **Health monitoring**: Detects timeouts, broken pipes, and output stalls (v0.4)
- **Loop detection**: Identifies stuck states after 3 no-progress iterations
- **Zellij integration**: Live output streaming in terminal multiplexer (optional)
- **Hexagonal architecture**: Swappable adapters for execution, storage, and feedback

## Prerequisites

**⚠️ CRITICAL: This supervisor is deeply integrated with SpecKit and will NOT work without it.**

### SpecKit Dependency

The Claude Supervisor is built specifically for the SpecKit workflow system and requires:

1. **SpecKit infrastructure**: The supervisor expects SpecKit's directory structure, task format, and commands
2. **Specification-driven development**: Projects must use SpecKit's `specs/###-feature-name/` directory structure
3. **Task tracking format**: SpecKit's `tasks.md` format with `[x]` checkbox completion markers
4. **Implementation command**: Executes workers via SpecKit's `/speckit.implement` command

**What SpecKit provides:**
- Structured feature specification workflow (specify → plan → tasks → implement)
- Standardized task format that supervisor can parse (`- [x] T001 Task description`)
- Implementation execution framework via `/speckit.implement` command
- Integration with Claude Code's skill system

**Where to get SpecKit:**
- SpecKit is included in Claude Code projects via `.specify/` directory
- Initialize with `claude-code` or copy SpecKit templates to your project
- See SpecKit documentation for setup: [SpecKit README](.specify/README.md)

**Without SpecKit:**
- Supervisor cannot find `specs/*/tasks.md` files → fails with EXIT_WORKTREE_NOT_FOUND
- `/speckit.implement` command unavailable → workers fail to start
- Task completion detection fails → stuck loop or infinite iterations

**Integration flow:**
```
1. SpecKit: Define feature spec (speckit.specify)
2. SpecKit: Generate tasks (speckit.tasks)
3. Supervisor: Execute workers with /speckit.implement
4. Supervisor: Monitor tasks.md for [x] completion
5. Supervisor: Restart on context limits until done
```

### Other Requirements

- **Python 3.11+**: Supervisor runtime
- **Claude Code CLI**: `claude` command in PATH
- **AWS Bedrock access**: Configured via `~/.aws/credentials` (or swap ClaudeRunner adapter)
- **macOS Monterey+ or Linux**: Ubuntu 20.04+, Debian 11+
- **Zellij 0.38+**: Optional, for PTY streaming and live pane display

## Features by Version

### v0.4 - Health Monitoring & Progress Visibility (Current)
- ENV-based timeout configuration (`CLAUDE_TIMEOUT_*`)
- Real-time progress indicators with status markers and elapsed time
- `select()`-based output health detection (non-blocking)
- Threading model for concurrent progress display
- Comprehensive port-adapter health monitoring interfaces

### v0.3 - CLI Installer & PTY Streaming
- One-line global installation (`curl | bash`)
- Per-project supervisor isolation with version pinning
- PTY streaming capture for complete output (tool calls, thinking, ANSI)
- Dual logging: rich logs (ANSI) + clean logs (automation)
- Optional Zellij live pane display

### v0.2 - Hexagonal Architecture
- Port-adapter pattern for execution strategies
- Protocol-based interfaces (structural typing)
- Fast unit tests (<5s) with stub implementations
- Swappable components: runners, storage, feedback, verification

### v0.1 - Initial Implementation
- Basic supervision loop with task monitoring
- Context limit detection and restart logic
- Simple subprocess execution model

## Quick Start

### Installation

**Step 1: Ensure SpecKit is set up in your project**

The supervisor requires SpecKit infrastructure. Verify:
```bash
# Check for SpecKit directory
ls .specify/

# Check for a spec with tasks.md
ls specs/*/tasks.md
```

If SpecKit is not installed, initialize it first (see SpecKit documentation).

**Step 2: Install the supervisor**

**One-line install (requires gh CLI for private repos):**
```bash
gh api repos/IgorCandido/claude-supervisor/contents/installer/install.sh \
  --jq '.content' | base64 -d | bash
```

**Initialize in your project:**
```bash
cd your-project
claude-supervisor-install init .
```

### AWS Credentials Setup

Create `~/.aws/credentials`:
```ini
[claude-code]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

Create `~/.aws/config`:
```ini
[profile claude-code]
region = us-west-2
output = json
```

Verify:
```bash
aws bedrock list-foundation-models --region us-west-2 --profile claude-code
```

### Basic Usage

**Complete workflow with SpecKit:**

```bash
# 1. Create a feature spec (SpecKit)
/speckit.specify "user authentication"

# 2. Generate implementation tasks (SpecKit)
/speckit.tasks

# 3. Run supervised implementation (Supervisor)
cd 001-user-authentication  # SpecKit worktree
claude-supervisor

# The supervisor will:
# - Execute /speckit.implement in the worktree
# - Monitor specs/001-user-authentication/tasks.md for [x] completion
# - Restart Claude on context limits until all tasks complete
```

**Advanced usage:**

```bash
# Custom timeout (10 minutes for output detection)
CLAUDE_TIMEOUT_OUTPUT=600 claude-supervisor

# Disable Zellij integration in CI/CD
SUPERVISOR_DISABLE_ZELLIJ=1 claude-supervisor

# Increase stuck loop threshold
SUPERVISOR_STUCK_THRESHOLD=5 claude-supervisor
```

**What the supervisor does:**

1. Navigates to the worktree (e.g., `001-user-authentication/`)
2. Finds `specs/001-user-authentication/tasks.md`
3. Runs `claude` with `/speckit.implement` prompt
4. Monitors output for timeouts (default: 5 minutes)
5. Parses `tasks.md` after each iteration for `[x]` checkboxes
6. Restarts on context limits if tasks incomplete
7. Exits when all tasks marked `[x]` or stuck loop detected

## Configuration

### Health Monitoring (v0.4)

Control output timeout detection:

```bash
# Output timeout (seconds) - default: 300 (5 minutes)
export CLAUDE_TIMEOUT_OUTPUT=300

# Worker timeout (seconds) - default: 3600 (1 hour)
export CLAUDE_TIMEOUT_WORKER=3600

# Iteration timeout (seconds) - default: 7200 (2 hours)
export CLAUDE_TIMEOUT_ITERATION=7200
```

### Progress Display (v0.4)

Progress indicators show real-time status with configurable markers:

```bash
# Status markers (defaults shown)
export CLAUDE_STATUS_WAITING="⏳"
export CLAUDE_STATUS_RUNNING="🔄"
export CLAUDE_STATUS_TIMEOUT="⏰"
export CLAUDE_STATUS_COMPLETED="✅"

# Disable progress display
export CLAUDE_PROGRESS_ENABLED=false
```

**Output format:**
```
⏳ Waiting for output... (0:00:15)
🔄 Processing... (0:02:34)
⏰ Output timeout detected (0:05:00)
✅ Iteration complete (0:03:45)
```

### Zellij Integration (v0.3)

```bash
# Disable Zellij integration
export SUPERVISOR_DISABLE_ZELLIJ=1

# Pane configuration
export SUPERVISOR_PANE_DIRECTION=down          # down|right|left|up
export SUPERVISOR_PANE_NAME_TEMPLATE="Claude Worker {iteration}"
export SUPERVISOR_AUTO_CLOSE_PANES=false       # Keep panes after completion
```

### Environment Variables (v0.2)

Automatically set by supervisor:
- `CLAUDE_CODE_USE_BEDROCK=1`
- `AWS_REGION=us-west-2`
- `AWS_PROFILE=claude-code`

### Limits

```bash
# Maximum iterations before forced exit
export SUPERVISOR_MAX_ITERATIONS=20            # Default: 20

# Stuck loop detection threshold
export SUPERVISOR_STUCK_THRESHOLD=3            # Default: 3 (no-progress iterations)
```

## How It Works

### Supervision Loop

```
1. Run Claude with /speckit.implement prompt
2. Monitor output for timeout/completion
3. Parse tasks.md for [x] checkbox completion
4. Detect stuck state (3 iterations, no progress)
5. If incomplete and not stuck → restart (goto 1)
6. If complete or stuck → exit with appropriate code
```

### Health Monitoring (v0.4)

**Output Timeout Detection:**
- `select()` monitors stdout for activity with configurable timeout
- Non-blocking detection (checks every 100ms)
- Triggers restart if no output for `CLAUDE_TIMEOUT_OUTPUT` seconds
- Default: 5 minutes (300s)

**Progress Visibility:**
- Background thread displays real-time status
- Shows elapsed time, spinner animation, status markers
- Updates every 100ms during active execution
- Thread-safe coordination with main supervision loop

**Port-Adapter Health Monitoring:**
- `HealthMonitor` port: Abstract interface for timeout detection
- `SelectBasedHealthMonitor` adapter: Non-blocking `select()` implementation
- Swappable implementations for different detection strategies

### Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `EXIT_SUCCESS` | All tasks completed |
| 1 | `EXIT_ERROR` | General error |
| 2 | `EXIT_INVALID_ARGS` | Invalid arguments |
| 3 | `EXIT_WORKTREE_NOT_FOUND` | Invalid worktree path |
| 4 | `EXIT_MAX_ITERATIONS` | Stuck loop detected |
| 130 | `EXIT_SIGINT` | User interrupted (Ctrl+C) |

**Shell script usage:**
```bash
claude-supervisor -p "Fix bug"
case $? in
    0) echo "✅ Complete" ;;
    4) echo "⚠️ Stuck loop" ;;
    130) echo "🛑 Interrupted" ;;
    *) echo "❌ Error" ;;
esac
```

## Logging

### Log Files

Logs saved to `.claude_supervisor/` directory:

**PTY streaming (Zellij enabled):**
- `YYYYMMDD_HHMMSS-iterNNN.log` - Full output with ANSI codes
- `YYYYMMDD_HHMMSS-iterNNN_stdout.log` - Clean stdout only

**Standard subprocess (Zellij disabled):**
- `YYYYMMDD_HHMMSS-iterNNN.log` - Combined stdout/stderr

### Security Considerations

**⚠️ Logs may contain sensitive data:**
- API keys, tokens, credentials
- Environment variables
- File paths and project structure
- Debug output from Claude

**Best practices:**
1. Review logs before sharing: `cat .claude_supervisor/*.log`
2. Never commit `.claude_supervisor/` to git (already in `.gitignore`)
3. Rotate logs on shared machines: `find .claude_supervisor/ -mtime +7 -delete`
4. Use `SUPERVISOR_DISABLE_ZELLIJ=1` in CI/CD to minimize output capture

## Architecture

### Hexagonal Design (v0.2)

```
src/
├── domain/                    # Business logic (no I/O)
│   ├── entities.py            # TaskCounts, RunResult, SessionResult, OutputTimeout
│   ├── supervisor_session.py  # Orchestration logic
│   ├── exit_codes.py          # Exit code constants
│   └── prompts.py             # Verification prompts
│
├── ports/                     # Interface contracts (Protocols)
│   ├── claude_runner.py       # Execute Claude instances
│   ├── task_repository.py     # Read/parse tasks.md
│   ├── output_logger.py       # Log iteration output
│   ├── completion_verifier.py # LLM-based verification
│   ├── user_feedback.py       # User notifications
│   └── health_monitor.py      # Output timeout detection (v0.4)
│
└── adapters/                  # Concrete implementations
    ├── subprocess_runner.py    # Standard subprocess execution
    ├── zellij_runner.py        # PTY streaming with Zellij (v0.3)
    ├── filesystem_tasks.py     # Read specs/*/tasks.md
    ├── filesystem_logger.py    # Write to .claude_supervisor/
    ├── llm_verifier.py         # Claude subprocess verification
    ├── console_feedback.py     # Print to stdout/stderr
    ├── select_health_monitor.py # select()-based timeout detection (v0.4)
    └── progress_indicator.py   # Real-time progress display (v0.4)
```

**Design principles:**
- Domain layer has zero I/O dependencies
- Ports define interfaces via `Protocol` (structural subtyping)
- Adapters are swappable via dependency injection
- Entry point (`cli.py`) wires adapters into domain

### Adding Custom Adapters

**Example: Docker-based execution**

1. Implement `ClaudeRunner` port:
```python
# src/adapters/docker_runner.py
from src.domain.entities import RunResult
from src.ports.claude_runner import ClaudeRunner

class DockerClaudeRunner:
    def run(self, prompt: str, working_dir: str, timeout: int = 3600) -> RunResult:
        # Run Claude in Docker container
        pass
```

2. Update CLI (3 lines):
```python
# src/cli.py
from src.adapters.docker_runner import DockerClaudeRunner

runner = DockerClaudeRunner()  # Changed from SubprocessClaudeRunner
session = SupervisorSession(..., runner=runner, ...)
```

3. Verify with contract tests:
```bash
pytest tests/contracts/test_claude_runner_contract.py::test_contract[DockerClaudeRunner]
```

## Development

### Running Tests

```bash
# Unit tests (fast, no I/O) - <5s
pytest tests/unit/ -v

# Contract tests (adapter conformance)
pytest tests/contracts/ -v

# Integration tests (behavioral equivalence)
pytest tests/integration/ -v

# All tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

### Test Categories

- **Unit tests**: Domain logic with stub adapters (no subprocess, no filesystem)
- **Contract tests**: Verify adapters conform to port interfaces
- **Integration tests**: End-to-end behavioral validation

### Prerequisites for Development

- Python 3.11+
- pytest, pytest-cov
- Claude Code CLI in PATH
- AWS credentials configured (for integration tests)

## CI/CD

### Continuous Integration

Every push to `main` and every pull request triggers the CI workflow (`.github/workflows/ci.yml`):

- Runs the full Python test suite (`pytest tests/ -v --tb=short`)
- Runs installer unit tests (`tests/installer/unit/run-all-tests.sh`)

Fork PRs run in an isolated environment with a read-only `GITHUB_TOKEN` and no access to repository secrets.

Check the **Actions** tab on GitHub for results.

### Releasing

Releases are automated via GitHub Actions. Push a version tag to create a release:

```bash
git tag v0.5.0
git push origin v0.5.0
```

The release workflow (`.github/workflows/release.yml`) runs tests, packages the tarball, creates a GitHub Release with assets, and validates installers on Linux and macOS.

Pre-release tags (containing a hyphen, e.g. `v0.5.0-beta.1`) are automatically marked as pre-release on GitHub.

If tests fail, no release is created.

## Troubleshooting

### Claude won't start

**Check AWS credentials:**
```bash
aws bedrock list-foundation-models --region us-west-2 --profile claude-code
```

**Verify Claude CLI:**
```bash
which claude
claude --version
```

### Stuck loop detected (exit code 4)

Supervisor detected 3 consecutive iterations with no task progress.

**Causes:**
- Worker asking permission questions (will be addressed in v0.5)
- Worker stuck in infinite reasoning loop
- Tasks too large for context window

**Solutions:**
- Review last 3 logs for repeated output: `tail -100 .claude_supervisor/*iter00{7,8,9}.log`
- Break tasks into smaller units in `tasks.md`
- Increase `SUPERVISOR_STUCK_THRESHOLD` if false positive

### Output timeout (default: 5 minutes)

No output detected for `CLAUDE_TIMEOUT_OUTPUT` seconds.

**Causes:**
- Worker hung on LLM call
- Long-running command with no stdout
- Broken pipe/PTY closure

**Solutions:**
- Increase timeout: `export CLAUDE_TIMEOUT_OUTPUT=600` (10 minutes)
- Check logs for last output: `tail -50 .claude_supervisor/*iter*.log`
- Verify network connectivity for LLM calls

### Zellij panes accumulate

**Disable auto-cleanup:**
```bash
export SUPERVISOR_AUTO_CLOSE_PANES=false
```

**Manual cleanup:**
```bash
# Close all Claude Worker panes
zellij action close-pane --name "Claude Worker*"
```

### Logs contain sensitive data

**Prevent exposure:**
1. Review before sharing: `less .claude_supervisor/*.log`
2. Redact sensitive lines: `sed -i '' '/API_KEY/d' .claude_supervisor/*.log`
3. Use clean logs only: `cat .claude_supervisor/*_stdout.log`

## FAQ

**Q: Why does supervisor restart Claude so often?**
A: Claude Code has a context window limit (~200K tokens). Complex tasks exceed this, requiring restarts to continue work.

**Q: Can I use this with Claude API instead of Bedrock?**
A: Yes, swap the `ClaudeRunner` adapter to use Anthropic API instead of AWS Bedrock. See "Adding Custom Adapters" section.

**Q: What happens if I Ctrl+C during execution?**
A: Supervisor catches SIGINT (130), saves current logs, and exits gracefully. Work up to that point is preserved.

**Q: Why are there two log files per iteration (with Zellij)?**
A: Streaming log captures full PTY output (ANSI codes, tool calls, thinking). Stdout log is clean for automation/parsing.

**Q: How do I disable progress indicators?**
A: `export CLAUDE_PROGRESS_ENABLED=false` before running supervisor.

**Q: Can I run this in CI/CD?**
A: Yes, use `SUPERVISOR_DISABLE_ZELLIJ=1` to disable interactive features and ensure clean log output.

## Roadmap

### v0.5 - Question Detection (Planned)
- Detect worker continuation questions at phase boundaries
- Inject affirmative answers to prevent false stuck loops
- Pattern matching for 4 standard question formats
- 95%+ detection accuracy for legitimate checkpoints

### v0.6 - Stream Health Detection (Planned)
- Detect broken pipes within 1 second (vs 5-minute timeout)
- Handle EPIPE, EIO, EBADF errors via `select()` exceptional conditions
- Zellij pane cleanup with 2-second timeout
- Coexist with timeout detection (complementary mechanisms)

### v0.7 - Testing & Polish (Planned)
- Contract tests for all health monitoring ports
- Unit tests for threading, ENV parsing, display formatting
- Integration tests for progress visibility and question injection
- Port abstraction for ProgressDisplay

## License

MIT License - see LICENSE file for details.

---

**Version**: 0.4 (health monitoring & progress visibility)
**Status**: Active development
**Maintainer**: Igor Candido
**Repository**: https://github.com/IgorCandido/claude-supervisor
