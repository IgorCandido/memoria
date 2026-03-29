# Claude Supervisor Installer

Development documentation for the Claude Supervisor installation system.

## Directory Structure

```
installer/
├── README.md               # This file
├── VERSION                 # Installer version (semver)
├── install.sh              # Global installer entry point (curl | bash)
├── claude-supervisor-install.sh  # Main installer logic
├── lib/
│   ├── shell-detect.sh     # Shell detection (bash/zsh/fish)
│   ├── version.sh          # Version management functions
│   ├── download.sh         # GitHub release download logic
│   ├── plugin-setup.sh     # Claude plugin directory creation
│   ├── python-check.sh     # Python version verification
│   └── common.sh           # Error handling, logging, utilities
└── templates/
    ├── shell-function.bash # Shell function template (bash/zsh)
    └── shell-function.fish # Shell function template (fish)
```

## Development Workflow

### Prerequisites

- Bash 4.0+ (macOS/Linux)
- Python 3.11+ (for testing)
- `shellcheck` for linting (optional but recommended)

### Running Tests

```bash
# Unit tests for library functions
./tests/installer/unit/run-tests.sh

# Integration tests (requires clean environment)
./tests/installer/integration/test-macos-fresh-install.sh
./tests/installer/integration/test-ubuntu-fresh-install.sh
./tests/installer/integration/test-upgrade-scenarios.sh
./tests/installer/integration/test-uninstall.sh
```

### Linting

```bash
# Lint all shell scripts
find installer/ -name "*.sh" -exec shellcheck {} \;
```

### Local Testing

1. **Test install.sh without downloading**:
   ```bash
   # Source functions locally
   source installer/lib/shell-detect.sh
   source installer/lib/version.sh

   # Test functions
   detect_shell
   compare_versions "0.3.0" "0.4.0"
   ```

2. **Test full installation locally**:
   ```bash
   # Run install.sh pointing to local files
   INSTALLER_LOCAL=1 ./installer/install.sh
   ```

3. **Test project initialization**:
   ```bash
   # Create test directory
   mkdir -p /tmp/test-project
   cd /tmp/test-project

   # Initialize
   ~/.local/bin/claude-supervisor-install init .
   ```

## Architecture

### Two-Stage Installation

1. **Global Installation** (`curl | bash`):
   - Installs `claude-supervisor-install` to `~/.local/bin/`
   - Sets up shell function in `~/.local/share/claude-supervisor/shell-init.sh`
   - Updates shell config (.zshrc, .bashrc, etc.) to source shell-init.sh

2. **Project Initialization** (`claude-supervisor-install init .`):
   - Downloads supervisor to `.claude/supervisor/`
   - Creates plugin directory structure (skills/, commands/, etc.)
   - Generates `.claude/manifest.json` with version and checksums

### Shell Function

The `claude-supervisor` shell function:
- Detects `.claude/` in current directory
- Executes `.claude/supervisor/claude_supervisor.py` with all arguments
- Provides helpful error messages when not initialized

### Version Isolation

- Global installer version tracked in `~/.local/share/claude-supervisor/config.json`
- Each project has its own supervisor version in `.claude/manifest.json`
- Upgrading global installer doesn't affect project versions
- Projects can use different supervisor versions

## Testing Strategy

### Unit Tests

Test individual library functions in isolation:
- `test-shell-detect.sh`: Shell detection logic
- `test-version.sh`: Version comparison functions
- `test-download.sh`: Download and checksum verification

### Integration Tests

Full installation flows on clean environments:
- Fresh install on macOS
- Fresh install on Ubuntu/Debian
- Upgrade scenarios (global + project)
- Uninstallation (global + project cleanup)

### E2E Tests

Complete user journeys:
1. Install → Init → Run supervisor → Verify output
2. Install old version → Upgrade → Verify no data loss
3. Install → Uninstall → Verify clean removal

## Release Process

1. Update `VERSION` file
2. Run full test suite
3. Create GitHub release with tag matching VERSION
4. Verify `curl | bash` installation works

## Debugging

### Common Issues

**"command not found: claude-supervisor-install"**
- Check `~/.local/bin` is in PATH
- Run `source ~/.zshrc` or restart shell

**"Python 3.11+ required"**
- Install Python 3.11+: `brew install python@3.11` (macOS)
- Verify: `python3 --version`

**"No .claude/ directory found"**
- Run `claude-supervisor-install init .` in project root

### Log Locations

- Installation logs: `~/.local/share/claude-supervisor/install.log`
- Supervisor logs: `.claude_supervisor/` (in project directory)

## Contributing

1. Follow shell scripting best practices
2. Add tests for new functionality
3. Run `shellcheck` before committing
4. Update this README for new features
