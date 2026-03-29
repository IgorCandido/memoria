#!/usr/bin/env bash
# Shell Detection Library
# Requires: Bash 4.0+ (BR-024)
# Detects the user's shell and finds appropriate config files

# Detect the user's current shell
# Returns: bash, zsh, fish, or unknown
detect_shell() {
    # First try $SHELL environment variable
    local shell_path="${SHELL:-}"

    if [[ -n "$shell_path" ]]; then
        local shell_name
        shell_name=$(basename "$shell_path")
        case "$shell_name" in
            bash|zsh|fish)
                echo "$shell_name"
                return 0
                ;;
        esac
    fi

    # Fallback: check running process
    local ps_shell
    ps_shell=$(ps -p $$ -o comm= 2>/dev/null | sed 's/-//')
    case "$ps_shell" in
        bash|zsh|fish)
            echo "$ps_shell"
            return 0
            ;;
    esac

    echo "unknown"
    return 1
}

# Get the shell configuration file path
# Arguments: shell_name (optional, defaults to detected shell)
# Returns: path to config file
get_shell_config_file() {
    local shell_name="${1:-$(detect_shell)}"
    local home="${HOME:-}"

    if [[ -z "$home" ]]; then
        echo ""
        return 1
    fi

    case "$shell_name" in
        bash)
            # Check common bash config files in order of preference
            for config in "$home/.bashrc" "$home/.bash_profile" "$home/.profile"; do
                if [[ -f "$config" ]]; then
                    echo "$config"
                    return 0
                fi
            done
            # Default to .bashrc even if it doesn't exist
            echo "$home/.bashrc"
            return 0
            ;;
        zsh)
            # Check common zsh config files
            for config in "$home/.zshrc" "$home/.zprofile"; do
                if [[ -f "$config" ]]; then
                    echo "$config"
                    return 0
                fi
            done
            # Default to .zshrc
            echo "$home/.zshrc"
            return 0
            ;;
        fish)
            # Fish uses XDG config directory
            local fish_config="${XDG_CONFIG_HOME:-$home/.config}/fish/config.fish"
            echo "$fish_config"
            return 0
            ;;
        *)
            echo ""
            return 1
            ;;
    esac
}

# Get all shell config files that should be updated
# Returns: newline-separated list of config files
get_all_shell_configs() {
    local home="${HOME:-}"
    local configs=()

    if [[ -z "$home" ]]; then
        return 1
    fi

    # Check bash configs
    for config in "$home/.bashrc" "$home/.bash_profile"; do
        if [[ -f "$config" ]]; then
            configs+=("$config")
        fi
    done

    # Check zsh configs
    for config in "$home/.zshrc" "$home/.zprofile"; do
        if [[ -f "$config" ]]; then
            configs+=("$config")
        fi
    done

    # Check fish config
    local fish_config="${XDG_CONFIG_HOME:-$home/.config}/fish/config.fish"
    if [[ -f "$fish_config" ]]; then
        configs+=("$fish_config")
    fi

    printf '%s\n' "${configs[@]}"
}

# Check if a source line already exists in a config file
# Arguments: config_file, source_line_pattern
# Returns: 0 if exists, 1 if not
source_line_exists() {
    local config_file="$1"
    local pattern="$2"

    if [[ ! -f "$config_file" ]]; then
        return 1
    fi

    grep -qF "$pattern" "$config_file" 2>/dev/null
}

# BR-005: Validate source line doesn't contain shell metacharacters
# CRITICAL-001 FIX: Corrected regex pattern to actually match metacharacters
validate_source_line() {
    local source_line="$1"

    # Check for dangerous shell metacharacters that could enable code injection
    # Allow: alphanumeric, space, /, ., -, _, ", $, {, } (for variable expansion), ~
    # Reject: ; & | ` ( ) < >
    if [[ "$source_line" =~ [\;\&\|\`\(\)\<\>] ]]; then
        log_error "Security: Source line contains shell metacharacters"
        return 1
    fi

    # Check for command substitution patterns
    if [[ "$source_line" =~ \$\( ]]; then
        log_error "Security: Source line contains command substitution"
        return 1
    fi

    # Check for embedded newlines or control characters
    if [[ "$source_line" =~ [[:cntrl:]] ]]; then
        log_error "Security: Source line contains control characters"
        return 1
    fi

    return 0
}

# Add source line to shell config
# Arguments: config_file, source_line
# Returns: 0 on success, 1 on failure
add_source_line() {
    local config_file="$1"
    local source_line="$2"
    local source_pattern="${3:-$source_line}"

    # BR-005: Validate source line before using it
    if ! validate_source_line "$source_line"; then
        log_error "Refusing to add unsafe source line to shell config"
        return 1
    fi

    # Check if already present
    if source_line_exists "$config_file" "$source_pattern"; then
        return 0  # Already present, success
    fi

    # Add to end of file with newline
    {
        echo ""
        echo "# Claude Supervisor shell integration"
        echo "$source_line"
    } >> "$config_file"

    return $?
}

# Remove source line from shell config
# Arguments: config_file, pattern_to_remove
# Returns: 0 on success, 1 on failure
remove_source_line() {
    local config_file="$1"
    local pattern="$2"

    if [[ ! -f "$config_file" ]]; then
        return 0  # Nothing to remove
    fi

    # Create temp file without the pattern and its comment
    local temp_file
    temp_file=$(mktemp)

    # Remove the source line and the comment above it
    sed -e '/# Claude Supervisor shell integration/d' \
        -e "/$pattern/d" \
        "$config_file" > "$temp_file"

    mv "$temp_file" "$config_file"
    return $?
}
