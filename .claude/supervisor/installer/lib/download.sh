#!/usr/bin/env bash
# Download Library
# Requires: Bash 4.0+ (BR-024)
# Functions for downloading from GitHub releases and verifying checksums

# BR-014: Configuration constants
readonly NETWORK_TIMEOUT_SECONDS=5

# GitHub repository information
GITHUB_REPO="IgorCandido/claude-supervisor"
GITHUB_API_URL="https://api.github.com/repos/${GITHUB_REPO}/releases"
GITHUB_DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download"

# Check network connectivity
# Returns: 0 if connected, 1 otherwise
check_network() {
    # BR-014: Try to reach GitHub with configured timeout
    if curl --silent --head --fail --connect-timeout "$NETWORK_TIMEOUT_SECONDS" "https://github.com" > /dev/null 2>&1; then
        return 0
    fi

    # Fallback: try to reach any DNS
    if curl --silent --head --fail --connect-timeout "$NETWORK_TIMEOUT_SECONDS" "https://1.1.1.1" > /dev/null 2>&1; then
        return 0
    fi

    return 1
}

# Validate semver format (BR-004)
# Arguments: version string (e.g., "v0.3.0" or "0.3.0")
# Returns: 0 if valid semver, 1 otherwise
validate_semver() {
    local version="$1"

    # Remove 'v' prefix if present
    version="${version#v}"

    # Validate format: X.Y.Z where X, Y, Z are numbers
    # Allow optional -alpha, -beta, -rc suffixes
    if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+(\.[0-9]+)?)?$ ]]; then
        return 0
    fi

    return 1
}

# BR-023: Version cache configuration (1-hour TTL)
readonly VERSION_CACHE_TTL_SECONDS=3600
VERSION_CACHE_DIR="${TMPDIR:-/tmp}/claude-supervisor-version-cache"

# Get cached version if available and not expired
# Returns: cached version string or empty if expired/missing
get_cached_version() {
    local cache_file="$VERSION_CACHE_DIR/latest-version"

    if [[ ! -f "$cache_file" ]]; then
        return 1
    fi

    # Check if cache is expired (BR-023: 1 hour TTL)
    # BR-025: Use helper function from common.sh for cross-platform stat
    local cache_age
    cache_age=$(($(date +%s) - $(get_file_mtime "$cache_file")))

    if [[ $cache_age -ge $VERSION_CACHE_TTL_SECONDS ]]; then
        # Cache expired
        return 1
    fi

    # Cache is valid, return cached version
    cat "$cache_file"
}

# Save version to cache
# Arguments: version string
save_version_cache() {
    local version="$1"

    mkdir -p "$VERSION_CACHE_DIR"
    echo "$version" > "$VERSION_CACHE_DIR/latest-version"
}

# Get latest release version from GitHub
# Returns: version string (e.g., "v0.3.0")
# BR-023: Enhanced with 1-hour cache to reduce GitHub API calls
get_latest_version() {
    # BR-023: Check cache first
    local cached_version
    cached_version=$(get_cached_version 2>/dev/null)
    if [[ -n "$cached_version" ]]; then
        echo "$cached_version"
        return 0
    fi

    # Cache miss or expired - fetch from GitHub
    # TODO: When repo goes public, change back to curl:
    # response=$(curl --silent --fail "${GITHUB_API_URL}/latest" 2>/dev/null)
    # For private repo, use gh api with authentication
    local response
    response=$(gh api "repos/${GITHUB_REPO}/releases/latest" 2>/dev/null)

    if [[ $? -ne 0 || -z "$response" ]]; then
        return 1
    fi

    # BR-004: Validate JSON response is not empty and contains expected structure
    if ! echo "$response" | grep -q '"tag_name"'; then
        log_error "Invalid GitHub API response: missing tag_name field"
        return 1
    fi

    # Parse tag_name from JSON (simple grep approach to avoid jq dependency)
    local version
    version=$(echo "$response" | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)

    if [[ -z "$version" ]]; then
        log_error "Failed to parse version from GitHub API response"
        return 1
    fi

    # BR-004: Validate semver format before returning
    if ! validate_semver "$version"; then
        log_error "Invalid version format from GitHub: $version (expected semver like v0.3.0)"
        return 1
    fi

    # BR-023: Save to cache for next time
    save_version_cache "$version"

    echo "$version"
}

# Get release info for specific version
# Arguments: version (e.g., "v0.3.0" or "0.3.0")
# Returns: JSON response on stdout
get_release_info() {
    local version="$1"

    # Ensure version has 'v' prefix for GitHub
    [[ "$version" != v* ]] && version="v$version"

    # TODO: When repo goes public, change back to curl:
    # curl --silent --fail "${GITHUB_API_URL}/tags/${version}" 2>/dev/null
    # For private repo, use gh api with authentication
    gh api "repos/${GITHUB_REPO}/releases/tags/${version}" 2>/dev/null
}

