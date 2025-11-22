# Claude Infrastructure Management

## Infrastructure Services

### Core Infrastructure
- **ChromaDB**: port 8000 (RAG vector database)
- **Redis**: port 6379 (single instance, multi-purpose)
  - Hook throttling (`hooks:throttle:*`)
  - MCP session persistence (`mcp:sessions:*`)
  - Distributed test mutex (`test:mutex:*`)
  - Chronos job scheduling (`chronos:*`)
- **PostgreSQL**: port 5435 (workdiary), port 5434 (chronos)
- **Kafka**: port 9092 (event streaming)
- **Kafka UI**: port 8080 (management dashboard)

### Chronos Services
- **chronos-postgres**: port 5434 (task metadata & history)
- **chronos-mcp-server**: port 9004 (MCP scheduling interface)
- **chronos-worker**: Background task executor
- **chronos-web-ui**: port 3000 (management dashboard)

### Monitoring & Dashboards
- **Infrastructure Monitor Dashboard**: port 9001 (service health monitoring)
- **Ollama Test Dashboard**: port 9000 (test execution monitoring)

### Ollama MCP Server

**Purpose**: AI-powered test execution and text processing tools via local LLM

**Status**: Deployed ✅ (Docker container on port 9005)

**Architecture**:
```
Claude Code → Audit Wrapper → Facade (STDIO→HTTP) → ollama-mcp (Docker) → Ollama Daemon (host)
```

**Key Features**:
- **Test Execution**: Streaming test runner with real-time progress (run_tests_stream)
- **Compilation**: sbt compile/warningsCheck with structured errors
- **Text Processing**: expand_query, summarize_text, extract_errors
- **Workdiary Helpers**: improve_log_message, enhance_todo, validate_workdiary_entry
- **17 MCP tools** exposed via HTTP transport

**Why Docker + HTTP?**:
- STDIO breaks on long operations (30+ second compilations)
- HTTP allows reconnection/retry and better cancellation support
- Docker provides isolation and resource management
- Facade provides security audit logging

**Dependencies**:
- **Ollama Daemon**: host.docker.internal:11434 (brew service)
- **Kafka**: kafka:29092 (event streaming for test events)
- **Shared Library**: /app/shared (ollama-shared utilities)

**Health Check Status**: ⚠️ Currently returns 404 for `/health`
- See `apps/ollama-mcp/DOCKER-HEALTH-CHECK-IMPROVEMENTS.md` for functional health check design
- Priority P1: Implement `/health` endpoint with Ollama/Kafka/tools verification

**Quick Recovery** (if hung/unresponsive):
```bash
# Use management scripts
~/Github/thinker/claude_infra/bin/stop-ollama-mcp.sh
~/Github/thinker/claude_infra/bin/start-ollama-mcp.sh
docker restart ollama-llm-facade
pkill -f "http-bridge-wrapper.*ollama"
```

**Troubleshooting**:
```bash
# Check server status
lsof -i :9005 | grep LISTEN
tail -f /tmp/ollama-mcp.log

# Test MCP connectivity
curl -X POST http://localhost:9005/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Check facade logs
docker logs ollama-llm-facade --tail 20 | grep ERROR

# Verify Ollama daemon running
brew services list | grep ollama
curl http://localhost:11434/api/tags
```

**Documentation**:
- `apps/ollama-mcp/CLAUDE.md` - **⭐ Complete operational guide and troubleshooting**
- `apps/ollama-mcp/MCP_SERVER_HUNG_INVESTIGATION_2025-10-13.md` - Root cause analysis of hung server incident
- `apps/ollama-mcp/README.md` - Comprehensive tool documentation
- `apps/ollama-mcp/DOCKER-HEALTH-CHECK-IMPROVEMENTS.md` - Health check design
- `apps/ollama-mcp/SESSION-SUMMARY-2025-10-10.md` - Docker migration session

**Query RAG for**: `"ollama-mcp hung server recovery"`, `"mcp troubleshooting"`, `"ollama-mcp operations"`

### Redis Architecture Decision

**Single Instance with Namespaced Keys** (not multiple databases)

**Rationale**:
- Low usage across all purposes - no need for separate instances
- Easier management and monitoring
- Avoids Docker container sprawl (3+ containers → 1)
- Namespaced keys provide logical separation
- Simple to reason about and debug

