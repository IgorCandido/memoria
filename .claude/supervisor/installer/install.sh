#!/usr/bin/env bash
# Claude Supervisor Global Installer
# Requires: Bash 4.0+ (BR-024)
# Usage: curl -fsSL https://raw.githubusercontent.com/IgorCandido/claude-supervisor/main/installer/install.sh | bash
#
# This script:
# 1. Detects OS/architecture and validates environment
# 2. Checks Python 3.11+ is available
# 3. Downloads claude-supervisor-install to ~/.local/bin/
# 4. Sets up shell integration
# 5. Creates global configuration
#
# BR-001: Self-verification of downloaded script
# Expected SHA256: __INSTALLER_CHECKSUM__
# This checksum is replaced during release packaging

set -euo pipefail

# BR-014: Configuration constants
readonly MIN_DISK_SPACE_MB=50
readonly LOCK_TIMEOUT_SECONDS=600
readonly NETWORK_TIMEOUT_SECONDS=5

# BR-001: Self-verification function
verify_self() {
    # Only verify if we have shasum/sha256sum available
    if command -v shasum &>/dev/null || command -v sha256sum &>/dev/null; then
        local expected_checksum="__INSTALLER_CHECKSUM__"

        # Skip verification for development version (placeholder checksum)
        if [[ "$expected_checksum" == "__INSTALLER_CHECKSUM__" ]]; then
            return 0
        fi

        # Compute actual checksum of this script
        local actual_checksum
        if command -v shasum &>/dev/null; then
            actual_checksum=$(shasum -a 256 "$0" | awk '{print $1}')
        else
            actual_checksum=$(sha256sum "$0" | awk '{print $1}')
        fi

        # Verify match
        if [[ "$actual_checksum" != "$expected_checksum" ]]; then
            echo "ERROR: Installer checksum verification failed!" >&2
            echo "Expected: $expected_checksum" >&2
            echo "Got: $actual_checksum" >&2
            echo "" >&2
            echo "This could indicate:" >&2
            echo "  1. Downloaded script was corrupted during transfer" >&2
            echo "  2. Script was tampered with" >&2
            echo "  3. You're using an outdated URL" >&2
            echo "" >&2
            echo "For your security, installation has been aborted." >&2
            echo "Please download from: https://github.com/IgorCandido/claude-supervisor" >&2
            exit 1
        fi
    fi
}

# BR-001: Run self-verification before proceeding
verify_self

# Version of this installer
INSTALLER_VERSION="0.3.0"

# Installation directories
INSTALL_BIN_DIR="${HOME}/.local/bin"
INSTALL_SHARE_DIR="${HOME}/.local/share/claude-supervisor"

# GitHub repository
GITHUB_REPO="IgorCandido/claude-supervisor"
GITHUB_RAW_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/main"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*" >&2; }
log_error() { echo -e "${RED}Error:${NC} $*" >&2; }
log_step() { echo -e "${BLUE}→${NC} $*"; }

die() {
    log_error "$@"
    exit 1
}

# T014: Detect OS
detect_os() {
    local os
    os=$(uname -s)
    case "$os" in
        Darwin) echo "macos" ;;
        Linux) echo "linux" ;;
        *) echo "unknown" ;;
    esac
}

# T014: Detect architecture
detect_arch() {
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64|amd64) echo "x86_64" ;;
        arm64|aarch64) echo "arm64" ;;
        *) echo "unknown" ;;
    esac
}

# T014: Detect shell
detect_shell() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")
    case "$shell_name" in
        bash|zsh|fish) echo "$shell_name" ;;
        *) echo "bash" ;;  # Default to bash
    esac
}

