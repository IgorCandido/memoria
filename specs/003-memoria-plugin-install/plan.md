# Implementation Plan: Memoria Plugin Installer & Auto-Update

**Branch**: `003-memoria-plugin-install` | **Date**: 2026-02-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-memoria-plugin-install/spec.md`

## Summary

Build a curl-based one-line installer for memoria that downloads from the private GitHub repo using `gh` CLI, installs to `~/.local/share/memoria/`, creates a Python venv, starts ChromaDB Docker container, and registers the Claude Code skill. Includes smart auto-update checking (24-hour cached, notification-only) integrated into `skill_helpers.py`, a `memoria` shell command for manual updates/health checks, and a GitHub Actions release pipeline triggered by version tags.

Architecture follows the claudeSupervisor two-stage bootstrap pattern: Stage 1 is a curl-fetched script that validates prerequisites and downloads the full installer; Stage 2 is the main installer with modular shell libraries for version management, downloads, shell integration, and Docker setup.

## Technical Context

**Language/Version**: Bash 4+ (installer), Python 3.11+ (version check integration)
**Primary Dependencies**: `gh` CLI (GitHub auth + private repo access), Docker (ChromaDB), standard Unix tools (curl, tar, sha256sum)
**Storage**: JSON files for config and version cache (`~/.local/share/memoria/`)
**Testing**: Bash unit tests (shell libraries), pytest (Python version check), bash integration tests (install/update/uninstall scenarios)
**Target Platform**: macOS (primary), Linux (secondary)
**Project Type**: Single project — shell installer + Python skill modification
**Performance Goals**: Installation < 2 minutes (excluding Docker image pull), version check < 5 seconds (network timeout)
**Constraints**: No root/sudo required, no external dependencies beyond standard Unix + `gh`, offline operation unaffected by version check failures
**Scale/Scope**: Single-user local installation, ~17K chunks in ChromaDB, ~293 indexed documents

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Architecture | PASS | Installer is shell-based, outside onion layers. Python changes (version check) go in application layer (skill_helpers.py) |
| II. Immutability | PASS | No changes to domain entities |
| III. Adapter Pattern | PASS | No new ports or adapters. Version check is application-level orchestration |
| IV. Backward Compatibility | PASS | `search_knowledge()` signature unchanged. Notification appended to output string only |
| V. Performance | PASS | Version check adds 0ms (cached) or runs in background thread. No search latency impact |
| VI. Testing Strategy | PASS | Shell tests for installer, pytest for Python changes, integration tests for end-to-end |

**Post-Phase 1 re-check**: All gates still PASS. The installer is a new subsystem that doesn't touch domain or adapter layers. The only Python change is adding version-check logic to `skill_helpers.py` (application layer), which appends an informational line to output — no signature changes.

## Project Structure

### Documentation (this feature)

```text
specs/003-memoria-plugin-install/
├── plan.md              # This file
├── research.md          # Phase 0 output — architectural decisions
├── data-model.md        # Phase 1 output — entity definitions
├── quickstart.md        # Phase 1 output — dev setup guide
├── contracts/
│   ├── installer-cli.md # CLI interface contract
│   └── github-actions.md # Release pipeline contract
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
installer/
├── install.sh                  # Stage 1: curl bootstrap (~100 lines)
├── memoria-install.sh          # Stage 2: full installer (~600 lines)
├── lib/
│   ├── common.sh               # Logging, error handling, lock files, utilities
│   ├── version.sh              # Semver parsing, comparison, validation
│   ├── download.sh             # GitHub release downloads, checksums, caching
│   ├── python-check.sh         # Python 3.11+ detection and validation
│   ├── docker-setup.sh         # ChromaDB container lifecycle (start/stop/check)
│   └── shell-detect.sh         # Shell detection, RC file management
├── templates/
│   └── shell-function.sh       # Shell function template for `memoria` command
└── tests/
    ├── unit/
    │   ├── run-all-tests.sh    # Test runner
    │   ├── test-version.sh     # Semver parsing/comparison tests
    │   ├── test-common.sh      # Utility function tests
    │   └── test-download.sh    # Download/checksum tests
    └── integration/
        ├── test-install.sh     # End-to-end install
        ├── test-update.sh      # Update scenarios
        └── test-uninstall.sh   # Clean removal

.github/workflows/
└── release.yml                 # Tag-triggered release pipeline

scripts/
└── package-release.sh          # Creates tarball + checksums + manifest

# Python modifications (existing files):
memoria/skill_helpers.py        # Add version check on first call
tests/unit/test_version_check.py # New test file for version check logic
```

**Structure Decision**: The installer is a standalone shell subsystem at `installer/` in the repo root. It follows the claudeSupervisor pattern: modular shell libraries in `lib/`, templates in `templates/`, tests alongside. The GitHub Actions workflow goes in `.github/workflows/` at repo root. Python changes are minimal — only `skill_helpers.py` gets version check logic.

## Complexity Tracking

No constitution violations. The installer is a new subsystem that doesn't affect the existing onion architecture.