# Download file from URL
# Arguments: url, output_path
# Returns: 0 on success, non-zero on failure
# BR-018: Enhanced with retry logic (3 attempts, exponential backoff)
download_file() {
    local url="$1"
    local output="$2"
    local max_retries=3
    local attempt=1

    # Create parent directory if needed
    local parent_dir
    parent_dir=$(dirname "$output")
    mkdir -p "$parent_dir"

    # BR-018: Retry loop with exponential backoff
    while (( attempt <= max_retries )); do
        # Download with progress indicator
        if curl --fail --location --progress-bar --output "$output" "$url" 2>&1; then
            return 0
        fi

        # Download failed
        rm -f "$output"  # Clean up partial download

        if (( attempt < max_retries )); then
            # Calculate exponential backoff: 2^(attempt-1) seconds
            local wait_time=$((2 ** (attempt - 1)))
            echo "Download failed (attempt ${attempt}/${max_retries}), retrying in ${wait_time}s..." >&2
            sleep "$wait_time"
        fi

        ((attempt++))
    done

    echo "Download failed after ${max_retries} attempts" >&2
    return 1
}

# Download release tarball
# Arguments: version, output_path
# Returns: 0 on success, non-zero on failure
download_release() {
    local version="$1"
    local output="$2"

    # Ensure version has 'v' prefix
    [[ "$version" != v* ]] && version="v$version"

    # Remove 'v' prefix for filename
    local version_num="${version#v}"

    local filename="claude-supervisor-${version_num}.tar.gz"

    # TODO: When repo goes public, change back to curl:
    # local url="${GITHUB_DOWNLOAD_URL}/${version}/${filename}"
    # download_file "$url" "$output"
    # For private repo, use gh release download with authentication
    local temp_dir
    temp_dir=$(mktemp -d)
    if gh release download "$version" --repo "$GITHUB_REPO" --pattern "$filename" --dir "$temp_dir" 2>/dev/null; then
        mv "$temp_dir/$filename" "$output"
        rm -rf "$temp_dir"
        return 0
    else
        rm -rf "$temp_dir"
        return 1
    fi
}

# Download checksums file
# Arguments: version, output_path
# Returns: 0 on success, non-zero on failure
download_checksums() {
    local version="$1"
    local output="$2"

    # Ensure version has 'v' prefix
    [[ "$version" != v* ]] && version="v$version"

    # TODO: When repo goes public, change back to curl:
    # local url="${GITHUB_DOWNLOAD_URL}/${version}/checksums.txt"
    # download_file "$url" "$output"
    # For private repo, use gh release download with authentication
    local temp_dir
    temp_dir=$(mktemp -d)
    if gh release download "$version" --repo "$GITHUB_REPO" --pattern "checksums.txt" --dir "$temp_dir" 2>/dev/null; then
        mv "$temp_dir/checksums.txt" "$output"
        rm -rf "$temp_dir"
        return 0
    else
        rm -rf "$temp_dir"
        return 1
    fi
}

# Compute SHA256 checksum of file
# Arguments: file_path
# Returns: checksum string
compute_sha256() {
    local file="$1"

    if command -v sha256sum &> /dev/null; then
        sha256sum "$file" | cut -d' ' -f1
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$file" | cut -d' ' -f1
    else
        # macOS fallback
        openssl dgst -sha256 "$file" | awk '{print $NF}'
    fi
}

# Verify file checksum
# Arguments: file_path, expected_checksum
# Returns: 0 if matches, 1 if mismatch
verify_checksum() {
    local file="$1"
    local expected="$2"

    local actual
    actual=$(compute_sha256 "$file")

    [[ "$actual" == "$expected" ]]
}

# Verify file against checksums.txt
# Arguments: file_path, checksums_file
# Returns: 0 if verified, 1 if not found or mismatch
verify_against_checksums_file() {
    local file="$1"
    local checksums_file="$2"

    if [[ ! -f "$checksums_file" ]]; then
        return 1
    fi

    local filename
    filename=$(basename "$file")

    # Find expected checksum for this file
    local expected
    expected=$(grep -F "$filename" "$checksums_file" | awk '{print $1}')

    if [[ -z "$expected" ]]; then
        return 1
    fi

    verify_checksum "$file" "$expected"
}

# Extract tarball
# Arguments: tarball_path, destination_directory
# Returns: 0 on success, non-zero on failure
extract_tarball() {
    local tarball="$1"
    local destination="$2"

    mkdir -p "$destination"

    tar -xzf "$tarball" -C "$destination" 2>/dev/null
}