# T015: Check Python version
check_python() {
    log_step "Checking Python version..."

    local python_cmd=""
    for cmd in python3 python3.13 python3.12 python3.11; do
        if command -v "$cmd" &> /dev/null; then
            python_cmd="$cmd"
            break
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        log_error "Python 3 not found"
        echo ""
        echo "Please install Python 3.11 or higher:"
        echo ""
        local os
        os=$(detect_os)
        if [[ "$os" == "macos" ]]; then
            echo "  brew install python@3.11"
        else
            echo "  sudo apt install python3.11  # Ubuntu/Debian"
            echo "  sudo dnf install python3.11  # Fedora"
        fi
        echo ""
        echo "  Or download from: https://www.python.org/downloads/"
        exit 1
    fi

    local version
    version=$("$python_cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    local major minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)

    if [[ $major -lt 3 ]] || [[ $major -eq 3 && $minor -lt 11 ]]; then
        log_error "Python 3.11+ required, found Python $version"
        echo ""
        echo "Please upgrade Python to version 3.11 or higher"
        exit 1
    fi

    log_info "Python $version found"
}

# T014: Validate environment
validate_environment() {
    log_step "Validating environment..."

    # Check not running as root
    if [[ $EUID -eq 0 ]]; then
        die "Do not run this installer as root. Install as regular user."
    fi

    # Check required commands
    for cmd in curl tar; do
        if ! command -v "$cmd" &> /dev/null; then
            die "Required command not found: $cmd"
        fi
    done

    # BR-014: Check disk space (need at least MIN_DISK_SPACE_MB)
    local available_mb
    if [[ "$(uname)" == "Darwin" ]]; then
        available_mb=$(df -m "$HOME" | awk 'NR==2 {print $4}')
    else
        available_mb=$(df -m "$HOME" | awk 'NR==2 {print $4}')
    fi

    if [[ $available_mb -lt $MIN_DISK_SPACE_MB ]]; then
        die "Insufficient disk space. Need at least ${MIN_DISK_SPACE_MB}MB, have ${available_mb}MB"
    fi

    log_info "Environment validated"
}

# T016: Download claude-supervisor-install
download_installer() {
    log_step "Downloading claude-supervisor-install..."

    # Create directories
    mkdir -p "$INSTALL_BIN_DIR"
    mkdir -p "$INSTALL_SHARE_DIR"

    local installer_url="${GITHUB_RAW_URL}/installer/claude-supervisor-install.sh"
    local installer_path="$INSTALL_BIN_DIR/claude-supervisor-install"

    # Check for existing installation
    if [[ -f "$installer_path" ]]; then
        log_warning "Found existing installation"
        local backup_path="${installer_path}.backup-$(date +%Y%m%d-%H%M%S)"
        cp "$installer_path" "$backup_path"
        log_info "Backed up to: $backup_path"
    fi

    # Download
    # TODO: When repo goes public, change back to curl:
    # if ! curl --silent --fail --location --output "$installer_path" "$installer_url"; then
    # For private repo, use gh api with authentication
    if ! gh api "repos/${GITHUB_REPO}/contents/installer/claude-supervisor-install.sh" --jq '.content' | base64 -d > "$installer_path"; then
        die "Failed to download installer from GitHub (requires gh CLI authentication)"
    fi

    # Make executable
    chmod +x "$installer_path"

    log_info "Downloaded to: $installer_path"

    # Download lib directory
    log_step "Downloading library files..."
    local lib_dir="$INSTALL_SHARE_DIR/lib"
    mkdir -p "$lib_dir"

    local lib_files=(
        "common.sh"
        "download.sh"
        "plugin-setup.sh"
        "python-check.sh"
        "shell-detect.sh"
        "version.sh"
    )

    for lib_file in "${lib_files[@]}"; do
        # TODO: When repo goes public, change back to curl
        # For private repo, use gh api with authentication
        if ! gh api "repos/${GITHUB_REPO}/contents/installer/lib/${lib_file}" --jq '.content' | base64 -d > "$lib_dir/$lib_file"; then
            die "Failed to download library file: $lib_file"
        fi
        chmod +x "$lib_dir/$lib_file"
    done

    log_info "Downloaded library files to: $lib_dir"

    # Download templates directory
    log_step "Downloading template files..."
    local templates_dir="$INSTALL_SHARE_DIR/templates"
    mkdir -p "$templates_dir"

    local template_files=(
        "shell-function.bash"
        "shell-function.fish"
    )

    for template_file in "${template_files[@]}"; do
        # TODO: When repo goes public, change back to curl
        if ! gh api "repos/${GITHUB_REPO}/contents/installer/templates/${template_file}" --jq '.content' | base64 -d > "$templates_dir/$template_file"; then
            die "Failed to download template file: $template_file"
        fi
    done

    log_info "Downloaded template files to: $templates_dir"

    # Download VERSION file
    if ! gh api "repos/${GITHUB_REPO}/contents/installer/VERSION" --jq '.content' | base64 -d > "$INSTALL_SHARE_DIR/VERSION"; then
        log_warning "Failed to download VERSION file (non-critical)"
    fi
}

# T017: Generate shell-init.sh
generate_shell_init() {
    log_step "Generating shell integration..."

    local shell_init="$INSTALL_SHARE_DIR/shell-init.sh"
    local shell_name
    shell_name=$(detect_shell)

    # Write shell function based on detected shell
    if [[ "$shell_name" == "fish" ]]; then
        cat > "$shell_init" << 'EOF'
# Claude Supervisor shell integration (fish)
function claude-supervisor --description "Execute Claude Supervisor in current project"
    if not test -d ".claude"
        echo "Error: No .claude/ directory found in current directory" >&2
        echo "Run 'claude-supervisor-install init .' to initialize this project" >&2
        return 1
    end

    set -l supervisor_path ".claude/supervisor/claude_supervisor.py"
    if not test -f "$supervisor_path"
        echo "Error: Supervisor not found in .claude/supervisor/" >&2
        echo "Try running: claude-supervisor-install init ." >&2
        return 1
    end

    python3 $supervisor_path $argv
end
EOF
    else
        # Bash/Zsh compatible
        cat > "$shell_init" << 'EOF'
# Claude Supervisor shell integration
claude-supervisor() {
    if [[ ! -d ".claude" ]]; then
        echo "Error: No .claude/ directory found in current directory" >&2
        echo "Run 'claude-supervisor-install init .' to initialize this project" >&2
        return 1
    fi

    local supervisor_path=".claude/supervisor/claude_supervisor.py"
    if [[ ! -f "$supervisor_path" ]]; then
        echo "Error: Supervisor not found in .claude/supervisor/" >&2
        echo "Try running: claude-supervisor-install init ." >&2
        return 1
    fi

    python3 "$supervisor_path" "$@"
}
EOF
    fi

    # BR-011: Validate fish shell function syntax
    if [[ "$shell_name" == "fish" ]] && command -v fish &>/dev/null; then
        log_step "Validating Fish shell syntax..."
        if fish --no-execute "$shell_init" 2>/dev/null; then
            log_info "Fish syntax validation passed"
        else
            log_warning "Fish syntax validation failed - function may have errors"
        fi
    fi

    log_info "Generated: $shell_init"
}

# T18: Update shell configuration
update_shell_config() {
    log_step "Updating shell configuration..."

    local shell_name
    shell_name=$(detect_shell)
    local source_line="source \"$INSTALL_SHARE_DIR/shell-init.sh\""
    local config_file=""

    case "$shell_name" in
        bash)
            for cfg in "$HOME/.bashrc" "$HOME/.bash_profile"; do
                if [[ -f "$cfg" ]]; then
                    config_file="$cfg"
                    break
                fi
            done
            config_file="${config_file:-$HOME/.bashrc}"
            ;;
        zsh)
            config_file="$HOME/.zshrc"
            ;;
        fish)
            config_file="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
            source_line="source \"$INSTALL_SHARE_DIR/shell-init.sh\""
            mkdir -p "$(dirname "$config_file")"
            ;;
    esac

    # Check if already present
    if grep -qF "claude-supervisor/shell-init.sh" "$config_file" 2>/dev/null; then
        log_info "Shell configuration already updated: $config_file"
        return 0
    fi

    # Add source line
    {
        echo ""
        echo "# Claude Supervisor shell integration"
        echo "$source_line"
    } >> "$config_file"

    log_info "Updated: $config_file"
}

