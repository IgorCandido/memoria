# Contract: GitHub Actions Release Pipeline

**Feature**: 003-memoria-plugin-install
**Date**: 2026-02-11

## Workflow: `release.yml`

**Trigger**: Push to tags matching `v*`

```yaml
on:
  push:
    tags:
      - 'v*'
```

## Jobs

### Job 1: `test`

Run test suite before release.

- **Runner**: ubuntu-latest
- **Steps**:
  1. Checkout code
  2. Set up Python 3.11
  3. Install dependencies (`pip install -e .[dev]`)
  4. Run tests (`pytest tests/`)
  5. Report results

**Failure behavior**: If tests fail, subsequent jobs are skipped. No release is created.

### Job 2: `package`

Create release artifacts.

- **Runner**: ubuntu-latest
- **Depends on**: `test` (success)
- **Steps**:
  1. Extract version from git tag (strip `v` prefix)
  2. Run `scripts/package-release.sh $VERSION`
  3. Upload artifacts: tarball, checksums, manifest

**Package script creates**:
```
dist/
├── memoria-{version}.tar.gz      # Release tarball
├── checksums.txt                  # SHA256 checksums for all files
└── release-manifest.json          # Release metadata
```

**Tarball contents** (included):
- `memoria/` (Python package directory)
- `pyproject.toml`
- `requirements.txt`
- `VERSION`
- `README.md`
- `installer/` (shell scripts)

**Tarball excludes**:
- `.git/`, `.github/`
- `chroma_data/`, `docs/`
- `tests/`, `specs/`
- `.venv/`, `__pycache__/`
- `.specify/`, `contexts/`

### Job 3: `release`

Create GitHub release with artifacts.

- **Runner**: ubuntu-latest
- **Depends on**: `package` (success)
- **Steps**:
  1. Download artifacts from `package` job
  2. Create GitHub Release via `softprops/action-gh-release@v2`
  3. Attach: tarball, checksums.txt, release-manifest.json
  4. Set release name: "Memoria v{version}"
  5. Set pre-release flag if version contains `-` (e.g., `v0.5.0-alpha`)
  6. Auto-generate release notes from commits since last tag

### Job 4: `validate` (optional)

Post-release validation on multiple platforms.

- **Runner**: matrix [ubuntu-latest, macos-latest]
- **Depends on**: `release` (success)
- **Steps**:
  1. Download release tarball from GitHub release
  2. Verify checksums match
  3. Extract and verify file count matches manifest
  4. Verify Python package is importable

## Release Manifest Schema

```json
{
  "version": "0.5.0",
  "build_date": "2026-02-11T12:00:00Z",
  "git_commit": "abc1234def5678",
  "git_tag": "v0.5.0",
  "file_count": 42,
  "tarball_name": "memoria-0.5.0.tar.gz",
  "tarball_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "python_min_version": "3.11",
  "dependencies_changed": false
}
```

## Checksums File Format

```
e3b0c44298fc1c14...  memoria-0.5.0.tar.gz
a1b2c3d4e5f67890...  release-manifest.json
```

Standard `sha256sum` format — one line per file, hash followed by two spaces and filename.
