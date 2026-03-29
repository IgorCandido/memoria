# Contract: Installer CLI Interface

**Feature**: 003-memoria-plugin-install
**Date**: 2026-02-11

## Stage 1: Bootstrap Script (`install.sh`)

Entry point via curl. No arguments — fully automatic.

```
curl -fsSL <raw-url> | bash
```

**Behavior**:
1. Validate prerequisites (Python 3.11+, Docker, `gh` authenticated)
2. Download Stage 2 installer and libraries via `gh`
3. Set up `~/.local/share/memoria/lib/`
4. Download and run Stage 2

**Exit codes**:
- 0: Success
- 1: Missing prerequisite (message printed to stderr)
- 2: Download failure
- 3: `gh` authentication failure

---

## Stage 2: Main Installer (`memoria-install.sh`)

### `memoria-install.sh install`

Full installation of memoria.

```bash
memoria-install.sh install [--version VERSION]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--version` | latest | Specific version to install (e.g., "0.5.0") |

**Steps**:
1. Clone repo (or download release tarball)
2. Create Python venv and install dependencies
3. Start ChromaDB Docker container
4. Register skill symlink at `~/.claude/skills/memoria`
5. Run health check
6. Write `config.json` with installation metadata

**Exit codes**:
- 0: Success
- 1: Clone/download failure
- 2: Python venv creation failure
- 3: Docker failure (warning only if Docker not running)
- 4: Skill registration failure
- 5: Health check failure

### `memoria-install.sh uninstall [--yes]`

Remove memoria installation.

```bash
memoria-install.sh uninstall [--yes]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--yes` | false | Skip confirmation prompts |

**Steps**:
1. Prompt for confirmation (unless --yes)
2. Prompt about ChromaDB container and data
3. Remove skill symlink
4. Remove Python venv
5. Remove repo clone
6. Remove shell integration lines
7. Remove `~/.local/share/memoria/`

---

## Shell Commands (`memoria` function)

Available after installation via shell function loaded from `shell-init.sh`.

### `memoria update [--version VERSION]`

Download and install an update.

```bash
memoria update              # Update to latest
memoria update --version 0.4.0  # Install specific version
```

**Behavior**: Download → verify checksum → backup current → replace → update pip deps → health check → report

**On failure**: Automatic rollback to backup, error reported.

### `memoria check`

Force a version check (ignores cache TTL).

```bash
memoria check
```

**Output**: Current version, latest version, whether update available.

### `memoria health`

Run system health check.

```bash
memoria health
```

**Output**: ChromaDB status, Python venv status, skill registration status, indexed document count.

### `memoria version`

Show installed version.

```bash
memoria version
```

**Output**: `memoria v0.5.0 (commit abc1234, installed 2026-02-11)`

---

## Python API: Version Check Integration

### `search_knowledge()` — Modified behavior

The existing `search_knowledge()` function gains version-check awareness without changing its signature.

```python
# Signature unchanged (FR backward-compat)
def search_knowledge(query, mode="hybrid", expand=True, limit=5):
    ...
```

**New behavior**: On first invocation in a session, checks version cache. If update available and not yet notified this cycle, appends notification to output string:

```
ℹ️ Memoria v0.5.0 available. Run: memoria update
```

This line appears after the search results. It does not affect the search results themselves.

### Version check internal API

```python
# New internal functions (not public API)
def _check_version_cache() -> dict | None:
    """Read version cache file, return None if stale or missing."""

def _update_version_cache() -> dict:
    """Query GitHub releases API via subprocess, update cache file."""

def _should_notify_update() -> bool:
    """Check if user should be notified about available update."""
```

These are private implementation details in `skill_helpers.py`, not exposed as public API.
