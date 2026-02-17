#!/usr/bin/env bash
# shell-detect.sh — Shell detection and RC file management
# Detects user shell, manages source lines in RC files

# Detect the user's login shell
detect_shell() {
    local shell_name
    shell_name="$(basename "${SHELL:-/bin/bash}")"

    case "$shell_name" in
        bash|zsh) echo "$shell_name" ;;
        *)        echo "bash" ;;  # Default fallback
    esac
}

# Get the shell configuration file path
get_shell_config_file() {
    local shell_name="${1:-$(detect_shell)}"

    case "$shell_name" in
        zsh)  echo "${HOME}/.zshrc" ;;
        bash)
            # Prefer .bashrc, fall back to .bash_profile (macOS)
            if [[ -f "${HOME}/.bashrc" ]]; then
                echo "${HOME}/.bashrc"
            else
                echo "${HOME}/.bash_profile"
            fi
            ;;
        *) echo "${HOME}/.profile" ;;
    esac
}

# Validate a path for dangerous characters before using in source line
# Returns 0 if safe, 1 if dangerous
validate_source_line() {
    local path="$1"

    # Block dangerous metacharacters in the path
    if [[ "$path" == *";"* ]]; then
        echo "Rejected: semicolons not allowed in path" >&2
        return 1
    fi
    if [[ "$path" == *"|"* ]]; then
        echo "Rejected: pipes not allowed in path" >&2
        return 1
    fi
    if [[ "$path" == *'`'* ]]; then
        echo "Rejected: backticks not allowed in path" >&2
        return 1
    fi
    if [[ "$path" == *'$('* ]]; then
        echo "Rejected: command substitution not allowed in path" >&2
        return 1
    fi
    if [[ "$path" == *'&&'* ]]; then
        echo "Rejected: && not allowed in path" >&2
        return 1
    fi
    if [[ "$path" == *'||'* ]]; then
        echo "Rejected: || not allowed in path" >&2
        return 1
    fi
    if [[ "$path" == *".."* ]]; then
        echo "Rejected: path traversal not allowed" >&2
        return 1
    fi

    return 0
}

# Add a source line to a shell RC file (idempotent)
# Uses a marker comment to identify our lines
MEMORIA_MARKER="# Added by memoria installer"

add_source_line() {
    local rc_file="$1"
    local source_path="$2"

    local source_line="[ -f \"${source_path}\" ] && source \"${source_path}\" ${MEMORIA_MARKER}"

    # Check if already present
    if [[ -f "$rc_file" ]] && grep -qF "$MEMORIA_MARKER" "$rc_file"; then
        return 0  # Already present
    fi

    # Create RC file if it doesn't exist
    if [[ ! -f "$rc_file" ]]; then
        touch "$rc_file"
    fi

    # Append with a newline before if file doesn't end with one
    if [[ -s "$rc_file" ]] && [[ "$(tail -c 1 "$rc_file")" != "" ]]; then
        echo "" >> "$rc_file"
    fi

    echo "$source_line" >> "$rc_file"
    return 0
}

# Remove the source line from a shell RC file
remove_source_line() {
    local rc_file="$1"

    if [[ ! -f "$rc_file" ]]; then
        return 0
    fi

    # Remove lines containing our marker
    if grep -qF "$MEMORIA_MARKER" "$rc_file"; then
        local tmp_file
        tmp_file="$(mktemp)"
        grep -vF "$MEMORIA_MARKER" "$rc_file" > "$tmp_file"
        mv "$tmp_file" "$rc_file"
    fi

    return 0
}
