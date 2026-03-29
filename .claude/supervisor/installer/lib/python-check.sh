#!/usr/bin/env bash
# Python Version Check Library
# Requires: Bash 4.0+ (BR-024)
# Functions for verifying Python 3.11+ is available

# Minimum required Python version
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11

# Find Python 3 executable
# Returns: path to python3 executable
find_python() {
    # Try common python3 commands in order
    for cmd in python3 python3.13 python3.12 python3.11 python; do
        if command -v "$cmd" &> /dev/null; then
            # Verify it's actually Python 3
            local version
            version=$("$cmd" --version 2>&1 | grep -oE 'Python [0-9]+\.[0-9]+' | cut -d' ' -f2)
            local major
            major=$(echo "$version" | cut -d. -f1)
            if [[ "$major" == "3" ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done

    return 1
}

# Get Python version
# Arguments: python_command (optional, defaults to python3)
# Returns: version string (e.g., "3.11.5")
get_python_version() {
    local python_cmd="${1:-python3}"

    if ! command -v "$python_cmd" &> /dev/null; then
        return 1
    fi

    "$python_cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
}

# Parse Python version into major and minor
# Arguments: version_string
# Returns: "major minor" (space-separated)
parse_python_version() {
    local version="$1"

    local major minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)

    echo "$major $minor"
}

# Check if Python version meets minimum requirement
# Arguments: python_command (optional)
# Returns: 0 if meets requirement, 1 if not, 2 if Python not found
check_python_version() {
    local python_cmd="${1:-}"

    # Find Python if not specified
    if [[ -z "$python_cmd" ]]; then
        python_cmd=$(find_python)
        if [[ -z "$python_cmd" ]]; then
            return 2  # Python not found
        fi
    fi

    # Get version
    local version
    version=$(get_python_version "$python_cmd")
    if [[ -z "$version" ]]; then
        return 2
    fi

    # Parse version
    local major minor
    read -r major minor <<< "$(parse_python_version "$version")"

    # Check minimum version
    if [[ $major -gt $MIN_PYTHON_MAJOR ]]; then
        return 0
    elif [[ $major -eq $MIN_PYTHON_MAJOR && $minor -ge $MIN_PYTHON_MINOR ]]; then
        return 0
    fi

    return 1  # Version too old
}

# Get Python installation instructions for current OS
# Returns: installation instructions
get_python_install_instructions() {
    local os
    os=$(uname -s)

    echo ""
    echo "Please install Python 3.11 or higher:"
    echo ""

    case "$os" in
        Darwin)
            echo "  Using Homebrew (recommended):"
            echo "    brew install python@3.11"
            echo ""
            echo "  Or download from:"
            echo "    https://www.python.org/downloads/macos/"
            ;;
        Linux)
            # Detect Linux distribution
            if [[ -f /etc/os-release ]]; then
                source /etc/os-release
                case "$ID" in
                    ubuntu|debian)
                        echo "  Using apt:"
                        echo "    sudo apt update"
                        echo "    sudo apt install python3.11"
                        ;;
                    fedora)
                        echo "  Using dnf:"
                        echo "    sudo dnf install python3.11"
                        ;;
                    arch)
                        echo "  Using pacman:"
                        echo "    sudo pacman -S python"
                        ;;
                    *)
                        echo "  Download from:"
                        echo "    https://www.python.org/downloads/"
                        ;;
                esac
            else
                echo "  Download from:"
                echo "    https://www.python.org/downloads/"
            fi
            ;;
        *)
            echo "  Download from:"
            echo "    https://www.python.org/downloads/"
            ;;
    esac

    echo ""
}

# Verify Python and print status
# Returns: 0 on success, non-zero on failure
verify_python() {
    local python_cmd
    python_cmd=$(find_python)

    if [[ -z "$python_cmd" ]]; then
        echo "Error: Python 3 not found"
        get_python_install_instructions
        return 2
    fi

    local version
    version=$(get_python_version "$python_cmd")

    check_python_version "$python_cmd"
    local result=$?

    if [[ $result -eq 0 ]]; then
        echo "✓ Python $version found ($python_cmd)"
        return 0
    else
        echo "Error: Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ required, found $version"
        get_python_install_instructions
        return 1
    fi
}