**Key Namespace Conventions**:
- `hooks:throttle:<action>:<ppid>` - Hook message deduplication (5min TTL)
- `mcp:sessions:<session_id>` - MCP server session state (30min TTL)
- `test:mutex:<test_name>` - Distributed test coordination (10min TTL)
- `chronos:*` - Chronos job scheduling system (see Chronos section below)

**Why Not Multiple Databases?**
- Redis multi-DB is legacy, not recommended for production
- Can't set different eviction/persistence per DB
- `FLUSHALL` affects all DBs
- Not compatible with Redis Cluster
- Namespaced keys are clearer and more flexible

## Chronos - Task Scheduling System

**Status**: Deployed ✅ (as of 2025-10-08)

Chronos is a production-grade task scheduling system with MCP interface for Claude Code integration.

### Services

All chronos services run on the `claude-network` Docker network:

- **chronos-postgres** (port 5434): PostgreSQL database for task metadata and execution history
- **chronos-mcp-server** (port 9004): FastMCP server providing scheduling tools to Claude Code
- **chronos-worker**: Background worker executing scheduled tasks
- **chronos-web-ui** (port 3000): Next.js management dashboard

### Redis Integration

**Migration Completed**: 2025-10-08

Chronos was migrated from dedicated Redis (`chronos-redis` on port 6382) to shared `common-redis` (port 6379) with namespaced keys.

**Chronos Redis Key Patterns**:
- `chronos:task:<task_id>` - Task metadata (name, schedule, script path, params)
- `chronos:queue:<priority>` - Priority buckets (critical, high, normal, low) using sorted sets
- `chronos:executions:<task_id>` - Recent execution history (last 10 executions per task)
- `chronos:script:<script_name>` - Uploaded script metadata
- `chronos:notifications` - Redis pub/sub channel for real-time events

**Implementation**:
- All Redis operations in `chronos-mcp-server` and `chronos-worker` use `redis_key()` helper
- Configurable via `REDIS_PREFIX=chronos` environment variable
- Clean separation from other services using same Redis instance

### MCP Tools Available

Via Claude Code's `.claude.json` configuration (http-bridge-wrapper on port 9004):
- `schedule_task`: Schedule new tasks with cron expressions or delays
- `cancel_task`: Cancel scheduled tasks
- `list_schedules`: List all scheduled tasks with filters
- `get_task_status`: Get task status and execution history
- `upload_script`: Upload Python/Bash/JavaScript/Ruby scripts for execution

### Monitoring

All chronos services are monitored by `infrastructure-monitor` and visible on the dashboard at http://localhost:9001/

Health checks use `host.docker.internal` for cross-network communication.

**Query RAG for**: `"chronos mcp usage"`, `"chronos architecture"`, `"task scheduling patterns"`

## ⚠️ Migration Notice

**ACTION REQUIRED**: Active docker-compose infrastructure is currently in `~/Github/thinker/claude-infrastructure/`

**Current Situation**:
- This directory (`claude_infra`) contains canonical documentation and architecture decisions
- Active docker-compose.yml with common-redis, PostgreSQL, Kafka runs from `~/Github/thinker/claude-infrastructure/`
- **This split is confusing and needs consolidation**

**Migration Plan**:
1. Move docker-compose.yml from `claude-infrastructure/` → `claude_infra/docker/`
2. Move redis.conf to `claude_infra/config/`
3. Test new docker-compose location
4. Deprecate old `claude-infrastructure/` directory

**See**: `~/Github/thinker/claude-infrastructure/CLAUDE.md` for detailed migration steps

**Status**: Pending migration (as of 2025-10-08)

## Directory Structure

### `apps/`
**Central location for all infrastructure applications and services**

