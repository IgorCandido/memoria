# Tasks: Memoria Plugin Installer & Auto-Update

**Input**: Design documents from `/specs/003-memoria-plugin-install/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Shell unit tests included for installer libraries (critical for security and correctness). Python tests included for version check integration.

**Organization**: Tasks grouped by user story. US1 (install) and US2 (auto-update) are P1. US3 (manual update), US4 (GHA release) are P2. US5 (uninstall) is P3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create installer directory structure, shell library foundation, and shared utilities

- [ ] T001 Create installer directory structure: `installer/`, `installer/lib/`, `installer/templates/`, `installer/tests/unit/`, `installer/tests/integration/`
- [ ] T002 [P] Create `installer/lib/common.sh` — logging functions (log_info, log_warning, log_error, log_step), die(), color codes, OS/arch detection, disk space check, required command verification
- [ ] T003 [P] Create `installer/lib/version.sh` — parse_semver(), validate_semver(), compare_versions(), is_newer(), is_older(), normalize_version(), read_version_file()
- [ ] T004 [P] Create `installer/lib/python-check.sh` — find_python(), get_python_version(), check_python_version() (validates 3.11+), get_python_install_instructions() (macOS/Linux aware)
- [ ] T005 [P] Create `installer/lib/shell-detect.sh` — detect_shell() (bash/zsh), get_shell_config_file(), add_source_line(), remove_source_line(), validate_source_line() (block dangerous metacharacters)
- [ ] T006 [P] Create `installer/lib/download.sh` — network connectivity check (5s timeout), get_latest_version() (via `gh api`), download_file() (retry logic, 3 attempts, exponential backoff), compute_sha256() (cross-platform: sha256sum/shasum/openssl), verify_checksum(), version cache read/write (1-hour TTL in `${TMPDIR}`)
- [ ] T007 [P] Create `installer/lib/docker-setup.sh` — check_docker_running(), check_container_exists(), start_chromadb_container() (named `memoria-chromadb`, port 8001:8000, volume at install path), stop_chromadb_container(), wait_for_chromadb_healthy() (TCP probe, 30s timeout)
- [ ] T008 Create `installer/tests/unit/run-all-tests.sh` — test runner that sources each test file and reports pass/fail

**Checkpoint**: All shell libraries exist and are individually sourceable without errors

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shell unit tests for all libraries — validates correctness before any installer script uses them

**⚠️ CRITICAL**: No installer scripts can be built until libraries are tested

- [ ] T009 [P] Create `installer/tests/unit/test-version.sh` — test parse_semver (valid/invalid inputs), compare_versions (equal, newer, older, pre-release), normalize_version (partial versions, v-prefix)
- [ ] T010 [P] Create `installer/tests/unit/test-common.sh` — test logging output, die() exit behavior, OS detection, command verification
- [ ] T011 [P] Create `installer/tests/unit/test-download.sh` — test compute_sha256 (known hash), verify_checksum (match/mismatch), version cache TTL logic (fresh/stale)
- [ ] T012 [P] Create `installer/tests/unit/test-shell-detect.sh` — test detect_shell(), validate_source_line() (block semicolons, pipes, backticks, $()), add/remove_source_line idempotency

**Checkpoint**: All shell library tests pass. Foundation ready — installer scripts can now be built.

---

## Phase 3: User Story 1 — One-Line Installation (Priority: P1) 🎯 MVP

**Goal**: A single curl command installs memoria: clones repo, creates venv, starts ChromaDB, registers skill, verifies health.

**Independent Test**: On a machine with Python 3.11+, Docker, and `gh` authenticated, run `bash installer/install.sh`, verify `~/.claude/skills/memoria` exists, `search_knowledge()` returns results.

### Implementation for User Story 1

- [ ] T013 [US1] Create `installer/install.sh` — Stage 1 bootstrap: validate prerequisites (Python 3.11+ via python-check.sh, Docker via docker-setup.sh, `gh auth status`), download Stage 2 and libs via `gh` to `~/.local/share/memoria/`, run Stage 2. Exit codes per contract (0-3).
- [ ] T014 [US1] Create `installer/memoria-install.sh` install command — Stage 2: clone repo via `gh repo clone` to `~/.local/share/memoria/repo/`, create venv (`python3 -m venv`), `pip install -e .`, start ChromaDB container via docker-setup.sh, create skill symlink `~/.claude/skills/memoria → ~/.local/share/memoria/repo/`, run health check, write `~/.local/share/memoria/config.json` (InstalledVersion entity from data-model.md). Exit codes per contract (0-5).
- [ ] T015 [US1] Create `installer/templates/shell-function.sh` — shell function template for `memoria` command dispatching to update/check/health/version/uninstall subcommands. Sources `~/.local/share/memoria/lib/common.sh` for utilities.
- [ ] T016 [US1] Add shell integration to Stage 2 installer — after successful install, detect shell via shell-detect.sh, create `~/.local/share/memoria/shell-init.sh`, add source line to user's shell RC file (.zshrc/.bashrc)
- [ ] T017 [US1] Handle re-install scenario in `installer/memoria-install.sh` — detect existing `~/.local/share/memoria/config.json`, prompt user to reinstall or update, back up existing installation before overwrite
- [ ] T018 [US1] Create `installer/tests/integration/test-install.sh` — end-to-end install test using temp directory override (MEMORIA_INSTALL_DIR env var), verify: directory structure exists, venv works, skill symlink valid, config.json written with correct schema

**Checkpoint**: `bash installer/install.sh` completes successfully, `memoria version` works, `search_knowledge("test")` returns results from Claude Code.

---

## Phase 4: User Story 2 — Smart Auto-Update Check (Priority: P1)

**Goal**: Version cache checked on first `search_knowledge()` call per session. Non-blocking notification when update available. No redundant network calls.

**Independent Test**: Install an older version, set version cache to empty, call `search_knowledge()`, verify notification appears once and subsequent calls don't re-check.

### Implementation for User Story 2

- [ ] T019 [US2] Add version check functions to `memoria/skill_helpers.py` — implement `_check_version_cache()` (reads `~/.local/share/memoria/.version-cache`, returns None if stale/missing), `_update_version_cache()` (runs `gh api repos/IgorCandido/memoria/releases/latest` via subprocess with 5s timeout, writes VersionCache JSON), `_should_notify_update()` (compares versions, checks notification_shown flag)
- [ ] T020 [US2] Integrate version check into `search_knowledge()` in `memoria/skill_helpers.py` — on first call (module-level `_version_checked` flag), spawn background thread for `_update_version_cache()` if cache stale. After search results, if update available and not yet notified, append notification line to output. Set notification_shown=True in cache.
- [ ] T021 [US2] Handle version check failures gracefully in `memoria/skill_helpers.py` — network timeout (5s), `gh` not available, API rate limit, malformed JSON response. All failures silently caught, cached result used, no user-visible errors.
- [ ] T022 [US2] Create `tests/unit/test_version_check.py` — test _check_version_cache with fresh/stale/missing cache files, test _should_notify_update with various version combinations, test graceful failure on missing gh CLI, test notification_shown flag prevents repeat notifications. Use tmp_path fixture for cache files.

**Checkpoint**: `search_knowledge()` shows update notification when newer version exists, does NOT show it on subsequent calls, does NOT make network calls within 24h of last check.

---

## Phase 5: User Story 3 — User-Initiated Update (Priority: P2)

**Goal**: `memoria update` downloads new version, verifies checksum, backs up current, replaces, updates pip deps, runs health check. Rollback on failure.

**Independent Test**: Install version 0.1.0, run `memoria update`, verify new version installed, old version backed up, health check passes.

### Implementation for User Story 3

- [ ] T023 [US3] Add update command to `installer/memoria-install.sh` — parse `--version` flag (default: latest), download release tarball via download.sh, verify SHA256 checksum against checksums.txt, create backup of current repo dir to `~/.local/share/memoria/backups/v{current}-{timestamp}/`, extract new version, run `pip install -e .` to update dependencies, run health check.
- [ ] T024 [US3] Implement rollback logic in `installer/memoria-install.sh` — if health check fails after update: restore backup directory to repo path, re-run `pip install -e .`, report error with instructions. Write BackupRecord manifest.json in backup directory.
- [ ] T025 [US3] Add `memoria check` subcommand to `installer/templates/shell-function.sh` — force version check ignoring cache TTL, display current version, latest version, update available status.
- [ ] T026 [US3] Create `installer/tests/integration/test-update.sh` — test update from old to new version, verify backup created, verify new version active, test rollback on simulated failure (corrupt tarball), test `--version` flag for specific version install.

**Checkpoint**: `memoria update` successfully updates to latest, `memoria update --version X.Y.Z` installs specific version, failed updates roll back cleanly.

---

## Phase 6: User Story 4 — GitHub Actions Release Pipeline (Priority: P2)

**Goal**: Tag push triggers GHA workflow that runs tests, packages tarball with checksums and manifest, creates GitHub Release.

**Independent Test**: Push tag `v0.1.0-test`, verify GHA creates release with tarball, checksums.txt, and release-manifest.json. Download and verify checksums match.

### Implementation for User Story 4

- [ ] T027 [P] [US4] Create `scripts/package-release.sh` — accepts version arg, creates `dist/` directory, copies included files (memoria/, pyproject.toml, requirements.txt, VERSION, README.md, installer/), excludes (.git, chroma_data, docs, tests, specs, .venv, __pycache__, .specify, contexts), creates tarball `memoria-{version}.tar.gz`, computes SHA256 for all files → `checksums.txt`, generates `release-manifest.json` (ReleaseManifest entity from data-model.md)
- [ ] T028 [US4] Create `.github/workflows/release.yml` — trigger on `v*` tag push. Job 1 (test): checkout, setup Python 3.11, install deps, run pytest. Job 2 (package): depends on test, extract version from tag, run package-release.sh, upload artifacts. Job 3 (release): depends on package, create GitHub Release via softprops/action-gh-release@v2, attach tarball + checksums + manifest, set pre-release flag if version contains `-`.
- [ ] T029 [US4] Add optional Job 4 (validate) to `.github/workflows/release.yml` — matrix [ubuntu-latest, macos-latest], depends on release, download tarball from release, verify checksums, extract and check file count against manifest, verify Python package importable.

**Checkpoint**: `git tag v0.1.0 && git push origin v0.1.0` triggers GHA, creates release with valid tarball and matching checksums.

---

## Phase 7: User Story 5 — Uninstall (Priority: P3)

**Goal**: `memoria uninstall` cleanly removes all artifacts — repo, venv, skill symlink, shell integration, Docker container (with user prompt).

**Independent Test**: Install memoria, run uninstall, verify no files remain at `~/.local/share/memoria/`, no symlink at `~/.claude/skills/memoria`, no source lines in shell RC files.

### Implementation for User Story 5

- [ ] T030 [US5] Add uninstall command to `installer/memoria-install.sh` — parse `--yes` flag, prompt for confirmation, prompt about ChromaDB container/data (stop container? remove volume?), remove skill symlink, remove venv, remove repo directory, remove shell integration via shell-detect.sh remove_source_line(), remove `~/.local/share/memoria/` directory.
- [ ] T031 [US5] Add `memoria uninstall` subcommand to `installer/templates/shell-function.sh` — delegates to `memoria-install.sh uninstall`, passes through `--yes` flag.
- [ ] T032 [US5] Create `installer/tests/integration/test-uninstall.sh` — install then uninstall, verify: no `~/.local/share/memoria/`, no `~/.claude/skills/memoria` symlink, no source lines in shell RC files, Docker container stopped (if requested).

**Checkpoint**: `memoria uninstall` removes all artifacts cleanly. Fresh Claude Code session shows no memoria skill.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, security hardening, and final validation

- [ ] T033 [P] Add `installer/README.md` — developer documentation for installer: architecture overview, how to test locally, how to cut a release
- [ ] T034 [P] Add path traversal prevention to `installer/memoria-install.sh` — reject `..` in paths, block sensitive system directories (/etc, /System, /root), validate all user-provided paths
- [ ] T035 [P] Add lock file mechanism to `installer/memoria-install.sh` using common.sh — prevent concurrent installations via atomic mkdir-based locking with 10-minute stale lock cleanup
- [ ] T036 Validate idempotency — run install twice, verify second run detects existing installation and offers reinstall/update. Run uninstall twice, verify second run reports "not installed".
- [ ] T037 Run quickstart.md validation — execute all commands from quickstart.md in order, verify each step succeeds

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 Install (Phase 3)**: Depends on Phase 2 — core installer
- **US2 Auto-Update (Phase 4)**: Depends on Phase 2 only (Python-only, independent of US1 shell scripts). But practically uses config.json written by US1.
- **US3 Manual Update (Phase 5)**: Depends on US1 (needs working install to update from) and US4 (needs release artifacts to download)
- **US4 GHA Pipeline (Phase 6)**: Depends on Phase 2 only (independent CI/CD)
- **US5 Uninstall (Phase 7)**: Depends on US1 (needs working install to uninstall)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational)
                      ├── Phase 3 (US1: Install) ──────┬── Phase 5 (US3: Manual Update)
                      │                                 └── Phase 7 (US5: Uninstall)
                      ├── Phase 4 (US2: Auto-Update) ──┘
                      └── Phase 6 (US4: GHA Pipeline) ─┘
                                                        └── Phase 8 (Polish)
```

