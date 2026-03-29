#!/usr/bin/env bash
# install.sh — Stage 1 Bootstrap for Memoria
# Validates prerequisites, downloads Stage 2 installer, runs it.
# Usage: curl -fsSL <url> | bash
#   or:  bash installer/install.sh

set -euo pipefail

# Constants
INSTALL_DIR="${MEMORIA_INSTALL_DIR:-${HOME}/.local/share/memoria}"
GITHUB_REPO="IgorCandido/memoria"
MEMORIA_BRANCH="${MEMORIA_BRANCH:-main}"

# Colors (disabled if not a terminal)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' BOLD='' NC=''
fi

log_info()    { echo -e "${CYAN}ℹ${NC}  $*"; }
log_error()   { echo -e "${RED}✗${NC}  $*" >&2; }
log_step()    { echo -e "${CYAN}→${NC}  ${BOLD}$*${NC}"; }
log_success() { echo -e "${GREEN}✓${NC}  $*"; }

die() { log_error "$@"; exit 1; }

# ─── Banner ───────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  Memoria Installer${NC}"
echo -e "  RAG-powered knowledge system for Claude Code"
echo ""

# ─── Step 1: Validate prerequisites ──────────────────────────────────
log_step "Checking prerequisites..."

# Check gh CLI
if ! command -v gh &>/dev/null; then
    die "GitHub CLI (gh) is required but not installed.
  Install: https://cli.github.com/
  macOS:   brew install gh
  Linux:   See https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
fi

# Check gh authentication
if ! gh auth status &>/dev/null; then
    die "GitHub CLI is not authenticated. Run: gh auth login"
fi

# Check repo access
if ! gh api "repos/${GITHUB_REPO}" --jq '.name' &>/dev/null; then
    die "Cannot access ${GITHUB_REPO}. Ensure gh is authenticated with repo access."
fi
log_success "GitHub CLI authenticated with repo access"

# Check Python 3.11+
PYTHON_CMD=""
for candidate in python3 python3.13 python3.12 python3.11 python; do
    if command -v "$candidate" &>/dev/null; then
        version="$("$candidate" --version 2>&1 | awk '{print $2}')"
        major="$(echo "$version" | cut -d. -f1)"
        minor="$(echo "$version" | cut -d. -f2)"
        if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
            PYTHON_CMD="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    die "Python 3.11+ is required but not found.
  macOS:   brew install python@3.13
  Linux:   sudo apt install python3.11
  Manual:  https://www.python.org/downloads/"
fi
log_success "Python $(${PYTHON_CMD} --version 2>&1 | awk '{print $2}') found"

# Check Docker
if ! command -v docker &>/dev/null; then
    log_info "Docker not found — ChromaDB setup will be skipped"
    log_info "Install Docker and re-run installer to set up ChromaDB"
    DOCKER_AVAILABLE=false
else
    if docker info &>/dev/null; then
        log_success "Docker is running"
        DOCKER_AVAILABLE=true
    else
        log_info "Docker found but not running — ChromaDB setup will be skipped"
        DOCKER_AVAILABLE=false
    fi
fi

# ─── Step 2: Download Stage 2 installer and libraries ────────────────
log_step "Setting up installation directory..."
mkdir -p "$INSTALL_DIR/lib"

# If running from source checkout, copy files directly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || SCRIPT_DIR=""

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/memoria-install.sh" ]]; then
    log_info "Running from source checkout"
    INSTALLER="$SCRIPT_DIR/memoria-install.sh"
else
    log_step "Downloading installer from GitHub..."

    # Download Stage 2 installer
    gh api "repos/${GITHUB_REPO}/contents/installer/memoria-install.sh?ref=${MEMORIA_BRANCH}" \
        --jq '.content' | base64 --decode > "$INSTALL_DIR/memoria-install.sh" \
        || die "Failed to download Stage 2 installer"
    chmod +x "$INSTALL_DIR/memoria-install.sh"

    # Download shell libraries
    for lib in common.sh version.sh python-check.sh shell-detect.sh download.sh docker-setup.sh; do
        gh api "repos/${GITHUB_REPO}/contents/installer/lib/${lib}?ref=${MEMORIA_BRANCH}" \
            --jq '.content' | base64 --decode > "$INSTALL_DIR/lib/${lib}" \
            || die "Failed to download library: $lib"
    done

    INSTALLER="$INSTALL_DIR/memoria-install.sh"
fi

# ─── Step 3: Run Stage 2 installer ───────────────────────────────────
log_step "Running installer..."
export MEMORIA_INSTALL_DIR="$INSTALL_DIR"
export MEMORIA_PYTHON_CMD="$PYTHON_CMD"
export MEMORIA_DOCKER_AVAILABLE="${DOCKER_AVAILABLE}"
export MEMORIA_SOURCE_DIR="$SCRIPT_DIR"

bash "$INSTALLER" install "$@"

exit_code=$?
if [[ "$exit_code" -eq 0 ]]; then
    echo ""
    log_success "Memoria installed successfully!"
    echo ""
    echo "  To get started:"
    echo "    1. Restart your shell or run: source ~/.local/share/memoria/shell-init.sh"
    echo "    2. Try: memoria health"
    echo "    3. Use search_knowledge() from Claude Code"
    echo ""
else
    exit "$exit_code"
fi