All infrastructure-related applications, tools, and services are stored in the `apps/` directory:
- MCP servers (workdiary, ast-grep, etc.)
- Monitoring tools
- Automation scripts
- Infrastructure utilities
- **localAgent_longTermMemory/** - LocalAgent's ChromaDB long-term memory storage

This centralized approach:
- Makes dependencies clear and explicit
- Simplifies maintenance and updates
- Provides single source of truth for infrastructure code
- Easier to track versions and changes

#### LocalAgent Memory Migration ✅

**Date**: 2025-10-08
**Status**: Complete

**What changed:**
- Moved: `~/.local_agent/memory` → `~/Github/thinker/claude_infra/apps/localAgent_longTermMemory/memory`
- Updated all code references to use new path
- Contains: LocalAgent's ChromaDB database (chroma.sqlite3 + collection data, ~588K)

**Files updated:**
- `src/memory/long_term_memory_store.py` - Factory function default
- `src/memory/long_term_memory_types.py` - Config default
- `src/cli/agent_app.py` - Fallback path
- `src/cli/main.py` - CLI help text and config template

**Rationale**:
- Centralizes all infrastructure data in one location
- Easier to backup, version control, and manage
- Consistent with other infrastructure components
- Clean migration with no legacy symlinks

## Management

### Manual Management

```bash
cd ~/Github/thinker/claude_infra/docker
docker-compose up -d
docker-compose down
docker-compose logs -f
```

### Auto-Start on Mac (LaunchAgent)

**Status**: ✅ Configured (as of 2025-10-10)

Infrastructure services auto-start on Mac boot via LaunchAgent.

**Location**: `~/Library/LaunchAgents/com.claude.infrastructure.plist`

**What it does**:
- Runs `docker-compose up -d` on Mac login
- Uses docker-compose.yml from `~/Github/thinker/claude_infra/docker/`
- Logs to `/tmp/claude-infrastructure-startup.log` and `.err`

**Check status**:
```bash
# Check if LaunchAgent is loaded
launchctl list | grep claude.infrastructure

# View LaunchAgent details
launchctl print gui/$(id -u)/com.claude.infrastructure

# Check startup logs
tail -f /tmp/claude-infrastructure-startup.log
tail -f /tmp/claude-infrastructure-startup.err
```

**Reload LaunchAgent** (after editing plist):
```bash
launchctl unload ~/Library/LaunchAgents/com.claude.infrastructure.plist
launchctl load ~/Library/LaunchAgents/com.claude.infrastructure.plist
```

**Troubleshooting**:

**Problem**: Services not auto-starting on Mac boot

**Check**:
```bash
# 1. Is LaunchAgent loaded?
launchctl list | grep claude.infrastructure

# 2. Check last exit code
launchctl print gui/$(id -u)/com.claude.infrastructure | grep "exit code"

# 3. Check error logs
tail -50 /tmp/claude-infrastructure-startup.err
```

**Common Issues**:
1. **Exit code 78 (EX_CONFIG)**: docker-compose.yml path is wrong
   - Fix: Update path in plist file
   - Common after directory moves/renames
2. **Exit code 1**: Docker daemon not running
   - Fix: Ensure Docker Desktop is running
3. **No logs**: LaunchAgent not loaded
   - Fix: `launchctl load ~/Library/LaunchAgents/com.claude.infrastructure.plist`

**Recent Fix (2025-10-10)**:
- LaunchAgent was pointing to old location (`~/Github/thinker/claude-infrastructure/`)
- Updated to new location (`~/Github/thinker/claude_infra/docker/`)
- Exit code 78 resolved

## Language Preferences for Infrastructure Projects

**Status**: Standardized ✅ (as of 2025-10-13)

All infrastructure applications follow consistent language choices:

### Backend: Python (Always)

**Rationale**:
- FastAPI for modern async web frameworks
- Rich ecosystem for infrastructure tools (Docker SDK, Kafka, Redis clients)
- Excellent async/await support for concurrent operations
- Strong typing with Pydantic for data validation
- Preferred for all MCP servers, monitoring tools, automation scripts

**Examples**:
- `apps/dashboard/backend/` - Dashboard aggregator (FastAPI)
- `apps/workdiary-mcp-server/` - Workdiary MCP (FastAPI)
- `apps/infrastructure-monitor/` - Infrastructure monitoring (Python)
- `apps/chronos-mcp-server/` - Chronos MCP (FastMCP)

### Frontend: TypeScript (Always)

**Rationale**:
- Type safety prevents runtime errors in production
- Better IDE support and refactoring capabilities
- React ecosystem is TypeScript-first
- Self-documenting code with interface definitions
- Scales better for large applications

**Examples**:
- `apps/dashboard/frontend/` - Dashboard UI (React + TypeScript + Vite)
- `apps/chronos-web-ui/` - Chronos management (Next.js + TypeScript)
- `apps/workdiary-web-ui/` - Workdiary UI (React + TypeScript)

### When to Deviate

**Never** - These preferences are absolute for claude_infra applications.

For non-infrastructure projects outside this repository, standard language selection applies.

**Query RAG for**: `"infrastructure language preferences"`, `"python backend standards"`, `"typescript frontend patterns"`

## Critical: Distributed Test Mutex

**MANDATORY for all tests**:
```bash
cd ~/Github/thinker/claude_infra
source .venv/bin/activate
python lib/test_runner_hooks.py sbt test
```

**All operational details → Query RAG**

Query: `"distributed test mutex integration"`, `"claude infrastructure monitoring"`

## Versioning & Distribution

### Repository Versioning

**Status**: Implemented ✅ (as of 2025-10-10)

This repository (`claude_infra`) uses semantic versioning to track infrastructure changes:

**Current Version**: 0.1.0
**Version File**: `VERSION`
**Changelog**: `CHANGELOG.md`

#### Semantic Versioning Rules

- **Patch (0.0.X)** - Bug fixes, docs, config tweaks, minor improvements
- **Minor (0.X.0)** - New features, significant refactoring, multiple component updates
- **Major (X.0.0)** - Breaking changes, major architecture changes, removal of deprecated features

#### Version Bump Script

Use `bin/version-bump` to manage versions:

```bash
# Patch bump (bug fixes, docs)
./bin/version-bump patch "Fix Redis connection handling"

# Minor bump (new features, updates)
./bin/version-bump minor "Add Grafana monitoring service"

# Major bump (breaking changes)
./bin/version-bump major "Breaking: Migrate to Redis Cluster"
```

The script automatically:
1. Updates `VERSION` file
2. Updates `CHANGELOG.md` with dated entry and change description
3. Creates git commit with conventional message format
4. Creates git tag (e.g., `v0.1.1`)

#### Git Tags

All versions are tagged in git:
```bash
# List all version tags
git tag -l "v*"

# View specific version details
git show v0.1.0
```

### Distribution System

This repository serves as the **source** for `~/Github/thinker/claude-infrastructure-distribution`.

#### Version Tracking Architecture

**Two-Level Versioning**:
1. **Distribution Version** - Overall installer version (e.g., 1.0.0)
2. **Component Versions** - Individual component versions (e.g., rag:1.2.0, chronos:0.8.0)

**Component Release Notes**:
Each component in `apps/` tracks its own version and release notes:
- `apps/chronos/VERSION` - Component version
- `apps/chronos/RELEASE_NOTES.md` - Version-specific changes
- `apps/workdiary-mcp-server/VERSION` - Component version
- `apps/workdiary-mcp-server/RELEASE_NOTES.md` - Changes

#### Installer Behavior

The installer (`install_claude_infrastructure.py`) supports:

**Fresh Installation**:
- Installs all selected components
- Records installed versions in `~/.claude/.installed_versions.json`
- Shows component versions and changes during setup

**Upgrade Detection**:
- Compares installed versions with available versions
- Reports what's installed, what's missing, what can be upgraded
- Shows aggregated release notes for upgrades
- Allows selective component upgrades

**Version Hashing**:
- Components are hashed (SHA256) to detect manual modifications
- Integrity checks warn if installed components differ from expected

#### Creating Distribution Releases

When creating a new distribution from `claude_infra`:

1. **Update component versions** in `claude_infra`:
   ```bash
   # Update a component's version
   cd apps/chronos
   echo "0.9.0" > VERSION
   # Update RELEASE_NOTES.md with changes
   ```

2. **Bump claude_infra version**:
   ```bash
   ./bin/version-bump minor "Add Chronos 0.9.0 with improved queue fairness"
   ```

3. **Create distribution** (using upcoming `bin/create-distribution`):
   ```bash
   ./bin/create-distribution v0.2.0
   # This will:
   # - Copy components to distribution folder
   # - Aggregate all component versions
   # - Collect all release notes by version
   # - Generate distribution metadata
   # - Create distribution git tag
   ```

4. **Push tags**:
   ```bash
   git push && git push --tags
   ```

#### Distribution Metadata

When distribution is created, it generates:
- `DISTRIBUTION_VERSION` - Overall version
- `components/metadata.json` - Component versions and hashes
- `AGGREGATED_RELEASE_NOTES.md` - All component changes by version

**Query RAG for**: `"distribution versioning"`, `"component release notes"`, `"upgrade detection"`
