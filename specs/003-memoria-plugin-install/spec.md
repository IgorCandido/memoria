# Feature Specification: Memoria Plugin Installer & Auto-Update

**Feature Branch**: `003-memoria-plugin-install`
**Created**: 2026-02-11
**Status**: Draft
**Input**: Curl-based installer for memoria from private GitHub repo using gh CLI. Installs into user folder. Auto-update checks with smart frequency throttling. Release cutting via GitHub Actions.

## Background

Memoria currently requires manual setup: cloning the repo, creating symlinks, installing Python dependencies, configuring Docker, and registering the skill. This multi-step process is error-prone and not reproducible. The claudeSupervisor sister project has a proven curl-based installer pattern with two-stage bootstrap, modular shell libraries, version management, and GitHub Actions release pipeline.

Memoria needs the same treatment: a one-line install command that sets up everything, plus an auto-update mechanism that checks for new releases without being intrusive or taxing on every interaction.

### Update Frequency Challenge

Checking for updates on every memoria interaction (every RAG query) would be too expensive — memoria is called dozens of times per session. The update check needs smart throttling:

- **Time-based cache**: Check at most once per day (or configurable interval), cache the result
- **Session-based**: Check once at the start of a new Claude Code session, not on every tool call
- **Passive notification**: When an update is available, inform the user on next interaction but don't block or interrupt workflow
- **User-initiated**: Provide an explicit command to check for updates on demand

## Dependencies

- **GitHub CLI (`gh`)**: Required for downloading from private repo. Must be authenticated.
- **Python 3.11+**: Required for memoria itself
- **Docker**: Required for ChromaDB container
- **claudeSupervisor pattern**: Follows the same installer architecture (`~/Github/thinker/claude_supervisor/main/installer/`)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-Line Installation (Priority: P1)

As a new user, I want to install memoria with a single curl command, so that I can start using RAG search without manually cloning repos, creating symlinks, or configuring services.

**Why this priority**: Without installation, nothing else works. This is the entry point for all users.

**Independent Test**: On a clean machine with Python 3.11+ and Docker, run the curl install command, verify memoria is functional (search returns results after indexing a test document).

**Acceptance Scenarios**:

1. **Given** a machine with Python 3.11+, Docker, and `gh` authenticated, **When** the user runs the curl install command, **Then** memoria is installed to `~/.local/share/memoria/`, the skill is registered at `~/.claude/skills/memoria`, ChromaDB container is started, and `search_knowledge()` is functional
2. **Given** a successful install, **When** the user starts a new Claude Code session, **Then** the memoria skill is available and RAG queries work without additional setup
3. **Given** `gh` is not authenticated or not installed, **When** installation is attempted, **Then** a clear error is shown with instructions to install and authenticate `gh`
4. **Given** Python version is below 3.11, **When** installation is attempted, **Then** a clear error is shown with the minimum version requirement
5. **Given** memoria is already installed, **When** the install command is run again, **Then** the existing installation is detected and the user is prompted to reinstall or update

---

### User Story 2 - Smart Auto-Update Check (Priority: P1)

As a memoria user, I want the system to periodically check for new releases and notify me when an update is available, so that I stay current without being interrupted during my workflow.

**Why this priority**: Users on stale versions miss bug fixes and new features. Auto-update awareness is essential for a distributed tool, but must not degrade the user experience.

**Independent Test**: Install an older version, configure update check, trigger a session start, verify the user is notified of the newer version exactly once and the notification does not block any workflow.

**Acceptance Scenarios**:

1. **Given** a version check has not been performed in the last 24 hours, **When** memoria is invoked, **Then** a background check queries the GitHub releases API for the latest version and caches the result
2. **Given** a newer version exists and the cache indicates it, **When** the user's next interaction occurs, **Then** a non-blocking notification informs the user (e.g., "Memoria v0.5.0 available, run `memoria update` to upgrade") and does not repeat until the next cache expiry
3. **Given** a version check was performed within the last 24 hours, **When** memoria is invoked, **Then** no network call is made — the cached result is used
4. **Given** the network is unavailable during a version check, **When** the check fails, **Then** it silently falls back to the cached version (or no notification) without errors or delays
5. **Given** the user is on the latest version, **When** a version check runs, **Then** no notification is shown

---

### User Story 3 - User-Initiated Update (Priority: P2)

As a memoria user, I want to explicitly check for and apply updates when I choose, so that I control when my system changes.

**Why this priority**: Complements auto-check with user agency. Some users prefer manual control over updates.

**Independent Test**: Run the update command, verify it checks for the latest release, downloads it, replaces the current installation, and confirms the new version.

**Acceptance Scenarios**:

1. **Given** a newer version is available, **When** the user runs the update command, **Then** the new version is downloaded, installed, and verified — the old version is backed up
2. **Given** the user is already on the latest version, **When** the update command is run, **Then** a message confirms "already up to date"
3. **Given** an update fails mid-process, **When** the failure is detected, **Then** the system rolls back to the previous version and reports the error
4. **Given** a specific version is requested (e.g., `memoria update --version 0.4.0`), **When** the command runs, **Then** that exact version is installed (allows downgrades)

---

### User Story 4 - GitHub Actions Release Pipeline (Priority: P2)

As a memoria maintainer, I want releases to be cut automatically when a version tag is pushed, so that the distribution artifacts are always consistent and verified.

**Why this priority**: Manual release creation is error-prone. Automated releases ensure checksums, manifests, and tarballs are always correct.

**Independent Test**: Push a version tag (e.g., `v0.5.0`), verify the GitHub Action creates a release with tarball, checksums, and manifest.

**Acceptance Scenarios**:

1. **Given** a version tag is pushed (e.g., `git tag v0.5.0 && git push origin v0.5.0`), **When** the GitHub Action runs, **Then** a GitHub Release is created with: tarball, SHA256 checksums file, and release manifest JSON
2. **Given** a release is created, **When** the tarball is downloaded and extracted, **Then** its contents match the source repo at the tagged commit
3. **Given** a release is created, **When** checksums are verified, **Then** all file checksums match the checksums file in the release
4. **Given** tests fail during the release pipeline, **When** the Action detects failures, **Then** the release is not published and the pipeline reports the failure

---

### User Story 5 - Uninstall (Priority: P3)

As a memoria user, I want to cleanly uninstall memoria, so that no artifacts are left behind if I no longer need it.

**Why this priority**: Clean uninstall is good hygiene but not critical for core functionality.

**Independent Test**: Install memoria, run uninstall, verify all files, symlinks, and configurations are removed.

**Acceptance Scenarios**:

1. **Given** memoria is installed, **When** the uninstall command is run, **Then** all installed files are removed from `~/.local/share/memoria/`, the skill symlink is removed, and shell integrations are cleaned up
2. **Given** uninstall is run, **When** the ChromaDB container is running, **Then** the user is prompted about whether to stop/remove the container and its data
3. **Given** uninstall completes, **When** a Claude Code session starts, **Then** the memoria skill is no longer available

---

### Edge Cases

- What happens when the GitHub API rate limit is exceeded during version check? (Silently use cached version, log warning, retry on next interval)
- What happens when the user has local modifications to the installed memoria files? (Warn the user, offer to backup before overwriting)
- What happens when Docker is not running during install? (Install the Python components, warn that ChromaDB setup will be completed when Docker starts)
- What happens when multiple Claude instances trigger version checks simultaneously? (File-lock the cache to prevent race conditions)
- What happens when the private repo access is revoked after installation? (Memoria continues to work offline — update checks fail gracefully)
- What happens when the installed version's Python dependencies change in a new release? (Update command must also update pip dependencies)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a curl-based one-line install command that bootstraps memoria from the private GitHub repo using `gh` CLI
- **FR-002**: System MUST install memoria to a user-scoped directory (`~/.local/share/memoria/` or similar) without requiring root/sudo
- **FR-003**: System MUST register the memoria skill at `~/.claude/skills/memoria` via symlink during installation
- **FR-004**: System MUST validate prerequisites before installation: Python 3.11+, Docker, `gh` CLI authenticated with repo access
- **FR-005**: System MUST provide an auto-update check that queries GitHub releases API with a configurable time-based cache (default: 24 hours)
- **FR-006**: System MUST NOT perform network calls for version checking more than once per cache interval — all subsequent checks within the interval use the cached result
- **FR-007**: System MUST display update notifications passively (non-blocking) when a newer version is detected
- **FR-008**: System MUST provide an explicit update command that downloads and installs a newer version with rollback on failure
- **FR-009**: System MUST provide an uninstall command that removes all installed files, symlinks, and configurations
- **FR-010**: System MUST include a GitHub Actions workflow that creates releases with tarball, checksums, and manifest when a version tag is pushed
- **FR-011**: System MUST verify release integrity via SHA256 checksums during installation and updates
- **FR-012**: System MUST handle network failures gracefully — offline operation continues normally, version checks silently fail
- **FR-013**: System MUST support version pinning — users can install or update to a specific version
- **FR-014**: System MUST set up the Python virtual environment and install pip dependencies as part of installation

### Non-Functional Requirements

- **NFR-001**: Installation MUST complete in under 2 minutes on a standard internet connection (excluding Docker image pull)
- **NFR-002**: Version check network calls MUST timeout within 5 seconds to avoid blocking user workflows
- **NFR-003**: The installer MUST be a self-contained shell script with no external dependencies beyond standard Unix tools + `gh`
- **NFR-004**: All installer operations MUST be idempotent — running install twice produces the same result

### Key Entities

- **InstalledVersion**: Record of the currently installed memoria version — version string, install timestamp, install path, Python venv path.
- **VersionCache**: Cached result of the latest available version — version string, check timestamp, cache expiry. Stored as a lightweight file (e.g., `~/.local/share/memoria/.version-cache`).
- **ReleaseManifest**: Metadata about a release — version, build date, git commit, file count, checksums, requirements.
- **UpdateResult**: Summary of an update operation — previous version, new version, files changed, rollback status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can install memoria with a single curl command and have working RAG search within 2 minutes (excluding Docker image pull)
- **SC-002**: Auto-update checks occur at most once per 24-hour period — no redundant network calls during a session
- **SC-003**: Update notification is displayed at most once per detected new version and does not block or delay any user operation
- **SC-004**: GitHub Actions release pipeline produces valid artifacts (tarball, checksums, manifest) on every tag push
- **SC-005**: Failed updates roll back to the previous version with zero data loss
- **SC-006**: Offline operation works normally — version checks silently fail without errors or degraded functionality
- **SC-007**: Uninstall removes all memoria artifacts with no leftover files or broken symlinks

## Assumptions

- The GitHub repo `IgorCandido/memoria` remains private — `gh` CLI with authentication is the required access method
- The claudeSupervisor installer pattern (two-stage bootstrap, modular shell libraries) is the reference architecture
- The version cache will be a simple JSON file at `~/.local/share/memoria/.version-cache` with TTL-based expiry
- The update check hook will be implemented as part of the memoria skill's initialization path (checked once when the skill module is first imported in a session)
- ChromaDB Docker container setup is part of the install but uses the existing `docker-compose.yml` pattern from `claude_infra`
- The release pipeline will follow the same pattern as claudeSupervisor: tag push triggers GHA, which runs tests and creates the release
- Shell integration (bash/zsh) will add memoria commands to PATH via `~/.local/bin/` and shell RC file modifications
