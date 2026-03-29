#!/usr/bin/env bash
# Claude Supervisor Install - Main Installer Tool
# Requires: Bash 4.0+ (BR-024)
# Commands: init, uninstall, clean, --version, --help
#
# Usage:
#   claude-supervisor-install init <directory> [--version VERSION]
#   claude-supervisor-install uninstall [--yes]
#   claude-supervisor-install clean <directory> [--yes]
#   claude-supervisor-install --version
#   claude-supervisor-install --help

set -euo pipefail

# Get script directory for library imports
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if running from installed location or development
if [[ -d "$SCRIPT_DIR/../installer/lib" ]]; then
    # Development mode
    LIB_DIR="$SCRIPT_DIR/../installer/lib"
elif [[ -d "${HOME}/.local/share/claude-supervisor/lib" ]]; then
    # Installed mode (libs bundled)
    LIB_DIR="${HOME}/.local/share/claude-supervisor/lib"
else
    # Fallback: assume libs are in same directory
    LIB_DIR="$SCRIPT_DIR"
fi

# Source library functions if available
[[ -f "$LIB_DIR/common.sh" ]] && source "$LIB_DIR/common.sh"
[[ -f "$LIB_DIR/version.sh" ]] && source "$LIB_DIR/version.sh"
[[ -f "$LIB_DIR/download.sh" ]] && source "$LIB_DIR/download.sh"
[[ -f "$LIB_DIR/plugin-setup.sh" ]] && source "$LIB_DIR/plugin-setup.sh"
[[ -f "$LIB_DIR/python-check.sh" ]] && source "$LIB_DIR/python-check.sh"
[[ -f "$LIB_DIR/shell-detect.sh" ]] && source "$LIB_DIR/shell-detect.sh"

