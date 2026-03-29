#!/usr/bin/env bash
# Common Utilities Library
# Requires: Bash 4.0+ (BR-024)
# Shared functions for error handling, logging, lock files, and PATH verification

# BR-014: Configuration constants
readonly LOCK_TIMEOUT_SECONDS=600

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $*" >&2
}

log_error() {
    echo -e "${RED}Error:${NC} $*" >&2
}

log_step() {
    echo -e "${BLUE}→${NC} $*"
}

# Error handling
die() {
    log_error "$@"
    exit 1
}

# BR-025: Detect OS once at script load for efficient stat usage
DETECTED_OS="$(uname -s)"

# BR-025: Cross-platform file modification time helper
# Arguments: file_path
# Returns: modification time in seconds since epoch
get_file_mtime() {
    local file_path="$1"

    if [[ ! -e "$file_path" ]]; then
        echo "0"
        return 1
    fi

    # Use appropriate stat command based on OS (detected once)
    if [[ "$DETECTED_OS" == "Darwin" ]]; then
        stat -f %m "$file_path" 2>/dev/null || echo "0"
    else
        stat -c %Y "$file_path" 2>/dev/null || echo "0"
    fi
}

# Check if running as root (we don't want that)
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Do not run this installer as root"
        log_info "Install to user directory with: curl ... | bash (no sudo)"
        return 1
    fi
    return 0
}

# Lock file management (BR-003: Use atomic mkdir-based locking)
LOCK_DIR="${TMPDIR:-/tmp}/claude-supervisor-install.lock.d"

# Acquire lock to prevent concurrent installations
acquire_lock() {
    # BR-003: Use atomic mkdir for race-free locking
    # mkdir is atomic on all POSIX systems - either succeeds or fails
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        # Lock acquired successfully
        echo $$ > "$LOCK_DIR/pid"
        return 0
    fi

    # Lock directory exists - check if stale (older than 10 minutes)
    local lock_age
    if [[ -d "$LOCK_DIR" ]]; then
        # BR-025: Use helper function for cross-platform stat
        lock_age=$(($(date +%s) - $(get_file_mtime "$LOCK_DIR")))

        if [[ $lock_age -lt $LOCK_TIMEOUT_SECONDS ]]; then
            # BR-014: Fresh lock - another installation is running
            local other_pid
            other_pid=$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "unknown")
            log_error "Another installation is in progress (PID: $other_pid)"
            log_info "If this is incorrect, remove $LOCK_DIR and try again"
            return 1
        fi

        # Stale lock (>10 minutes) - remove and retry once
        log_warning "Found stale lock (${lock_age}s old), removing..."
        rm -rf "$LOCK_DIR"

        # Retry lock acquisition
        if mkdir "$LOCK_DIR" 2>/dev/null; then
            echo $$ > "$LOCK_DIR/pid"
            return 0
        fi
    fi

    # Failed to acquire lock even after stale lock removal
    log_error "Failed to acquire installation lock"
    return 1
}

# Release lock
release_lock() {
    rm -rf "$LOCK_DIR"
}

# Cleanup on exit
cleanup_on_exit() {
    release_lock
}

# Set up trap for cleanup
setup_cleanup_trap() {
    trap cleanup_on_exit EXIT INT TERM
}

# PATH verification
INSTALL_BIN_DIR="${HOME}/.local/bin"

# Check if install directory is in PATH
check_path() {
    if [[ ":$PATH:" == *":$INSTALL_BIN_DIR:"* ]]; then
        return 0
    fi
    return 1
}

# Get PATH modification guidance
get_path_guidance() {
    local shell_name="$1"

    case "$shell_name" in
        bash)
            echo "Add to ~/.bashrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
        zsh)
            echo "Add to ~/.zshrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
            ;;
        fish)
            echo "Run: fish_add_path ~/.local/bin"
            ;;
        *)
            echo "Add ~/.local/bin to your PATH environment variable"
            ;;
    esac
}

# Create install directories
ensure_install_dirs() {
    mkdir -p "$INSTALL_BIN_DIR"
    mkdir -p "${HOME}/.local/share/claude-supervisor"
}

# Check for conflicting commands
check_no_conflict() {
    local command="$1"

    # Check if command exists and is not ours
    local existing
    existing=$(command -v "$command" 2>/dev/null)

    if [[ -n "$existing" && "$existing" != "$INSTALL_BIN_DIR/$command" ]]; then
        log_warning "Found existing $command at: $existing"
        log_warning "This may conflict with the installer"
        return 1
    fi

    return 0
}

# Confirm action with user
confirm() {
    local prompt="${1:-Continue?}"
    local default="${2:-N}"

    local yn
    if [[ "$default" == "Y" || "$default" == "y" ]]; then
        read -r -p "$prompt (Y/n): " yn
        yn="${yn:-Y}"
    else
        read -r -p "$prompt (y/N): " yn
        yn="${yn:-N}"
    fi

    case "$yn" in
        [Yy]* ) return 0;;
        * ) return 1;;
    esac
}

# Check disk space
# Arguments: directory, required_mb
check_disk_space() {
    local directory="$1"
    local required_mb="$2"

    # Get available space in MB
    local available_mb
    if [[ "$(uname)" == "Darwin" ]]; then
        available_mb=$(df -m "$directory" | awk 'NR==2 {print $4}')
    else
        available_mb=$(df -m "$directory" | awk 'NR==2 {print $4}')
    fi

    if [[ $available_mb -lt $required_mb ]]; then
        log_error "Insufficient disk space"
        log_info "Required: ${required_mb}MB, Available: ${available_mb}MB"
        return 1
    fi

    return 0
}

# Check if directory is writable
check_writable() {
    local directory="$1"

    if [[ -d "$directory" ]]; then
        if [[ -w "$directory" ]]; then
            return 0
        fi
    else
        # Directory doesn't exist, check parent
        local parent
        parent=$(dirname "$directory")
        if [[ -w "$parent" ]]; then
            return 0
        fi
    fi

    return 1
}

# Detect OS
detect_os() {
    local os
    os=$(uname -s)

    case "$os" in
        Darwin)
            echo "macos"
            ;;
        Linux)
            echo "linux"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Detect architecture
detect_arch() {
    local arch
    arch=$(uname -m)

    case "$arch" in
        x86_64|amd64)
            echo "x86_64"
            ;;
        arm64|aarch64)
            echo "arm64"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Check for required commands
check_required_commands() {
    local missing=()

    for cmd in curl tar; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required commands: ${missing[*]}"
        return 1
    fi

    return 0
}
