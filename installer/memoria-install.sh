#!/usr/bin/env bash
# memoria-install.sh — Stage 2: Full Memoria Installer
# Handles install, update, and uninstall operations
# Called by install.sh (Stage 1) or directly for updates

set -euo pipefail

# ─── Paths ────────────────────────────────────────────────────────────
INSTALL_DIR="${MEMORIA_INSTALL_DIR:-${HOME}/.local/share/memoria}"
REPO_DIR="${INSTALL_DIR}/repo"
VENV_DIR="${INSTALL_DIR}/.venv"
SKILL_LINK="${HOME}/.claude/skills/memoria"
CONFIG_FILE="${INSTALL_DIR}/config.json"
SHELL_INIT="${INSTALL_DIR}/shell-init.sh"
LOCK_PATH="${INSTALL_DIR}/.install-lock"
GITHUB_REPO="IgorCandido/memoria"
MEMORIA_BRANCH="${MEMORIA_BRANCH:-main}"

# ─── Source libraries ─────────────────────────────────────────────────
# Try source dir first (running from checkout), then install dir
LIB_DIR=""
SOURCE_DIR="${MEMORIA_SOURCE_DIR:-}"
if [[ -n "$SOURCE_DIR" && -f "$SOURCE_DIR/lib/common.sh" ]]; then
    LIB_DIR="$SOURCE_DIR/lib"
elif [[ -f "$INSTALL_DIR/lib/common.sh" ]]; then
    LIB_DIR="$INSTALL_DIR/lib"
elif [[ -f "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh" ]]; then
    LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" && pwd)"
fi

if [[ -z "$LIB_DIR" ]]; then
    echo "ERROR: Cannot find shell libraries" >&2
    exit 1
fi

source "$LIB_DIR/common.sh"
source "$LIB_DIR/version.sh"
source "$LIB_DIR/python-check.sh"
source "$LIB_DIR/shell-detect.sh"
source "$LIB_DIR/download.sh"
source "$LIB_DIR/docker-setup.sh"

# ─── Detect Python ───────────────────────────────────────────────────
PYTHON_CMD="${MEMORIA_PYTHON_CMD:-}"
if [[ -z "$PYTHON_CMD" ]]; then
    PYTHON_CMD="$(find_python)" || die "Python 3.11+ not found. $(get_python_install_instructions)"
fi

# ─── Commands ─────────────────────────────────────────────────────────

