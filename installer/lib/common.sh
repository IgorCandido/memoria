#!/usr/bin/env bash
# common.sh — Shared utilities for memoria installer
# Logging, error handling, OS detection, prerequisite checks

set -euo pipefail

# Colors (disabled if not a terminal)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' DIM='' NC=''
fi

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ${NC}  $*"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC}  $*" >&2
}

log_error() {
    echo -e "${RED}✗${NC}  $*" >&2
}

log_step() {
    echo -e "${CYAN}→${NC}  ${BOLD}$*${NC}"
}

log_success() {
    echo -e "${GREEN}✓${NC}  $*"
}

# Exit with error message
die() {
    log_error "$@"
    exit 1
}

# OS and architecture detection
detect_os() {
    local os
    os="$(uname -s)"
    case "$os" in
        Darwin) echo "macos" ;;
        Linux)  echo "linux" ;;
        *)      echo "unknown" ;;
    esac
}

detect_arch() {
    local arch
    arch="$(uname -m)"
    case "$arch" in
        x86_64|amd64) echo "x86_64" ;;
        arm64|aarch64) echo "arm64" ;;
        *)             echo "$arch" ;;
    esac
}

# Disk space check (in MB)
check_disk_space() {
    local path="${1:-.}"
    local required_mb="${2:-500}"
    local available_mb

    if [[ "$(detect_os)" == "macos" ]]; then
        available_mb=$(df -m "$path" | awk 'NR==2 {print $4}')
    else
        available_mb=$(df -m "$path" | awk 'NR==2 {print $4}')
    fi

    if [[ "$available_mb" -lt "$required_mb" ]]; then
        log_error "Insufficient disk space: ${available_mb}MB available, ${required_mb}MB required"
        return 1
    fi
    return 0
}

# Check if a command exists
require_command() {
    local cmd="$1"
    local install_hint="${2:-}"
    if ! command -v "$cmd" &>/dev/null; then
        if [[ -n "$install_hint" ]]; then
            die "'$cmd' is required but not found. $install_hint"
        else
            die "'$cmd' is required but not found."
        fi
    fi
}

# Lock file mechanism (atomic mkdir-based)
LOCK_DIR=""
LOCK_STALE_MINUTES=10

acquire_lock() {
    local lock_path="$1"
    LOCK_DIR="$lock_path"

    # Check for stale lock
    if [[ -d "$lock_path" ]]; then
        local lock_age
        if [[ "$(detect_os)" == "macos" ]]; then
            lock_age=$(( ( $(date +%s) - $(stat -f %m "$lock_path") ) / 60 ))
        else
            lock_age=$(( ( $(date +%s) - $(stat -c %Y "$lock_path") ) / 60 ))
        fi

        if [[ "$lock_age" -ge "$LOCK_STALE_MINUTES" ]]; then
            log_warning "Removing stale lock (${lock_age} minutes old): $lock_path"
            rmdir "$lock_path" 2>/dev/null || true
        fi
    fi

    if ! mkdir "$lock_path" 2>/dev/null; then
        die "Another memoria operation is in progress. If this is incorrect, remove: $lock_path"
    fi

    # Cleanup on exit
    trap 'release_lock' EXIT
}

release_lock() {
    if [[ -n "$LOCK_DIR" && -d "$LOCK_DIR" ]]; then
        rmdir "$LOCK_DIR" 2>/dev/null || true
        LOCK_DIR=""
    fi
}

# Path safety validation
validate_path() {
    local path="$1"

    # Reject path traversal
    if [[ "$path" == *".."* ]]; then
        die "Path traversal detected in: $path"
    fi

    # Block sensitive system directories
    case "$path" in
        /etc/*|/System/*|/root/*|/usr/*|/bin/*|/sbin/*)
            die "Cannot operate in system directory: $path"
            ;;
    esac

    return 0
}
