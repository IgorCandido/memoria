# Research: Memoria Plugin Installer & Auto-Update

**Feature**: 003-memoria-plugin-install
**Date**: 2026-02-11

## R1: Installer Architecture — Two-Stage Bootstrap Pattern

**Decision**: Adopt claudeSupervisor's two-stage bootstrap pattern adapted for memoria's specific needs.

**Rationale**: The claudeSupervisor installer is proven, battle-tested, and solves the exact same problem (private GitHub repo → user-local install → skill registration). Reusing the architecture avoids reinventing security, cross-platform compatibility, and shell integration.

**How it works**:

- **Stage 1** (`install.sh`): Minimal script fetched via curl. Validates environment (Python 3.11+, Docker, `gh` auth), downloads the Stage 2 installer and shell libraries via `gh`, sets up `~/.local/bin/` and `~/.local/share/memoria/`.
- **Stage 2** (`memoria-install.sh`): Full installer with library support. Clones the repo (or downloads a release tarball), creates Python venv, installs dependencies, starts ChromaDB Docker container, registers the skill symlink, runs health check.

**Alternatives considered**:
- Single-stage script: Rejected — too much logic for a curl-piped script, hard to maintain and test
- Python-based installer (pip install): Rejected — requires pip, doesn't handle Docker/skill registration, private repo complicates PyPI-style distribution
- Homebrew formula: Rejected — doesn't exist for private repos, macOS-only

## R2: Installation Target Directory

**Decision**: Install to `~/.local/share/memoria/` with `gh` clone (not tarball for initial release).

**Rationale**: For the initial implementation, `gh repo clone` is simpler and provides git history for future updates. The tarball-based approach can be added when the GHA release pipeline is built. The `~/.local/share/` prefix follows XDG Base Directory conventions and is the standard user-local data location on both macOS and Linux.

**Layout**:
```
~/.local/share/memoria/
├── repo/                    # Git clone of memoria repo
│   ├── memoria/             # Python package
│   ├── pyproject.toml
│   ├── docs/                # Shared docs (symlinked or copied)
│   └── ...
├── .venv/                   # Python virtual environment
├── lib/                     # Installer shell libraries
├── config.json              # Installation metadata
├── .version-cache           # Version check cache (JSON)
└── backups/                 # Pre-update backups
```

**Alternatives considered**:
- `~/.memoria/`: Custom dotdir — less standard, clutters home directory
- `~/Github/thinker/memoria/`: Current location — assumes specific directory structure, not reproducible
- `/opt/memoria/`: System-wide — requires root

## R3: Version Check & Auto-Update Strategy

**Decision**: Time-based cache with 24-hour TTL, checked at skill import time via Python, not shell.

**Rationale**: The update check must happen within the memoria Python code path (not a shell hook) because:
1. Memoria is invoked as a Python skill, not a shell command
2. Python can do the HTTP call, file I/O, and JSON parsing more reliably than shell
3. The check integrates naturally into `skill_helpers.py` initialization

**Implementation approach**:
1. On first `search_knowledge()` call in a session, check `~/.local/share/memoria/.version-cache`
2. If cache is missing or older than 24 hours, spawn a background thread to query GitHub releases API via `gh api`
3. Cache the result as JSON: `{"latest_version": "0.5.0", "checked_at": "2026-02-11T12:00:00Z", "current_version": "0.4.0"}`
4. If a newer version is detected, append a notification line to the search output: `"ℹ️ Memoria v0.5.0 available. Run: memoria update"`
5. Notification shown at most once per cache interval (flag in cache file)

**Alternatives considered**:
- Shell hook (PreToolUse): Rejected — too complex, adds latency to every tool call, hooks are fragile
- Cron job: Rejected — overkill, requires system scheduler, user doesn't see the result
- Check on every call: Rejected — too expensive, memoria called dozens of times per session

## R4: Docker ChromaDB Management

**Decision**: Installer starts ChromaDB via `docker run` with named container and persistent volume. Does not use docker-compose.

**Rationale**: The installer should be self-contained. Requiring docker-compose adds a dependency. A named container (`memoria-chromadb`) is simpler, can be checked/started/stopped individually, and doesn't require a compose file in the install directory.

**Container config**:
```bash
docker run -d \
  --name memoria-chromadb \
  --restart unless-stopped \
  -p 8001:8000 \
  -v ~/.local/share/memoria/chroma_data:/data \
  -e CHROMA_SERVER_HOST=0.0.0.0 \
  -e CHROMA_SERVER_HTTP_PORT=8000 \
  -e IS_PERSISTENT=TRUE \
  chromadb/chroma:latest
```

**Data persistence**: Volume at `~/.local/share/memoria/chroma_data/` so data survives container restarts and updates. The healthcheck uses `bash -c 'echo > /dev/tcp/localhost/8000'` (no curl in container image).

**Alternatives considered**:
- docker-compose: Rejected — adds dependency, overkill for single container
- Podman: Rejected — less common, Docker is the standard
- Embedded ChromaDB (persistent mode): Rejected — requires SQLite in Python process, less reliable for concurrent access