cmd_install() {
    local target_version="${1:-}"

    # Validate install path for security
    validate_path "$INSTALL_DIR"

    log_step "Installing Memoria..."

    # Check for existing installation
    if [[ -f "$CONFIG_FILE" ]]; then
        local current
        current=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('version','unknown'))" 2>/dev/null || echo "unknown")
        log_warning "Existing installation detected (v${current})"
        log_info "Re-installing..."

        # Backup existing installation
        if [[ -d "$REPO_DIR" ]]; then
            local backup_dir="${INSTALL_DIR}/backups/v${current}-$(date +%Y%m%d%H%M%S)"
            mkdir -p "$backup_dir"
            cp -r "$REPO_DIR" "$backup_dir/repo"
            log_info "Backed up existing installation to $backup_dir"
        fi
    fi

    # Acquire installation lock
    mkdir -p "$INSTALL_DIR"
    acquire_lock "$LOCK_PATH"

    # Step 1: Clone repository
    log_step "Cloning repository..."
    if [[ -d "$REPO_DIR/.git" ]] || [[ -f "$REPO_DIR/.git" ]]; then
        log_info "Repository already exists, pulling latest..."
        (cd "$REPO_DIR" && git pull origin "$MEMORIA_BRANCH" --ff-only 2>/dev/null) \
            || { rm -rf "$REPO_DIR"; _clone_repo; }
    else
        _clone_repo
    fi

    # Step 2: Create Python venv and install dependencies
    log_step "Setting up Python environment..."
    if [[ ! -d "$VENV_DIR" ]]; then
        "$PYTHON_CMD" -m venv "$VENV_DIR" || die "Failed to create Python virtual environment"
    fi

    "$VENV_DIR/bin/pip" install --quiet --upgrade pip 2>/dev/null || true
    "$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR" \
        || die "Failed to install Python dependencies"
    log_success "Python environment ready"

    # Step 3: Start ChromaDB Docker container
    local docker_available="${MEMORIA_DOCKER_AVAILABLE:-true}"
    if [[ "$docker_available" == "true" ]] && check_docker_running; then
        log_step "Setting up ChromaDB..."
        local data_dir="${INSTALL_DIR}/chroma_data"
        start_chromadb_container "$data_dir" \
            || { log_warning "Failed to start ChromaDB container (exit code: $?)"; }

        if wait_for_chromadb_healthy 30; then
            log_success "ChromaDB is running on port ${CHROMADB_HOST_PORT}"
        else
            log_warning "ChromaDB failed to become healthy within 30s"
            log_info "You can start it manually: docker start memoria-chromadb"
        fi
    else
        log_info "Docker not available — skipping ChromaDB setup"
        log_info "Start Docker and run: docker start memoria-chromadb"
    fi

    # Step 4: Register skill symlink
    log_step "Registering Claude Code skill..."
    mkdir -p "$(dirname "$SKILL_LINK")"
    if [[ -L "$SKILL_LINK" ]]; then
        rm "$SKILL_LINK"
    elif [[ -e "$SKILL_LINK" ]]; then
        log_warning "Skill path exists but is not a symlink: $SKILL_LINK"
        log_info "Backing up and replacing..."
        mv "$SKILL_LINK" "${SKILL_LINK}.bak.$(date +%s)"
    fi
    ln -sf "$REPO_DIR" "$SKILL_LINK"
    log_success "Skill registered at $SKILL_LINK"

    # Step 5: Health check
    log_step "Running health check..."
    local health_ok=true
    if [[ -f "$REPO_DIR/memoria/skill_helpers.py" ]]; then
        if "$VENV_DIR/bin/python3" -c "from memoria.skill_helpers import search_knowledge; print('OK')" 2>/dev/null; then
            log_success "Memoria Python module importable"
        else
            log_warning "Memoria Python module import failed"
            health_ok=false
        fi
    else
        log_warning "skill_helpers.py not found in repo"
        health_ok=false
    fi

    # Step 6: Write config.json
    log_step "Writing configuration..."
    local git_commit=""
    if [[ -d "$REPO_DIR/.git" ]] || [[ -f "$REPO_DIR/.git" ]]; then
        git_commit=$(cd "$REPO_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")
    fi

    local installed_version
    if [[ -f "$REPO_DIR/VERSION" ]]; then
        installed_version=$(tr -d '[:space:]' < "$REPO_DIR/VERSION")
    else
        installed_version="${target_version:-0.0.0}"
    fi

    $PYTHON_CMD -c "
import json
from datetime import datetime, timezone

config = {
    'version': '$installed_version',
    'install_date': datetime.now(timezone.utc).isoformat(),
    'install_path': '$INSTALL_DIR',
    'repo_path': '$REPO_DIR',
    'venv_path': '$VENV_DIR',
    'installer_version': '1.0.0',
    'python_version': '$($PYTHON_CMD --version 2>&1 | awk \"{print \\$2}\")',
    'install_method': 'clone',
    'git_commit': '$git_commit'
}

