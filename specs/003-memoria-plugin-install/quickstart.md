# Quickstart: Memoria Plugin Installer & Auto-Update

**Feature**: 003-memoria-plugin-install
**Date**: 2026-02-11

## Development Setup

### Prerequisites

- Python 3.11+
- Docker Desktop (running)
- `gh` CLI installed and authenticated (`gh auth status`)
- Bash or Zsh shell
- Access to `IgorCandido/memoria` private repo

### Repository Structure

```
installer/
├── install.sh                  # Stage 1: curl bootstrap
├── memoria-install.sh          # Stage 2: full installer
├── lib/
│   ├── common.sh               # Logging, error handling, utilities
│   ├── version.sh              # Semver parsing & comparison
│   ├── download.sh             # GitHub release downloads & checksums
│   ├── python-check.sh         # Python 3.11+ verification
│   ├── docker-setup.sh         # ChromaDB container management
│   └── shell-detect.sh         # Shell detection & RC integration
├── templates/
│   └── shell-function.sh       # Shell function template for `memoria` command
└── tests/
    ├── unit/                   # Shell unit tests (bats or plain bash)
    │   ├── test-version.sh
    │   ├── test-common.sh
    │   └── test-download.sh
    └── integration/
        ├── test-install.sh     # Full install on clean environment
        ├── test-update.sh      # Update from old to new version
        └── test-uninstall.sh   # Clean uninstall verification

.github/workflows/
└── release.yml                 # Tag-triggered release pipeline

scripts/
└── package-release.sh          # Creates release tarball + checksums

memoria/
└── skill_helpers.py            # Modified: version check on first call
```

### Running Tests

**Shell tests** (installer):
```bash
# Run all shell unit tests
bash installer/tests/unit/run-all-tests.sh

# Run specific test
bash installer/tests/unit/test-version.sh
```

**Python tests** (version check integration):
```bash
# Activate memoria venv
source .venv/bin/activate

# Run version check tests
pytest tests/unit/test_version_check.py -v

# Run full test suite
pytest tests/ -v
```

**Integration tests** (require Docker):
```bash
# Full install test (uses temp directory)
bash installer/tests/integration/test-install.sh

# Update scenario test
bash installer/tests/integration/test-update.sh
```

### Testing the Installer Locally

```bash
# Test Stage 1 (bootstrap) without curl:
bash installer/install.sh

# Test Stage 2 (full install) directly:
bash installer/memoria-install.sh install

# Test update:
memoria update

# Test health check:
memoria health

# Test uninstall:
bash installer/memoria-install.sh uninstall
```

### Creating a Test Release

```bash
# Package a release locally:
bash scripts/package-release.sh 0.1.0-dev

# Verify:
ls -la dist/
sha256sum -c dist/checksums.txt
```

### Key Development Notes

1. **Shell libraries are sourced, not executed**: `lib/*.sh` are sourced by the installer scripts. They define functions, not standalone scripts.

2. **Version cache is at `~/.local/share/memoria/.version-cache`**: Delete this file to force a fresh version check during testing.

3. **Config file is at `~/.local/share/memoria/config.json`**: Contains installation metadata. Delete to simulate fresh install.

4. **Docker container is named `memoria-chromadb`**: Use `docker ps -a | grep memoria-chromadb` to check status.

5. **Skill symlink**: `~/.claude/skills/memoria` must point to the repo directory containing `memoria/skill_helpers.py`.

6. **The `memoria` shell function**: Loaded from `~/.local/share/memoria/shell-init.sh`. Source it manually during development: `source installer/templates/shell-function.sh`.
