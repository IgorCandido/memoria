#!/usr/bin/env bash
# version.sh — Semantic version parsing and comparison
# Provides semver parsing, validation, comparison, and normalization

# Parse semver string into components
# Usage: parse_semver "1.2.3-beta" → sets SEMVER_MAJOR=1, SEMVER_MINOR=2, SEMVER_PATCH=3, SEMVER_PRE="beta"
parse_semver() {
    local version="$1"

    # Strip leading 'v' if present
    version="${version#v}"

    # Validate format
    if ! validate_semver "$version"; then
        return 1
    fi

    # Split pre-release suffix
    SEMVER_PRE=""
    if [[ "$version" == *-* ]]; then
        SEMVER_PRE="${version#*-}"
        version="${version%%-*}"
    fi

    SEMVER_MAJOR="${version%%.*}"
    local rest="${version#*.}"
    SEMVER_MINOR="${rest%%.*}"
    SEMVER_PATCH="${rest#*.}"

    return 0
}

# Validate semver format (X.Y.Z with optional -prerelease)
validate_semver() {
    local version="$1"
    version="${version#v}"

    if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        return 0
    fi
    return 1
}

# Compare two semver strings
# Returns: 0 if equal, 1 if v1 > v2, 2 if v1 < v2
compare_versions() {
    local v1="$1"
    local v2="$2"

    # Normalize both
    v1="$(normalize_version "$v1")"
    v2="$(normalize_version "$v2")"

    # Parse v1
    local v1_pre=""
    local v1_base="$v1"
    if [[ "$v1" == *-* ]]; then
        v1_pre="${v1#*-}"
        v1_base="${v1%%-*}"
    fi

    local v1_major="${v1_base%%.*}"
    local v1_rest="${v1_base#*.}"
    local v1_minor="${v1_rest%%.*}"
    local v1_patch="${v1_rest#*.}"

    # Parse v2
    local v2_pre=""
    local v2_base="$v2"
    if [[ "$v2" == *-* ]]; then
        v2_pre="${v2#*-}"
        v2_base="${v2%%-*}"
    fi

    local v2_major="${v2_base%%.*}"
    local v2_rest="${v2_base#*.}"
    local v2_minor="${v2_rest%%.*}"
    local v2_patch="${v2_rest#*.}"

    # Compare major
    if [[ "$v1_major" -gt "$v2_major" ]]; then return 1; fi
    if [[ "$v1_major" -lt "$v2_major" ]]; then return 2; fi

    # Compare minor
    if [[ "$v1_minor" -gt "$v2_minor" ]]; then return 1; fi
    if [[ "$v1_minor" -lt "$v2_minor" ]]; then return 2; fi

    # Compare patch
    if [[ "$v1_patch" -gt "$v2_patch" ]]; then return 1; fi
    if [[ "$v1_patch" -lt "$v2_patch" ]]; then return 2; fi

    # If versions are equal in X.Y.Z, check pre-release
    # A version with pre-release has LOWER precedence than without
    if [[ -z "$v1_pre" && -n "$v2_pre" ]]; then return 1; fi
    if [[ -n "$v1_pre" && -z "$v2_pre" ]]; then return 2; fi
    if [[ -z "$v1_pre" && -z "$v2_pre" ]]; then return 0; fi

    # Both have pre-release — compare lexicographically
    if [[ "$v1_pre" > "$v2_pre" ]]; then return 1; fi
    if [[ "$v1_pre" < "$v2_pre" ]]; then return 2; fi

    return 0
}

# Check if v1 is newer than v2
is_newer() {
    compare_versions "$1" "$2"
    [[ $? -eq 1 ]]
}

# Check if v1 is older than v2
is_older() {
    compare_versions "$1" "$2"
    [[ $? -eq 2 ]]
}

# Normalize version string
# - Strips leading 'v'
# - Fills missing components with 0 (e.g., "1" → "1.0.0", "1.2" → "1.2.0")
normalize_version() {
    local version="$1"

    # Strip leading 'v'
    version="${version#v}"

    # Count dots
    local dots="${version//[^.]/}"
    local dot_count="${#dots}"

    case "$dot_count" in
        0) version="${version}.0.0" ;;
        1) version="${version}.0" ;;
    esac

    echo "$version"
}

# Read version from a VERSION file
read_version_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        echo ""
        return 1
    fi

    local version
    version="$(tr -d '[:space:]' < "$file")"
    echo "$version"
}