# BR-012: Validate required functions are loaded
validate_library_loading() {
    local missing_functions=()

    # Check common.sh functions
    declare -f log_info >/dev/null || missing_functions+=("log_info from common.sh")
    declare -f log_error >/dev/null || missing_functions+=("log_error from common.sh")
    declare -f log_step >/dev/null || missing_functions+=("log_step from common.sh")
    declare -f die >/dev/null || missing_functions+=("die from common.sh")

    # Check version.sh functions
    declare -f compare_versions >/dev/null || missing_functions+=("compare_versions from version.sh")
    declare -f validate_semver >/dev/null || missing_functions+=("validate_semver from version.sh")

    # Check download.sh functions
    declare -f download_release >/dev/null || missing_functions+=("download_release from download.sh")

    # Check plugin-setup.sh functions
    declare -f create_plugin_structure >/dev/null || missing_functions+=("create_plugin_structure from plugin-setup.sh")

    # Check python-check.sh functions
    declare -f check_python_version >/dev/null || missing_functions+=("check_python_version from python-check.sh")

    # Check shell-detect.sh functions
    declare -f detect_shell >/dev/null || missing_functions+=("detect_shell from shell-detect.sh")
    declare -f get_shell_config_file >/dev/null || missing_functions+=("get_shell_config_file from shell-detect.sh")

    if [[ ${#missing_functions[@]} -gt 0 ]]; then
        echo "ERROR: Required functions not found after sourcing libraries:" >&2
        printf '  - %s\n' "${missing_functions[@]}" >&2
        echo "Library directory: $LIB_DIR" >&2
        exit 1
    fi
}

# Validate libraries loaded successfully
validate_library_loading

# Version (read from VERSION file or use default)
VERSION_FILE="$(dirname "$SCRIPT_DIR")/installer/VERSION"
if [[ -f "$VERSION_FILE" ]]; then
    INSTALLER_VERSION=$(cat "$VERSION_FILE")
else
    INSTALLER_VERSION="0.3.0"
fi

# GitHub repository info
GITHUB_REPO="IgorCandido/claude-supervisor"
GITHUB_DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download"

# Configuration
INSTALL_SHARE_DIR="${HOME}/.local/share/claude-supervisor"
CONFIG_FILE="$INSTALL_SHARE_DIR/config.json"

# Color codes (define if not sourced from common.sh)
RED="${RED:-\033[0;31m}"
GREEN="${GREEN:-\033[0;32m}"
YELLOW="${YELLOW:-\033[0;33m}"
BLUE="${BLUE:-\033[0;34m}"
NC="${NC:-\033[0m}"

# Logging (define if not sourced)
log_info() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*" >&2; }
log_error() { echo -e "${RED}Error:${NC} $*" >&2; }
log_step() { echo -e "${BLUE}→${NC} $*"; }

die() {
    log_error "$@"
    exit 1
}

# T031: Show help
show_help() {
    cat << EOF
claude-supervisor-install - Installation tool for Claude Supervisor

Usage:
  claude-supervisor-install init <directory> [--version VERSION]
  claude-supervisor-install uninstall [--yes]
  claude-supervisor-install clean <directory> [--yes]
  claude-supervisor-install --version
  claude-supervisor-install --help

Commands:
  init        Initialize a project with Claude Supervisor
  uninstall   Remove global installer and shell integration
  clean       Remove supervisor from a specific project

Options:
  --version VERSION   Specific supervisor version to install (default: latest)
  --yes               Skip confirmation prompts
  --help              Show this help message

Examples:
  # Install latest version in current project
  claude-supervisor-install init .

  # Install specific version
  claude-supervisor-install init . --version v0.3.0

  # Remove supervisor from current project
  claude-supervisor-install clean .

  # Completely uninstall
  claude-supervisor-install uninstall

For more information: https://github.com/${GITHUB_REPO}
EOF
    exit 0
}

# T030: Show version
show_version() {
    echo "claude-supervisor-install v${INSTALLER_VERSION}"
    exit 0
}

# BR-007: Validate version string format
validate_version_format() {
    local version="$1"

    # Allow "latest" as special case
    if [[ "$version" == "latest" ]]; then
        return 0
    fi

    # Remove 'v' prefix if present
    local version_num="${version#v}"

    # Validate semver format: X.Y.Z or X.Y.Z-prerelease
    if [[ ! "$version_num" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+(\.[0-9]+)?)?$ ]]; then
        log_error "Invalid version format: $version"
        log_info "Expected: X.Y.Z (e.g., 0.3.0 or v0.3.0)"
        return 1
    fi

    return 0
}

# BR-007: Validate directory path
validate_directory_path() {
    local dir="$1"

    # Check for null/empty
    if [[ -z "$dir" ]]; then
        log_error "Directory path cannot be empty"
        return 1
    fi

    # Check for suspicious patterns
    if [[ "$dir" =~ ^- ]]; then
        log_error "Directory path cannot start with '-' (looks like a flag)"
        return 1
    fi

    # Check for control characters
    if [[ "$dir" =~ [[:cntrl:]] ]]; then
        log_error "Directory path contains control characters"
        return 1
    fi

    return 0
}

# T021: Parse arguments
parse_args() {
    COMMAND=""
    TARGET_DIR=""
    TARGET_VERSION="latest"
    SKIP_CONFIRM=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            init|uninstall|clean)
                COMMAND="$1"
                shift
                ;;
            --version)
                if [[ -z "$COMMAND" ]]; then
                    show_version
                else
                    shift
                    TARGET_VERSION="${1:-latest}"
                    # BR-007: Validate version format
                    if ! validate_version_format "$TARGET_VERSION"; then
                        exit 1
                    fi
                    shift
                fi
                ;;
            --help|-h)
                show_help
                ;;
            --yes|-y)
                SKIP_CONFIRM=true
                shift
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                if [[ -z "$TARGET_DIR" ]]; then
                    # BR-007: Validate directory path
                    if ! validate_directory_path "$1"; then
                        exit 1
                    fi
                    TARGET_DIR="$1"
                fi
                shift
                ;;
        esac
    done

    # Validate command
    if [[ -z "$COMMAND" ]]; then
        show_help
    fi

    # BR-007: Validate flag combinations
    if [[ "$COMMAND" == "init" && -z "$TARGET_DIR" ]]; then
        die "Command 'init' requires a directory argument"
    fi

    if [[ "$COMMAND" == "clean" && -z "$TARGET_DIR" ]]; then
        die "Command 'clean' requires a directory argument"
    fi
}