### Within Each Phase

- Tasks marked [P] can run in parallel
- Sequential tasks within a phase follow listed order
- Shell library tasks (T002-T007) are all parallel — different files, no dependencies

### Parallel Opportunities

**Phase 1** — All library files (T002-T007) can be written in parallel:
```
T002 common.sh  ║  T003 version.sh  ║  T004 python-check.sh
T005 shell-detect.sh  ║  T006 download.sh  ║  T007 docker-setup.sh
```

**Phase 2** — All test files (T009-T012) can be written in parallel:
```
T009 test-version.sh  ║  T010 test-common.sh
T011 test-download.sh  ║  T012 test-shell-detect.sh
```

**Phase 6** — Package script and GHA workflow can be partially parallel:
```
T027 package-release.sh  ║  (T028 release.yml references T027, so sequential)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (shell libraries)
2. Complete Phase 2: Foundational (shell tests)
3. Complete Phase 3: US1 — One-Line Installation
4. **STOP and VALIDATE**: Run `bash installer/install.sh` on clean environment
5. If install works → MVP is functional

### Incremental Delivery

1. Phase 1 + 2 → Shell foundation ready
2. Phase 3 (US1) → Installation works → **MVP!**
3. Phase 4 (US2) → Auto-update notifications → Users stay informed
4. Phase 6 (US4) → GHA releases → Automated release pipeline
5. Phase 5 (US3) → Manual update → Users can self-update (needs US4 releases)
6. Phase 7 (US5) → Uninstall → Clean removal
7. Phase 8 → Polish → Production ready

### Recommended Order (Solo Developer)

P1 stories first, then P2, then P3:
```
Setup → Foundational → US1 (Install) → US2 (Auto-Update) → US4 (GHA) → US3 (Update) → US5 (Uninstall) → Polish
```

Note: US4 (GHA Pipeline) is recommended before US3 (Manual Update) because the update command downloads release tarballs — those don't exist until the GHA pipeline creates them.

---

## Summary

| Phase | Tasks | Parallel | Description |
|-------|-------|----------|-------------|
| 1. Setup | T001-T008 | 6 of 8 | Shell libraries + test runner |
| 2. Foundational | T009-T012 | 4 of 4 | Shell unit tests |
| 3. US1 Install | T013-T018 | 0 of 6 | One-line install (MVP) |
| 4. US2 Auto-Update | T019-T022 | 0 of 4 | Version check + notification |
| 5. US3 Manual Update | T023-T026 | 0 of 4 | Update + rollback |
| 6. US4 GHA Pipeline | T027-T029 | 1 of 3 | Release automation |
| 7. US5 Uninstall | T030-T032 | 0 of 3 | Clean removal |
| 8. Polish | T033-T037 | 3 of 5 | Docs, security, validation |
| **Total** | **37 tasks** | **14 parallel** | |

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US3 (Manual Update) depends on US4 (GHA Pipeline) for release artifacts
- Shell tests use simple bash assertions (no external test framework needed)
- Python tests use pytest with tmp_path fixture for isolation
- All integration tests use MEMORIA_INSTALL_DIR env var to avoid touching the real `~/.local/share/memoria/`