# T19: Check PATH
verify_path() {
    log_step "Verifying PATH..."

    if [[ ":$PATH:" == *":$INSTALL_BIN_DIR:"* ]]; then
        log_info "PATH includes $INSTALL_BIN_DIR"
        return 0
    fi

    log_warning "$INSTALL_BIN_DIR is not in PATH"
    echo ""
    echo "Add to your shell configuration:"
    local shell_name
    shell_name=$(detect_shell)
    case "$shell_name" in
        bash) echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc" ;;
        zsh) echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc" ;;
        fish) echo "  fish_add_path ~/.local/bin" ;;
    esac
    echo ""
}

# T20: Create global config.json
create_global_config() {
    log_step "Creating configuration..."

    local config_file="$INSTALL_SHARE_DIR/config.json"
    local install_date
    install_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    cat > "$config_file" << EOF
{
    "installer_version": "$INSTALLER_VERSION",
    "install_date": "$install_date",
    "install_path": "$INSTALL_BIN_DIR/claude-supervisor-install",
    "projects": []
}
EOF

    log_info "Created: $config_file"
}

# Main installation flow
main() {
    echo ""
    echo "Installing claude-supervisor-install..."
    echo ""

    # Detect environment
    local os arch shell_name
    os=$(detect_os)
    arch=$(detect_arch)
    shell_name=$(detect_shell)

    log_info "Detected: $os ($arch), $shell_name shell"

    # Validate OS
    if [[ "$os" == "unknown" ]]; then
        die "Unsupported operating system. Only macOS and Linux are supported."
    fi

    # Run installation steps
    validate_environment      # T014
    check_python             # T015
    download_installer       # T016
    generate_shell_init      # T017
    update_shell_config      # T018
    verify_path              # T019
    create_global_config     # T020

    # Success message
    echo ""
    echo "════════════════════════════════════════════════════════════"
    log_info "Installation successful!"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "Next steps:"
    echo "  1. Restart your shell or run: source ~/.${shell_name}rc"
    echo "  2. Initialize a project: cd your-project && claude-supervisor-install init ."
    echo "  3. Run supervisor: claude-supervisor -p \"Your prompt\""
    echo ""
    echo "For help: claude-supervisor-install --help"
    echo "Documentation: https://github.com/${GITHUB_REPO}"
    echo ""
}

# Run main
main "$@"
