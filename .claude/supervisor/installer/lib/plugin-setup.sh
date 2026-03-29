#!/usr/bin/env bash
# Plugin Setup Library
# Requires: Bash 4.0+ (BR-024)
# Functions for creating .claude/ directory structure and manifest

# Standard Claude plugin directory structure
CLAUDE_PLUGIN_DIRS=(
    "skills"
    "commands"
    "agents"
    "config"
    "supervisor"
)

# Create the .claude/ directory structure
# Arguments: target_directory
# Returns: 0 on success, non-zero on failure
create_plugin_structure() {
    local target="$1"
    local claude_dir="$target/.claude"

    # Create main .claude directory
    if ! mkdir -p "$claude_dir"; then
        return 1
    fi

    # Create subdirectories
    for dir in "${CLAUDE_PLUGIN_DIRS[@]}"; do
        if ! mkdir -p "$claude_dir/$dir"; then
            return 1
        fi
    done

    # Create .gitkeep files for empty directories
    for dir in skills commands agents config; do
        touch "$claude_dir/$dir/.gitkeep"
    done

    return 0
}

# Generate installation manifest
# Arguments: target_directory, version, release_url, checksums_array
# Returns: 0 on success, writes manifest.json
generate_manifest() {
    local target="$1"
    local version="$2"
    local release_url="$3"
    shift 3
    local checksums=("$@")

    local manifest_file="$target/.claude/manifest.json"
    local install_date
    install_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build checksums JSON array
    local checksums_json="["
    local first=true
    for checksum in "${checksums[@]}"; do
        if [[ "$first" == true ]]; then
            first=false
        else
            checksums_json+=","
        fi
        checksums_json+="\"$checksum\""
    done
    checksums_json+="]"

    # Write manifest
    cat > "$manifest_file" << EOF
{
    "version": "$version",
    "install_date": "$install_date",
    "release_url": "$release_url",
    "installer_version": "$(cat "$(dirname "${BASH_SOURCE[0]}")/../VERSION" 2>/dev/null || echo "unknown")",
    "file_checksums": $checksums_json
}
EOF

    return $?
}

# Read manifest version
# Arguments: target_directory
# Returns: version string or empty if no manifest
read_manifest_version() {
    local target="$1"
    local manifest_file="$target/.claude/manifest.json"

    if [[ ! -f "$manifest_file" ]]; then
        return 1
    fi

    # Parse version from JSON (simple grep to avoid jq dependency)
    grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$manifest_file" | head -1 | cut -d'"' -f4
}

# Check if project has existing installation
# Arguments: target_directory
# Returns: 0 if installed, 1 if not
has_installation() {
    local target="$1"

    [[ -f "$target/.claude/manifest.json" ]]
}

# Create backup of existing installation
# Arguments: target_directory
# Returns: backup directory path
create_backup() {
    local target="$1"
    local claude_dir="$target/.claude"

    if [[ ! -d "$claude_dir" ]]; then
        return 1
    fi

    local current_version
    current_version=$(read_manifest_version "$target")
    current_version="${current_version:-unknown}"

    local timestamp
    timestamp=$(date +"%Y%m%d-%H%M%S")

    local backup_dir="$claude_dir/.backup-${current_version}-${timestamp}"

    # Create backup directory
    mkdir -p "$backup_dir"

    # Copy all except backups
    for item in "$claude_dir"/*; do
        local name
        name=$(basename "$item")
        if [[ "$name" != .backup-* ]]; then
            cp -r "$item" "$backup_dir/"
        fi
    done

    echo "$backup_dir"
}

# Remove backup directory
# Arguments: backup_directory
remove_backup() {
    local backup_dir="$1"

    if [[ -d "$backup_dir" && "$backup_dir" == */.backup-* ]]; then
        rm -rf "$backup_dir"
    fi
}

# List all backups in project
# Arguments: target_directory
# Returns: newline-separated list of backup directories
list_backups() {
    local target="$1"
    local claude_dir="$target/.claude"

    if [[ ! -d "$claude_dir" ]]; then
        return 1
    fi

    for backup in "$claude_dir"/.backup-*; do
        if [[ -d "$backup" ]]; then
            echo "$backup"
        fi
    done
}

# Get checksums for all installed files
# Arguments: target_directory
# Returns: space-separated list of "filename:checksum" pairs
get_installation_checksums() {
    local target="$1"
    local supervisor_dir="$target/.claude/supervisor"

    if [[ ! -d "$supervisor_dir" ]]; then
        return 1
    fi

    local checksums=()

    while IFS= read -r -d '' file; do
        local filename
        filename=$(basename "$file")
        local checksum
        checksum=$(compute_sha256 "$file" 2>/dev/null)
        if [[ -n "$checksum" ]]; then
            checksums+=("$filename:$checksum")
        fi
    done < <(find "$supervisor_dir" -type f -print0)

    echo "${checksums[*]}"
}

# Compute SHA256 (local version - avoid circular dependency)
compute_sha256() {
    local file="$1"

    if command -v sha256sum &> /dev/null; then
        sha256sum "$file" | cut -d' ' -f1
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$file" | cut -d' ' -f1
    else
        openssl dgst -sha256 "$file" | awk '{print $NF}'
    fi
}