with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
"
    log_success "Configuration written to $CONFIG_FILE"

    # Step 7: Shell integration
    log_step "Setting up shell integration..."
    _create_shell_init
    local user_shell
    user_shell="$(detect_shell)"
    local rc_file
    rc_file="$(get_shell_config_file "$user_shell")"

    if validate_source_line "$SHELL_INIT"; then
        add_source_line "$rc_file" "$SHELL_INIT"
        log_success "Shell integration added to $rc_file"
    else
        log_warning "Skipping shell integration — path validation failed"
    fi

    # Copy libraries to install dir for runtime use
    if [[ "$LIB_DIR" != "$INSTALL_DIR/lib" ]]; then
        mkdir -p "$INSTALL_DIR/lib"
        cp "$LIB_DIR"/*.sh "$INSTALL_DIR/lib/" 2>/dev/null || true
    fi

    # Copy Stage 2 installer for runtime updates
    local this_script="${BASH_SOURCE[0]}"
    if [[ -f "$this_script" && "$this_script" != "$INSTALL_DIR/memoria-install.sh" ]]; then
        cp "$this_script" "$INSTALL_DIR/memoria-install.sh"
        chmod +x "$INSTALL_DIR/memoria-install.sh"
    fi

    release_lock

    echo ""
    log_success "Memoria v${installed_version} installed successfully!"
    return 0
}

cmd_update() {
    local target_version="${1:-}"

    if [[ ! -f "$CONFIG_FILE" ]]; then
        die "Memoria is not installed. Run installer first."
    fi

    log_step "Updating Memoria..."

    # Read current version
    local current_version
    current_version=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('version','unknown'))" 2>/dev/null)

    if [[ -z "$target_version" ]]; then
        # Get latest from GitHub
        target_version=$(get_latest_version) || die "Failed to get latest version from GitHub"
    fi

    # Check if update needed
    if [[ "$current_version" == "$target_version" ]]; then
        log_success "Already up to date (v${current_version})"
        return 0
    fi

    log_info "Updating from v${current_version} to v${target_version}"

    # Acquire lock
    acquire_lock "$LOCK_PATH"

    # Backup current installation
    local backup_dir="${INSTALL_DIR}/backups/v${current_version}-$(date +%Y%m%d%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r "$REPO_DIR" "$backup_dir/repo"
    log_info "Backed up to $backup_dir"

    # Write backup manifest
    $PYTHON_CMD -c "
import json
from datetime import datetime, timezone

manifest = {
    'version': '$current_version',
    'backup_date': datetime.now(timezone.utc).isoformat(),
    'backup_path': '$backup_dir',
    'reason': 'pre-update',
    'files_count': 0
}

with open('$backup_dir/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

    # Try to download and install update
    local update_success=true

    # Check if there's a release tarball available
    local tarball_path
    tarball_path=$(mktemp -d)/memoria-${target_version}.tar.gz

    if gh release download "v${target_version}" \
        --repo "$GITHUB_REPO" \
        --pattern "memoria-${target_version}.tar.gz" \
        --output "$tarball_path" 2>/dev/null; then

        # Verify checksum if checksums.txt available
        local checksums_path
        checksums_path=$(mktemp)
        if gh release download "v${target_version}" \
            --repo "$GITHUB_REPO" \
            --pattern "checksums.txt" \
            --output "$checksums_path" 2>/dev/null; then

            local expected_hash
            expected_hash=$(grep "memoria-${target_version}.tar.gz" "$checksums_path" | awk '{print $1}')
            if [[ -n "$expected_hash" ]]; then
                if ! verify_checksum "$tarball_path" "$expected_hash"; then
                    log_error "Checksum verification failed!"
                    update_success=false
                fi
            fi
        fi

        if [[ "$update_success" == "true" ]]; then
            # Extract tarball
            rm -rf "${REPO_DIR}.new"
            mkdir -p "${REPO_DIR}.new"
            tar xzf "$tarball_path" -C "${REPO_DIR}.new" --strip-components=0 2>/dev/null \
                || { log_error "Failed to extract tarball"; update_success=false; }

            if [[ "$update_success" == "true" ]]; then
                rm -rf "$REPO_DIR"
                mv "${REPO_DIR}.new" "$REPO_DIR"
            fi
        fi

        rm -f "$tarball_path" "$checksums_path" 2>/dev/null
    else
        # No release tarball — use git pull
        log_info "No release tarball found, using git pull..."
        if [[ -d "$REPO_DIR/.git" ]] || [[ -f "$REPO_DIR/.git" ]]; then
            (cd "$REPO_DIR" && git fetch origin && git checkout "v${target_version}" 2>/dev/null) \
                || (cd "$REPO_DIR" && git pull origin "$MEMORIA_BRANCH" --ff-only 2>/dev/null) \
                || { log_error "Git update failed"; update_success=false; }
        else
            _clone_repo || { log_error "Clone failed"; update_success=false; }
        fi
    fi

    # Update pip dependencies
    if [[ "$update_success" == "true" ]]; then
        log_step "Updating Python dependencies..."
        "$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR" \
            || { log_warning "pip install failed"; update_success=false; }
    fi

    # Health check
    if [[ "$update_success" == "true" ]]; then
        log_step "Running health check..."
        if "$VENV_DIR/bin/python3" -c "from memoria.skill_helpers import search_knowledge; print('OK')" 2>/dev/null; then
            log_success "Health check passed"
        else
            log_error "Health check failed after update"
            update_success=false
        fi
    fi

    # Rollback if needed
    if [[ "$update_success" != "true" ]]; then
        log_error "Update failed — rolling back..."
        rm -rf "$REPO_DIR"
        cp -r "$backup_dir/repo" "$REPO_DIR"
        "$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR" 2>/dev/null || true
        release_lock
        die "Update failed. Rolled back to v${current_version}."
    fi

    # Update config
    local new_version
    if [[ -f "$REPO_DIR/VERSION" ]]; then
        new_version=$(tr -d '[:space:]' < "$REPO_DIR/VERSION")
    else
        new_version="$target_version"
    fi

    local git_commit=""
    if [[ -d "$REPO_DIR/.git" ]] || [[ -f "$REPO_DIR/.git" ]]; then
        git_commit=$(cd "$REPO_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")
    fi

    $PYTHON_CMD -c "
import json
from datetime import datetime, timezone

config = json.load(open('$CONFIG_FILE'))
config['version'] = '$new_version'
config['install_date'] = datetime.now(timezone.utc).isoformat()
config['git_commit'] = '$git_commit'

with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
"

    release_lock
    log_success "Updated from v${current_version} to v${new_version}"
    return 0
}

cmd_uninstall() {
    local force="${1:-false}"

    if [[ ! -d "$INSTALL_DIR" ]] && [[ ! -L "$SKILL_LINK" ]]; then
        log_info "Memoria is not installed."
        return 0
    fi

    # Confirmation prompt
    if [[ "$force" != "true" ]]; then
        echo ""
        log_warning "This will remove Memoria and all its data."
        read -rp "Are you sure? [y/N] " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            log_info "Uninstall cancelled."
            return 0
        fi
    fi

    # Prompt about ChromaDB
    if check_docker_running && check_container_exists; then
        local remove_container=false
        if [[ "$force" != "true" ]]; then
            read -rp "Stop and remove ChromaDB container and data? [y/N] " confirm_docker
            if [[ "$confirm_docker" == "y" || "$confirm_docker" == "Y" ]]; then
                remove_container=true
            fi
        else
            remove_container=true
        fi

        if [[ "$remove_container" == "true" ]]; then
            log_step "Removing ChromaDB container..."
            remove_chromadb_container
            log_success "ChromaDB container removed"
        else
            log_info "Keeping ChromaDB container"
        fi
    fi

    # Remove skill symlink
    if [[ -L "$SKILL_LINK" ]]; then
        log_step "Removing skill symlink..."
        rm "$SKILL_LINK"
        log_success "Skill symlink removed"
    fi

    # Remove shell integration
    log_step "Removing shell integration..."
    for shell_name in bash zsh; do
        local rc_file
        rc_file="$(get_shell_config_file "$shell_name")"
        remove_source_line "$rc_file"
    done
    log_success "Shell integration removed"

    # Remove installation directory
    if [[ -d "$INSTALL_DIR" ]]; then
        log_step "Removing installation directory..."
        rm -rf "$INSTALL_DIR"
        log_success "Installation directory removed"
    fi

    echo ""
    log_success "Memoria uninstalled successfully"
    return 0
}

cmd_health() {
    echo ""
    echo -e "${BOLD}Memoria Health Check${NC}"
    echo "===================="

    # Installation
    if [[ -f "$CONFIG_FILE" ]]; then
        local version
        version=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('version','unknown'))" 2>/dev/null)
        log_success "Installed: v${version}"
    else
        log_error "Not installed (no config.json)"
        return 1
    fi

    # Python venv
    if [[ -f "$VENV_DIR/bin/python3" ]]; then
        log_success "Python venv: OK"
    else
        log_error "Python venv: Missing"
    fi

    # Skill symlink
    if [[ -L "$SKILL_LINK" ]] && [[ -d "$SKILL_LINK" ]]; then
        log_success "Skill symlink: OK"
    else
        log_error "Skill symlink: Missing or broken"
    fi

    # ChromaDB
    if check_docker_running; then
        if check_container_running; then
            if wait_for_chromadb_healthy 5; then
                log_success "ChromaDB: Running and healthy"
            else
                log_warning "ChromaDB: Running but not responding"
            fi
        else
            log_warning "ChromaDB: Container not running"
        fi
    else
        log_warning "ChromaDB: Docker not available"
    fi

    # Python module
    if "$VENV_DIR/bin/python3" -c "from memoria.skill_helpers import search_knowledge; print('OK')" 2>/dev/null; then
        log_success "Python module: Importable"
    else
        log_warning "Python module: Import failed"
    fi

    echo ""
}

cmd_version() {
    if [[ -f "$CONFIG_FILE" ]]; then
        local version git_commit install_date
        version=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('version','unknown'))" 2>/dev/null)
        git_commit=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('git_commit','unknown')[:7])" 2>/dev/null)
        install_date=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('install_date','unknown')[:10])" 2>/dev/null)
        echo "memoria v${version} (commit ${git_commit}, installed ${install_date})"
    else
        echo "memoria: not installed"
        return 1
    fi
}

cmd_check() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        die "Memoria is not installed."
    fi

    local current_version
    current_version=$($PYTHON_CMD -c "import json; print(json.load(open('$CONFIG_FILE')).get('version','unknown'))" 2>/dev/null)
    echo "Current version: v${current_version}"

    log_step "Checking for updates..."
    local latest_version
    latest_version=$(get_latest_version 2>/dev/null) || {
        log_warning "Could not check for updates (network error)"
        return 0
    }

    echo "Latest version:  v${latest_version}"

    compare_versions "$latest_version" "$current_version"
    local cmp=$?
    if [[ "$cmp" -eq 1 ]]; then
        log_info "Update available! Run: memoria update"
    else
        log_success "You are up to date"
    fi
}

# ─── Internal helpers ─────────────────────────────────────────────────

_clone_repo() {
    rm -rf "$REPO_DIR"
    gh repo clone "$GITHUB_REPO" "$REPO_DIR" -- -b "$MEMORIA_BRANCH" --single-branch \
        || die "Failed to clone repository"
    log_success "Repository cloned"
}

_create_shell_init() {
    cat > "$SHELL_INIT" << 'SHELLINIT'
#!/usr/bin/env bash
# memoria shell integration — sourced from shell RC file
# Provides the `memoria` command

MEMORIA_DIR="${HOME}/.local/share/memoria"

memoria() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    case "$cmd" in
        update)
            local version=""
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --version) version="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            bash "$MEMORIA_DIR/memoria-install.sh" update "$version"
            ;;
        check)
            bash "$MEMORIA_DIR/memoria-install.sh" check
            ;;
        health)
            bash "$MEMORIA_DIR/memoria-install.sh" health
            ;;
        version)
            bash "$MEMORIA_DIR/memoria-install.sh" version
            ;;
        uninstall)
            local yes_flag="false"
            [[ "${1:-}" == "--yes" ]] && yes_flag="true"
            bash "$MEMORIA_DIR/memoria-install.sh" uninstall "$yes_flag"
            ;;
        help|*)
            echo "Usage: memoria <command>"
            echo ""
            echo "Commands:"
            echo "  update [--version X.Y.Z]  Update to latest (or specific) version"
            echo "  check                     Check for available updates"
            echo "  health                    Run system health check"
            echo "  version                   Show installed version"
            echo "  uninstall [--yes]         Remove memoria installation"
            echo "  help                      Show this help"
            ;;
    esac
}
SHELLINIT
}

# ─── Main dispatch ────────────────────────────────────────────────────

main() {
    local command="${1:-help}"
    shift 2>/dev/null || true

    case "$command" in
        install)
            cmd_install "$@"
            ;;
        update)
            cmd_update "$@"
            ;;
        uninstall)
            local force="${1:-false}"
            cmd_uninstall "$force"
            ;;
        health)
            cmd_health
            ;;
        version)
            cmd_version
            ;;
        check)
            cmd_check
            ;;
        *)
            echo "Usage: memoria-install.sh <command> [options]"
            echo ""
            echo "Commands:"
            echo "  install [--version X.Y.Z]   Install memoria"
            echo "  update [VERSION]             Update to latest or specific version"
            echo "  uninstall [--yes]            Remove memoria"
            echo "  health                       Health check"
            echo "  version                      Show version"
            echo "  check                        Check for updates"
            exit 1
            ;;
    esac
}

main "$@"