# T23: Validate directory for init (BR-002: Enhanced path validation)
validate_init_directory() {
    local dir="$1"

    # BR-002: Reject paths containing .. before resolving
    if [[ "$dir" == *".."* ]]; then
        die "Security: Path traversal detected (..). Use absolute paths or paths without '..' components."
    fi

    # Resolve to absolute path
    if [[ "$dir" == "." ]]; then
        dir="$(pwd)"
    else
        dir="$(cd "$dir" 2>/dev/null && pwd)" || die "Directory does not exist: $dir"
    fi

    # BR-002: Validate not in sensitive directories (system or home root)
    case "$dir" in
        /|/etc|/var|/System|/usr|/bin|/sbin|/root|/boot|/dev|/proc|/sys|/tmp)
            die "Security: Cannot run in sensitive system directory: $dir"
            ;;
        "$HOME")
            die "Security: Cannot run directly in home directory root: $dir. Create a project subdirectory."
            ;;
    esac

    # BR-002: Check for symlinks to sensitive directories
    if [[ -L "$dir" ]]; then
        local target
        target=$(readlink -f "$dir" 2>/dev/null || realpath "$dir" 2>/dev/null || echo "$dir")
        case "$target" in
            /|/etc|/var|/System|/usr|/bin|/sbin|/root|/boot|/dev|/proc|/sys|/tmp)
                die "Security: Directory is a symlink to sensitive system directory: $target"
                ;;
        esac
    fi

    # Check writable
    if [[ ! -w "$dir" ]]; then
        die "Directory is not writable: $dir"
    fi

    echo "$dir"
}

# T23: Check network connectivity
check_network() {
    log_step "Checking network connectivity..."
    if ! curl --silent --head --fail --connect-timeout 5 "https://github.com" > /dev/null 2>&1; then
        die "Cannot connect to GitHub. Check your internet connection."
    fi
    log_info "Network connectivity OK"
}

# T24: Resolve version
resolve_version() {
    local requested="$1"

    if [[ "$requested" == "latest" ]]; then
        log_step "Fetching latest version..." >&2
        local latest
        # TODO: When repo goes public, change back to curl
        # latest=$(curl --silent --fail "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" 2>/dev/null | \
        #          grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)
        # For private repo, use gh api
        latest=$(gh api "repos/${GITHUB_REPO}/releases/latest" 2>/dev/null | \
                 grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)

        if [[ -z "$latest" ]]; then
            # Fallback to installer version
            log_warning "Could not fetch latest version, using installer version" >&2
            latest="v${INSTALLER_VERSION}"
        fi

        echo "$latest"
    else
        # Ensure 'v' prefix
        [[ "$requested" != v* ]] && requested="v$requested"
        echo "$requested"
    fi
}

# T25: Download supervisor release
download_supervisor() {
    local version="$1"
    local target_dir="$2"

    local version_num="${version#v}"
    local tarball_url="${GITHUB_DOWNLOAD_URL}/${version}/claude-supervisor-${version_num}.tar.gz"
    local checksums_url="${GITHUB_DOWNLOAD_URL}/${version}/checksums.txt"

    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" EXIT

    log_step "Downloading claude-supervisor ${version}..."

    local tarball_path="$temp_dir/claude-supervisor.tar.gz"
    local checksums_path="$temp_dir/checksums.txt"

    # Download tarball and checksums
    # TODO: When repo goes public, change back to curl
    # For private repo, use gh release download
    if ! gh release download "$version" --repo "$GITHUB_REPO" --pattern "claude-supervisor-${version_num}.tar.gz" --pattern "checksums.txt" --dir "$temp_dir"; then
        # Release might not exist yet - create from source
        log_warning "Release not found, using development version"
        log_error "gh release download failed. Debug info:"
        log_error "  Version: $version"
        log_error "  Repo: $GITHUB_REPO"
        log_error "  Pattern: claude-supervisor-${version_num}.tar.gz"
        log_error "  Temp dir: $temp_dir"
        create_dev_installation "$target_dir" "$version"
        return 0
    fi

    # Rename downloaded files to expected paths
    mv "$temp_dir/claude-supervisor-${version_num}.tar.gz" "$tarball_path"

    # BR-013: Verify checksums file exists (mandatory for release versions)
    if [[ ! -f "$temp_dir/checksums.txt" ]]; then
        die "Checksums file not available for release ${version}. Cannot verify download integrity. This is a security requirement for production releases."
    fi
    mv "$temp_dir/checksums.txt" "$checksums_path"

    # BR-013: Verify checksum (mandatory for release versions)
    log_step "Verifying checksum..."
    local expected_checksum
    expected_checksum=$(grep "claude-supervisor-${version_num}.tar.gz" "$checksums_path" | cut -d' ' -f1)

    if [[ -z "$expected_checksum" ]]; then
        die "Checksum not found in checksums.txt for claude-supervisor-${version_num}.tar.gz"
    fi

    local actual_checksum
    if command -v sha256sum &> /dev/null; then
        actual_checksum=$(sha256sum "$tarball_path" | cut -d' ' -f1)
    else
        actual_checksum=$(shasum -a 256 "$tarball_path" | cut -d' ' -f1)
    fi

    if [[ "$actual_checksum" != "$expected_checksum" ]]; then
        die "Checksum verification failed for ${version}. Expected: ${expected_checksum}, Got: ${actual_checksum}"
    fi

    log_info "Checksum verified: ${actual_checksum}"

    log_info "Downloaded claude-supervisor ${version}"

    # CRITICAL-002 FIX: Validate tarball contents before extraction
    log_step "Validating tarball contents..."
    if ! tar -tzf "$tarball_path" > /dev/null 2>&1; then
        die "Tarball is corrupted or invalid"
    fi

    # Check for path traversal attempts in tarball entries
    local has_traversal=false
    while IFS= read -r entry; do
        if [[ "$entry" =~ \.\. ]]; then
            log_error "Security: Tarball contains path traversal: $entry"
            has_traversal=true
        fi
    done < <(tar -tzf "$tarball_path")

    if [[ "$has_traversal" == true ]]; then
        die "Security: Tarball contains dangerous path traversal entries"
    fi

    # T27: Extract to .claude/supervisor/
    log_step "Extracting supervisor..."
    local supervisor_dir="$target_dir/.claude/supervisor"
    mkdir -p "$supervisor_dir"

    # Extract with safety flags: --no-same-owner prevents ownership issues
    tar -xzf "$tarball_path" -C "$supervisor_dir" --strip-components=1 --no-same-owner 2>/dev/null || \
        tar -xzf "$tarball_path" -C "$supervisor_dir" --no-same-owner 2>/dev/null

    log_info "Extracted to: $supervisor_dir"
}

