#!/usr/bin/env bash
# Version Comparison Library
# Requires: Bash 4.0+ (BR-024)
# Functions for parsing, comparing, and validating semantic versions

# Parse semver string into components
# Arguments: version_string
# Returns: major minor patch prerelease (space-separated, prerelease is empty for stable)
# BR-017: Enhanced to extract pre-release identifier
parse_semver() {
    local version="$1"

    # Remove leading 'v' if present
    version="${version#v}"

    # BR-017: Extract components including pre-release (e.g., "1.0.0-alpha.1")
    if [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(-([a-zA-Z0-9.-]+))?(\+.*)?$ ]]; then
        local major="${BASH_REMATCH[1]}"
        local minor="${BASH_REMATCH[2]}"
        local patch="${BASH_REMATCH[3]}"
        local prerelease="${BASH_REMATCH[5]:-}"
        echo "$major $minor $patch $prerelease"
        return 0
    fi

    # Handle partial versions (e.g., "0.3" -> "0.3.0")
    if [[ "$version" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
        echo "${BASH_REMATCH[1]} ${BASH_REMATCH[2]} 0 "
        return 0
    fi

    # Handle single number (e.g., "1" -> "1.0.0")
    if [[ "$version" =~ ^([0-9]+)$ ]]; then
        echo "${BASH_REMATCH[1]} 0 0 "
        return 0
    fi

    return 1
}

# Validate semver format
# Arguments: version_string
# Returns: 0 if valid, 1 if invalid
validate_semver() {
    local version="$1"

    # Remove leading 'v' if present
    version="${version#v}"

    # Check for valid semver format
    if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$ ]]; then
        return 0
    fi

    # Also accept partial versions
    if [[ "$version" =~ ^[0-9]+\.[0-9]+$ ]] || [[ "$version" =~ ^[0-9]+$ ]]; then
        return 0
    fi

    return 1
}

# Compare two versions
# Arguments: version1, version2
# Returns: 0 if v1 == v2, 1 if v1 > v2, 2 if v1 < v2
# BR-017: Enhanced to handle pre-release versions per semver spec
compare_versions() {
    local v1="$1"
    local v2="$2"

    # Parse both versions
    local v1_parts v2_parts
    v1_parts=$(parse_semver "$v1") || return 3
    v2_parts=$(parse_semver "$v2") || return 3

    # Split into arrays (BR-017: now includes prerelease)
    read -r v1_major v1_minor v1_patch v1_prerelease <<< "$v1_parts"
    read -r v2_major v2_minor v2_patch v2_prerelease <<< "$v2_parts"

    # Compare major
    if (( v1_major > v2_major )); then
        return 1
    elif (( v1_major < v2_major )); then
        return 2
    fi

    # Compare minor
    if (( v1_minor > v2_minor )); then
        return 1
    elif (( v1_minor < v2_minor )); then
        return 2
    fi

    # Compare patch
    if (( v1_patch > v2_patch )); then
        return 1
    elif (( v1_patch < v2_patch )); then
        return 2
    fi

    # BR-017: Compare pre-release versions
    # Per semver spec: stable > pre-release (e.g., 1.0.0 > 1.0.0-alpha)
    if [[ -z "$v1_prerelease" && -n "$v2_prerelease" ]]; then
        return 1  # v1 (stable) > v2 (pre-release)
    elif [[ -n "$v1_prerelease" && -z "$v2_prerelease" ]]; then
        return 2  # v1 (pre-release) < v2 (stable)
    elif [[ -n "$v1_prerelease" && -n "$v2_prerelease" ]]; then
        # Both are pre-releases: lexicographic comparison
        if [[ "$v1_prerelease" > "$v2_prerelease" ]]; then
            return 1
        elif [[ "$v1_prerelease" < "$v2_prerelease" ]]; then
            return 2
        fi
    fi

    # Equal
    return 0
}

# Check if version1 is newer than version2
# Arguments: version1, version2
# Returns: 0 if v1 > v2, 1 otherwise
is_newer() {
    compare_versions "$1" "$2"
    [[ $? -eq 1 ]]
}

# Check if version1 is older than version2
# Arguments: version1, version2
# Returns: 0 if v1 < v2, 1 otherwise
is_older() {
    compare_versions "$1" "$2"
    [[ $? -eq 2 ]]
}

# Check if two versions are equal
# Arguments: version1, version2
# Returns: 0 if equal, 1 otherwise
is_equal() {
    compare_versions "$1" "$2"
    [[ $? -eq 0 ]]
}

# Normalize version string (remove 'v' prefix, ensure 3 parts)
# Arguments: version_string
# Returns: normalized version (e.g., "0.3.0")
normalize_version() {
    local version="$1"

    # Remove leading 'v'
    version="${version#v}"

    # Parse and reconstruct
    local parts
    parts=$(parse_semver "$version") || return 1
    read -r major minor patch <<< "$parts"

    echo "$major.$minor.$patch"
}

# Get version from VERSION file
# Arguments: version_file_path
# Returns: version string
read_version_file() {
    local version_file="$1"

    if [[ ! -f "$version_file" ]]; then
        return 1
    fi

    # Read first non-empty line
    local version
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ -n "$line" && ! "$line" =~ ^[[:space:]]*# ]]; then
            version="$line"
            break
        fi
    done < "$version_file"

    echo "$version"
}
