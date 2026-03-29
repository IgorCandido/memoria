#!/usr/bin/env bash
# python-check.sh — Python 3.11+ detection and validation
# Finds suitable Python, validates version, provides install instructions

# Minimum required Python version
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

# Find a suitable Python executable
# Returns the path to python3 or python that meets version requirements
find_python() {
    local candidates=("python3" "python3.13" "python3.12" "python3.11" "python")

    for cmd in "${candidates[@]}"; do
        if command -v "$cmd" &>/dev/null; then
            local version
            version="$("$cmd" --version 2>&1 | awk '{print $2}')"
            if check_python_version "$version"; then
                command -v "$cmd"
                return 0
            fi
        fi
    done

    return 1
}

# Get Python version string from executable
get_python_version() {
    local python_cmd="${1:-python3}"

    if ! command -v "$python_cmd" &>/dev/null; then
        echo ""
        return 1
    fi

    "$python_cmd" --version 2>&1 | awk '{print $2}'
}

# Check if a Python version string meets minimum requirements (3.11+)
check_python_version() {
    local version="$1"

    # Parse major.minor
    local major minor
    major="$(echo "$version" | cut -d. -f1)"
    minor="$(echo "$version" | cut -d. -f2)"

    if [[ -z "$major" || -z "$minor" ]]; then
        return 1
    fi

    if [[ "$major" -gt "$PYTHON_MIN_MAJOR" ]]; then
        return 0
    fi

    if [[ "$major" -eq "$PYTHON_MIN_MAJOR" && "$minor" -ge "$PYTHON_MIN_MINOR" ]]; then
        return 0
    fi

    return 1
}

# Get platform-specific Python install instructions
get_python_install_instructions() {
    local os
    os="$(uname -s)"

    case "$os" in
        Darwin)
            cat <<'EOF'
Python 3.11+ is required. Install options for macOS:
  1. brew install python@3.13
  2. Download from https://www.python.org/downloads/
  3. pyenv install 3.13.0
EOF
            ;;
        Linux)
            cat <<'EOF'
Python 3.11+ is required. Install options for Linux:
  1. sudo apt install python3.11  (Debian/Ubuntu)
  2. sudo dnf install python3.11  (Fedora/RHEL)
  3. pyenv install 3.13.0
  4. Download from https://www.python.org/downloads/
EOF
            ;;
        *)
            echo "Python 3.11+ is required. Download from https://www.python.org/downloads/"
            ;;
    esac
}