# Create development installation (for when release doesn't exist)
create_dev_installation() {
    local target_dir="$1"
    local version="$2"

    local supervisor_dir="$target_dir/.claude/supervisor"
    mkdir -p "$supervisor_dir"

    # Copy from repository root if we're in development
    local repo_root
    repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

    if [[ -f "$repo_root/claude_supervisor.py" ]]; then
        cp "$repo_root/claude_supervisor.py" "$supervisor_dir/"
        log_info "Installed development version from local repository"
    elif [[ -d "$repo_root/src" ]]; then
        cp -r "$repo_root/src" "$supervisor_dir/"
        # BR-006: Log warning if legacy file doesn't exist (expected for hexagonal architecture)
        if [[ -f "$repo_root/claude_supervisor.py" ]]; then
            cp "$repo_root/claude_supervisor.py" "$supervisor_dir/"
        else
            log_warning "Legacy claude_supervisor.py not found (expected for hexagonal architecture)"
        fi
        log_info "Installed development version from local repository"
    else
        die "Cannot find supervisor source files"
    fi
}

# T26: Create plugin structure
create_plugin_structure() {
    local target_dir="$1"

    log_step "Creating plugin directory structure..."

    local claude_dir="$target_dir/.claude"
    mkdir -p "$claude_dir/skills"
    mkdir -p "$claude_dir/commands"
    mkdir -p "$claude_dir/agents"
    mkdir -p "$claude_dir/config"
    mkdir -p "$claude_dir/supervisor"

    # Create .gitkeep files
    for dir in skills commands agents config; do
        touch "$claude_dir/$dir/.gitkeep"
    done

    log_info "Created plugin structure in .claude/"
}

# T006: Prompt user to select panel manager for live output display
prompt_panel_manager() {
    # Non-interactive mode or SKIP_CONFIRM: default to "none"
    if [[ "$SKIP_CONFIRM" == true ]] || [[ ! -t 0 ]]; then
        echo "none"
        return
    fi

    echo "" >&2
    echo "Select panel manager for live output display:" >&2
    echo "  1) tmux   - Use tmux panes (recommended if you use tmux)" >&2
    echo "  2) zellij - Use zellij panes" >&2
    echo "  3) none   - No panel management (subprocess only)" >&2
    echo "" >&2
    read -r -p "Choice [1-3] (default: 3): " choice

    case "$choice" in
        1) echo "tmux" ;;
        2) echo "zellij" ;;
        3|"") echo "none" ;;
        *)
            log_warning "Invalid choice '$choice', defaulting to 'none'"
            echo "none"
            ;;
    esac
}

