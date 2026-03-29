# Data Model: Memoria Plugin Installer & Auto-Update

**Feature**: 003-memoria-plugin-install
**Date**: 2026-02-11

## Entities

### InstalledVersion

Tracks the currently installed memoria version and installation metadata.

**Storage**: `~/.local/share/memoria/config.json`

| Field | Type | Description |
|-------|------|-------------|
| version | string | Semantic version (e.g., "0.5.0") |
| install_date | ISO 8601 datetime | When this version was installed |
| install_path | string | Absolute path to installation root |
| repo_path | string | Absolute path to cloned repo |
| venv_path | string | Absolute path to Python venv |
| installer_version | string | Version of the installer used |
| python_version | string | Python version used (e.g., "3.13.7") |
| install_method | enum | "clone" or "tarball" |
| git_commit | string | Git commit SHA (if clone-based) |

### VersionCache

Cached result of the latest available version check. Prevents redundant GitHub API calls.

**Storage**: `~/.local/share/memoria/.version-cache`

| Field | Type | Description |
|-------|------|-------------|
| latest_version | string | Latest available version on GitHub |
| current_version | string | Installed version at check time |
| checked_at | ISO 8601 datetime | Timestamp of last check |
| cache_ttl_hours | integer | Hours until cache expires (default: 24) |
| update_available | boolean | Whether latest > current |
| notification_shown | boolean | Whether user has been notified this cycle |
| check_error | string (nullable) | Error message if check failed |

### ReleaseManifest

Metadata about a published release. Included in every GitHub release as `release-manifest.json`.

**Storage**: Published as GitHub release asset; downloaded during install/update.

| Field | Type | Description |
|-------|------|-------------|
| version | string | Release version |
| build_date | ISO 8601 datetime | When release was built |
| git_commit | string | Git commit SHA |
| git_tag | string | Git tag name (e.g., "v0.5.0") |
| file_count | integer | Number of files in release |
| tarball_name | string | Name of release tarball |
| tarball_sha256 | string | SHA256 checksum of tarball |
| python_min_version | string | Minimum Python version required |
| dependencies_changed | boolean | Whether pip deps changed from previous release |

### BackupRecord

Metadata about a pre-update backup.

**Storage**: `~/.local/share/memoria/backups/{version}-{timestamp}/manifest.json`

| Field | Type | Description |
|-------|------|-------------|
| version | string | Version that was backed up |
| backup_date | ISO 8601 datetime | When backup was created |
| backup_path | string | Absolute path to backup directory |
| reason | string | Why backup was created (e.g., "pre-update") |
| files_count | integer | Number of files in backup |

## Relationships

```
InstalledVersion -- tracks --> VersionCache (1:1, current vs latest)
InstalledVersion -- produces --> BackupRecord (1:N, on each update)
ReleaseManifest -- downloaded during --> install/update operations
VersionCache -- queries --> GitHub Releases API (external)
```

## State Transitions

### Installation Lifecycle

```
NOT_INSTALLED → INSTALLING → INSTALLED → UPDATING → INSTALLED
                    ↓                        ↓
                FAILED_INSTALL          ROLLED_BACK → INSTALLED (previous version)
                                            ↓
                                      FAILED_ROLLBACK → MANUAL_INTERVENTION
```

### Version Check Lifecycle

```
CACHE_EMPTY → CHECKING → CACHE_FRESH (update_available: true/false)
                  ↓              ↓ (after TTL expiry)
             CHECK_FAILED    CACHE_STALE → CHECKING
```

## Validation Rules

- `version`: Must be valid semver (X.Y.Z, optional -prerelease suffix)
- `install_path`: Must be absolute path, must exist after installation
- `cache_ttl_hours`: Must be >= 1, default 24
- `checked_at`: Must be valid ISO 8601, must not be in the future
- `tarball_sha256`: Must be 64 hex characters
- `python_min_version`: Must be >= "3.11"