## R5: Python Virtual Environment Strategy

**Decision**: Dedicated venv at `~/.local/share/memoria/.venv/`, created during installation.

**Rationale**: A dedicated venv isolates memoria's dependencies (sentence-transformers, chromadb, pypdf, etc.) from the system Python and other tools. Editable install (`pip install -e .`) allows updating the code without reinstalling packages.

**Setup steps**:
1. `python3 -m venv ~/.local/share/memoria/.venv`
2. `~/.local/share/memoria/.venv/bin/pip install -e ~/.local/share/memoria/repo/`
3. Verify: `~/.local/share/memoria/.venv/bin/python3 -c "from memoria.skill_helpers import search_knowledge; print('OK')"`

**Alternatives considered**:
- System-wide pip install: Rejected — pollutes system Python, conflicts with other packages
- Shared venv (claude_infra pattern): Rejected — creates dependency on claude_infra being installed
- uv: Considered for speed — could be adopted later, but requires uv to be installed

## R6: Skill Registration Mechanism

**Decision**: Create symlink `~/.claude/skills/memoria → ~/.local/share/memoria/repo/` during installation.

**Rationale**: Claude Code discovers skills by scanning `~/.claude/skills/` for directories containing Python modules. The symlink approach means the skill points to the live code, so updates to the repo automatically update the skill. No file copying needed.

**Verification**: After symlink creation, verify `~/.claude/skills/memoria/memoria/skill_helpers.py` exists and is importable.

**Alternatives considered**:
- Copy files to `~/.claude/skills/`: Rejected — requires re-copying on every update
- Register via Claude Code API: No such API exists
- Hardcoded path in CLAUDE.md: Rejected — fragile, requires manual editing

## R7: Update Mechanism — Download & Replace

**Decision**: Update downloads the new version to a temp directory, verifies it, then atomically replaces the old installation.

**Rationale**: Atomic replacement prevents partial updates that leave the system broken. The backup is kept for rollback.

**Update flow**:
1. `memoria update` (or `memoria update --version X.Y.Z`)
2. Check GitHub releases API for target version
3. Download release tarball + checksums to temp directory
4. Verify checksums
5. Back up current installation: `~/.local/share/memoria/backups/v{current}-{timestamp}/`
6. Extract new version to `~/.local/share/memoria/repo/`
7. Re-run `pip install -e .` in the existing venv to update dependencies
8. Run health check
9. On failure: restore backup, report error

**Alternatives considered**:
- `git pull`: Simpler but doesn't work for tarball-based releases, leaves .git history growing
- pip upgrade: Doesn't handle non-Python files (shell scripts, configs)
- Full reinstall: Wasteful — venv and Docker data don't need recreation

## R8: GitHub Actions Release Pipeline

**Decision**: Follow claudeSupervisor pattern — tag push triggers GHA, which runs tests, packages tarball, computes checksums, creates GitHub release.

**Rationale**: Proven pattern that ensures release artifacts are always consistent and verified.

**Workflow**:
1. Tag: `git tag v0.5.0 && git push origin v0.5.0`
2. GHA triggers on `v*` tag push
3. Job: checkout → run tests → package release → compute checksums → create release
4. Artifacts: `memoria-{version}.tar.gz`, `checksums.txt`, `release-manifest.json`

**Package script**: Creates tarball containing:
- `memoria/` (Python package)
- `pyproject.toml`, `requirements.txt`
- `installer/` (shell scripts for self-update)
- `VERSION`, `README.md`
- Excludes: `.git/`, `chroma_data/`, `docs/`, `tests/`, `.venv/`, `__pycache__/`

## R9: Shell Integration & Commands

**Decision**: Add `memoria` shell function via `~/.local/share/memoria/shell-init.sh`, sourced from user's shell RC file.

**Rationale**: A shell function provides the `memoria` command (update, check, uninstall, health) without requiring PATH manipulation. The function dispatches to the Stage 2 installer script or Python commands.

**Commands**:
- `memoria update [--version X.Y.Z]`: Download and install update
- `memoria check`: Force version check
- `memoria health`: Run health check
- `memoria uninstall`: Remove installation
- `memoria version`: Show current version

**Shell integration**: Adds one line to `.zshrc`/`.bashrc`:
```bash
[ -f ~/.local/share/memoria/shell-init.sh ] && source ~/.local/share/memoria/shell-init.sh
```

## R10: Constitution Compliance for Installer

**Decision**: The installer is a new shell-based subsystem that sits outside the existing onion architecture. Constitution principles apply to the Python code changes (version check in skill_helpers.py) but not to the shell installer scripts themselves.

**Constitution impacts**:
- **Clean Architecture**: Version check logic goes in application layer (skill_helpers.py), not domain or adapters
- **Backward Compatibility**: `search_knowledge()` signature unchanged — version notification appended to output string
- **Immutability**: No changes to domain entities
- **Port-Adapter Pattern**: No new ports needed — version check is application-level orchestration
- **Testing**: Installer tests are shell script tests (bash unit tests), Python tests use existing pytest setup