# T28: Generate manifest
# T007: Accept panel_manager parameter and include in manifest JSON
generate_manifest() {
    local target_dir="$1"
    local version="$2"
    local panel_manager="${3:-none}"

    # BR-012: Validate panel_manager value before writing to JSON
    case "$panel_manager" in
        tmux|zellij|none) ;;
        *)
            log_warning "Invalid panel_manager value '$panel_manager', defaulting to 'none'"
            panel_manager="none"
            ;;
    esac

    log_step "Generating manifest..."

    local manifest_file="$target_dir/.claude/manifest.json"
    local install_date
    install_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Compute checksums for installed files
    local checksums="[]"
    local supervisor_dir="$target_dir/.claude/supervisor"
    if [[ -d "$supervisor_dir" ]]; then
        local files=()
        while IFS= read -r -d '' file; do
            local filename checksum
            filename=$(basename "$file")
            if command -v sha256sum &> /dev/null; then
                checksum=$(sha256sum "$file" | cut -d' ' -f1)
            else
                checksum=$(shasum -a 256 "$file" | cut -d' ' -f1)
            fi
            files+=("\"$filename:$checksum\"")
        done < <(find "$supervisor_dir" -type f -name "*.py" -print0 2>/dev/null)

        if [[ ${#files[@]} -gt 0 ]]; then
            checksums="[$(IFS=,; echo "${files[*]}")]"
        fi
    fi

    cat > "$manifest_file" << EOF
{
    "version": "${version#v}",
    "install_date": "$install_date",
    "installer_version": "$INSTALLER_VERSION",
    "panel_manager": "$panel_manager",
    "release_url": "${GITHUB_DOWNLOAD_URL}/${version}/claude-supervisor-${version#v}.tar.gz",
    "file_checksums": $checksums
}
EOF

    log_info "Generated manifest: $manifest_file"
}

# T29: Update global config
update_global_config() {
    local project_dir="$1"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        mkdir -p "$(dirname "$CONFIG_FILE")"
        echo '{"projects":[]}' > "$CONFIG_FILE"
    fi

    # Add project to list if not already present (simple approach without jq)
    if ! grep -qF "\"$project_dir\"" "$CONFIG_FILE" 2>/dev/null; then
        # Read existing projects
        local projects
        projects=$(grep -o '"projects"[[:space:]]*:[[:space:]]*\[[^]]*\]' "$CONFIG_FILE" | \
                   sed 's/"projects"[[:space:]]*:[[:space:]]*\[//' | sed 's/\]//' | tr -d ' ')

        if [[ -n "$projects" && "$projects" != "\"\"" ]]; then
            projects="$projects,\"$project_dir\""
        else
            projects="\"$project_dir\""
        fi

        # Rewrite config file
        local install_date
        install_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        cat > "$CONFIG_FILE" << EOF
{
    "installer_version": "$INSTALLER_VERSION",
    "last_update": "$install_date",
    "projects": [$projects]
}
EOF
    fi
}

# T22: Init command implementation
cmd_init() {
    local target_dir="${TARGET_DIR:-.}"

    # T23: Validate directory
    target_dir=$(validate_init_directory "$target_dir")
    echo "Initializing Claude Supervisor in: $target_dir"
    echo ""

    # T009: Handle existing installation and panel_manager upgrade path
    local panel_manager=""
    if [[ -f "$target_dir/.claude/manifest.json" ]]; then
        local current_version
        current_version=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$target_dir/.claude/manifest.json" | \
                         head -1 | cut -d'"' -f4)
        log_warning "Found existing installation: v${current_version}"

        # T009: Read current panel_manager from existing manifest
        local current_panel_manager
        current_panel_manager=$(grep -o '"panel_manager"[[:space:]]*:[[:space:]]*"[^"]*"' "$target_dir/.claude/manifest.json" 2>/dev/null | \
                               head -1 | cut -d'"' -f4 || true)

        if [[ "$SKIP_CONFIRM" != true ]]; then
            echo ""
            read -r -p "Reinstall/upgrade? (y/N): " confirm
            if [[ ! "$confirm" =~ ^[Yy] ]]; then
                echo "Cancelled"
                exit 4
            fi

            # T009: Ask about keeping current panel_manager during upgrade
            if [[ -n "$current_panel_manager" ]]; then
                echo ""
                read -r -p "Keep current panel manager [$current_panel_manager]? (Y/n): " keep_pm
                if [[ "$keep_pm" =~ ^[Nn] ]]; then
                    panel_manager=$(prompt_panel_manager)
                else
                    panel_manager="$current_panel_manager"
                fi
            fi
        else
            # Non-interactive upgrade: preserve current panel_manager
            if [[ -n "$current_panel_manager" ]]; then
                panel_manager="$current_panel_manager"
            fi
        fi

        # Create backup (BR-006: fail loudly if backup fails)
        log_step "Creating backup..."
        local backup_dir="$target_dir/.claude/.backup-${current_version}-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$backup_dir"

        if ! cp -r "$target_dir/.claude/supervisor" "$backup_dir/" 2>/dev/null; then
            log_error "Failed to backup supervisor directory"
            die "Backup failed - refusing to upgrade without backup"
        fi

        if ! cp "$target_dir/.claude/manifest.json" "$backup_dir/" 2>/dev/null; then
            log_warning "Could not backup manifest.json (may not exist)"
        fi

        log_info "Backed up to: $backup_dir"
    fi

    # T23: Check Python
    log_step "Checking Python..."
    local python_version
    python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    local major minor
    major=$(echo "$python_version" | cut -d. -f1)
    minor=$(echo "$python_version" | cut -d. -f2)
    if [[ $major -lt 3 ]] || [[ $major -eq 3 && $minor -lt 11 ]]; then
        die "Python 3.11+ required, found Python $python_version"
    fi
    log_info "Python $python_version found"

    # T008: Prompt for panel_manager selection (after Python check, before download)
    if [[ -z "$panel_manager" ]]; then
        panel_manager=$(prompt_panel_manager)
    fi
    log_info "Panel manager: $panel_manager"

    # T23: Check network
    check_network

    # T24: Resolve version
    local version
    version=$(resolve_version "$TARGET_VERSION")
    log_info "Installing version: $version"

    # BR-009: Transactional installation - use temp dir, atomically replace on success
    local temp_dir
    temp_dir=$(mktemp -d -t claude-supervisor-install.XXXXXX)
    trap "rm -rf '$temp_dir'" EXIT ERR INT TERM

    log_step "Preparing installation in temporary directory..."

    # T26: Create plugin structure in temp dir
    mkdir -p "$temp_dir/.claude"
    create_plugin_structure "$temp_dir"

    # T25, T27: Download and extract to temp dir
    download_supervisor "$version" "$temp_dir"

    # T28: Generate manifest in temp dir (T007: include panel_manager)
    generate_manifest "$temp_dir" "$version" "$panel_manager"

    # Verify installation succeeded before replacing target
    if [[ ! -d "$temp_dir/.claude/supervisor" ]]; then
        rm -rf "$temp_dir"
        die "Installation failed - supervisor directory not created"
    fi

    if [[ ! -f "$temp_dir/.claude/manifest.json" ]]; then
        rm -rf "$temp_dir"
        die "Installation failed - manifest not generated"
    fi

    # Atomic replacement: move temp .claude to target
    log_step "Installing to target directory (atomic replacement)..."
    if [[ -d "$target_dir/.claude" ]]; then
        # Remove old installation (backup already created above)
        rm -rf "$target_dir/.claude"
    fi

    mv "$temp_dir/.claude" "$target_dir/.claude"
    log_info "Installation atomically replaced"

    # T29: Update global config
    update_global_config "$target_dir"

    # Cleanup temp dir (trap will also handle this)
    rm -rf "$temp_dir"

    # Success message
    echo ""
    echo "════════════════════════════════════════════════════════════"
    log_info "Installation complete!"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "Usage:"
    echo "  cd $target_dir"
    echo "  claude-supervisor"
    echo ""
    echo "The supervisor will load prompt from:"
    echo "  1. prompt.md in your project root (custom prompt), OR"
    echo "  2. Default prompt from .claude/supervisor/prompt.md (speckit.implement workflow)"
    echo ""
    echo "For help: claude-supervisor --help"
    echo ""
}

# Uninstall command (T051-T056 - Phase 5)
cmd_uninstall() {
    echo "Uninstalling claude-supervisor-install..."
    echo ""

    if [[ "$SKIP_CONFIRM" != true ]]; then
        echo "This will remove:"
        echo "  - claude-supervisor-install from ~/.local/bin/"
        echo "  - Shell integration from ~/.zshrc, ~/.bashrc"
        echo "  - Configuration from ~/.local/share/claude-supervisor/"
        echo ""
        echo "Project installations (.claude/ directories) will NOT be removed."
        echo ""
        read -r -p "Continue? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy] ]]; then
            echo "Cancelled"
            exit 1
        fi
    fi

    # Remove binary
    local bin_path="${HOME}/.local/bin/claude-supervisor-install"
    if [[ -f "$bin_path" ]]; then
        rm -f "$bin_path"
        log_info "Removed: $bin_path"
    fi

    # BR-010: Fix silent failures in uninstall - check each operation
    local uninstall_incomplete=false
    local cleaned_files=0

    # Remove shell config entries
    for config in "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.zshrc" "$HOME/.zprofile"; do
        if [[ -f "$config" ]]; then
            if grep -q "claude-supervisor" "$config" 2>/dev/null; then
                # Remove lines containing claude-supervisor
                local temp_file
                temp_file=$(mktemp)

                if grep -v "claude-supervisor" "$config" > "$temp_file" 2>/dev/null; then
                    if mv "$temp_file" "$config" 2>/dev/null; then
                        log_info "Cleaned: $config"
                        ((cleaned_files++))
                    else
                        log_error "Failed to update $config (permission denied?)"
                        uninstall_incomplete=true
                        rm -f "$temp_file"
                    fi
                else
                    log_error "Failed to process $config"
                    uninstall_incomplete=true
                    rm -f "$temp_file"
                fi
            fi
        fi
    done

    if [[ $cleaned_files -eq 0 ]]; then
        log_warning "No shell configuration files were cleaned (may already be removed)"
    fi

    # Remove share directory
    if [[ -d "$INSTALL_SHARE_DIR" ]]; then
        if rm -rf "$INSTALL_SHARE_DIR" 2>/dev/null; then
            log_info "Removed: $INSTALL_SHARE_DIR"
        else
            log_error "Failed to remove $INSTALL_SHARE_DIR (permission denied?)"
            uninstall_incomplete=true
        fi
    fi

    echo ""
    if [[ "$uninstall_incomplete" == true ]]; then
        log_warning "Uninstallation completed with errors - some files may remain"
        echo ""
        echo "Manual cleanup may be required for:"
        echo "  - Shell config files that couldn't be updated"
        echo "  - Directories with permission issues"
        echo ""
    else
        log_info "Uninstallation complete"
    fi
    echo ""
    echo "Restart your shell or run: source ~/.zshrc"
    echo ""

    # Offer project cleanup info
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "To clean up project installations, manually delete .claude/ directories"
        echo ""
    fi
}

# Clean command (T057-T061 - Phase 5)
cmd_clean() {
    local target_dir="${TARGET_DIR:-.}"

    # Resolve path
    if [[ "$target_dir" == "." ]]; then
        target_dir="$(pwd)"
    else
        target_dir="$(cd "$target_dir" 2>/dev/null && pwd)" || die "Directory does not exist: $target_dir"
    fi

    local claude_dir="$target_dir/.claude"

    if [[ ! -d "$claude_dir" ]]; then
        die "No .claude/ directory found in: $target_dir"
    fi

    # Get installed version
    local version="unknown"
    if [[ -f "$claude_dir/manifest.json" ]]; then
        version=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$claude_dir/manifest.json" | \
                 head -1 | cut -d'"' -f4)
    fi

    echo "This will remove .claude/ directory from:"
    echo "  $target_dir"
    echo ""
    echo "Installed version: v${version}"
    echo ""

    if [[ "$SKIP_CONFIRM" != true ]]; then
        read -r -p "Continue? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy] ]]; then
            echo "Cancelled"
            exit 1
        fi
    fi

    rm -rf "$claude_dir"
    log_info "Removed .claude/ from $target_dir"

    echo ""
    echo "To reinstall: claude-supervisor-install init $target_dir"
    echo ""
}

# Main
main() {
    parse_args "$@"

    case "$COMMAND" in
        init)
            cmd_init
            ;;
        uninstall)
            cmd_uninstall
            ;;
        clean)
            cmd_clean
            ;;
        *)
            die "Unknown command: $COMMAND"
            ;;
    esac
}

main "$@"
