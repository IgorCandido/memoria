# Memoria Installer

Shell-based installer for the Memoria RAG system. Downloads from the private GitHub repo using `gh` CLI, sets up Python venv, starts ChromaDB, and registers the Claude Code skill.

## Architecture

Two-stage bootstrap pattern:

- **Stage 1** (`install.sh`): Lightweight bootstrap fetched via curl. Validates prerequisites, downloads Stage 2.
- **Stage 2** (`memoria-install.sh`): Full installer with modular shell libraries. Handles install/update/uninstall.

### Shell Libraries (`lib/`)

| Library | Purpose |
|---------|---------|
| `common.sh` | Logging, error handling, OS detection, lock files, path validation |
| `version.sh` | Semver parsing, comparison, normalization |
| `python-check.sh` | Python 3.11+ detection and validation |
| `shell-detect.sh` | Shell detection, RC file management, source line safety |
| `download.sh` | GitHub release downloads, SHA256 checksums, version cache |
| `docker-setup.sh` | ChromaDB container lifecycle (start/stop/health) |

## Testing

```bash
# Shell unit tests
bash installer/tests/unit/run-all-tests.sh

# Individual test
bash installer/tests/unit/test-version.sh

# Integration tests (require gh CLI + git)
bash installer/tests/integration/test-install.sh
bash installer/tests/integration/test-update.sh
bash installer/tests/integration/test-uninstall.sh
```

## Cutting a Release

```bash
# Package locally
bash scripts/package-release.sh 0.5.0

# Or push a tag to trigger GHA
git tag v0.5.0
git push origin v0.5.0
```

## Security

- Path traversal prevention in `common.sh` and `shell-detect.sh`
- SHA256 checksum verification for all downloads
- Atomic `mkdir`-based lock file to prevent concurrent operations
- Shell RC injection protection (blocks `;`, `|`, backticks, `$()`, `&&`, `||`)
- No root/sudo required
