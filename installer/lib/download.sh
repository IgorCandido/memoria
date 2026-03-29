#!/usr/bin/env bash
# download.sh — Network downloads, checksums, and version caching
# GitHub release downloads via gh CLI, SHA256 verification, version cache

# Constants
DOWNLOAD_TIMEOUT=30
DOWNLOAD_RETRIES=3
DOWNLOAD_RETRY_BASE_DELAY=2
VERSION_CACHE_TTL=3600  # 1 hour in seconds
GITHUB_REPO="IgorCandido/memoria"

# Check network connectivity (5s timeout)
check_network() {
    if command -v gh &>/dev/null; then
        if gh api /rate_limit --jq '.rate.remaining' 2>/dev/null; then
            return 0
        fi
    fi

    # Fallback: try to reach GitHub
    if curl -sf --connect-timeout 5 "https://api.github.com" &>/dev/null; then
        return 0
    fi

    return 1
}

# Get the latest release version from GitHub
get_latest_version() {
    local version

    version=$(gh api "repos/${GITHUB_REPO}/releases/latest" --jq '.tag_name' 2>/dev/null) || return 1

    # Strip leading 'v'
    version="${version#v}"
    echo "$version"
}

# Download a file with retry logic
# Usage: download_file <url> <output_path>
download_file() {
    local url="$1"
    local output="$2"
    local attempt=0
    local delay="$DOWNLOAD_RETRY_BASE_DELAY"

    while [[ "$attempt" -lt "$DOWNLOAD_RETRIES" ]]; do
        attempt=$((attempt + 1))

        if gh api "$url" > "$output" 2>/dev/null; then
            return 0
        fi

        # Fallback to curl for direct URLs
        if curl -fsSL --connect-timeout "$DOWNLOAD_TIMEOUT" -o "$output" "$url" 2>/dev/null; then
            return 0
        fi

        if [[ "$attempt" -lt "$DOWNLOAD_RETRIES" ]]; then
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done

    return 1
}

# Download a GitHub release asset
# Usage: download_release_asset <version> <asset_name> <output_path>
download_release_asset() {
    local version="$1"
    local asset_name="$2"
    local output="$3"

    local tag="v${version}"

    # Use gh to download release asset
    gh release download "$tag" \
        --repo "$GITHUB_REPO" \
        --pattern "$asset_name" \
        --output "$output" \
        2>/dev/null
}

# Compute SHA256 checksum (cross-platform)
compute_sha256() {
    local file="$1"

    if command -v sha256sum &>/dev/null; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v shasum &>/dev/null; then
        shasum -a 256 "$file" | awk '{print $1}'
    elif command -v openssl &>/dev/null; then
        openssl dgst -sha256 "$file" | awk '{print $NF}'
    else
        echo "ERROR: No SHA256 tool available" >&2
        return 1
    fi
}

# Verify a file's checksum against expected value
verify_checksum() {
    local file="$1"
    local expected="$2"

    local actual
    actual="$(compute_sha256 "$file")" || return 1

    if [[ "$actual" == "$expected" ]]; then
        return 0
    else
        echo "Checksum mismatch: expected=$expected actual=$actual" >&2
        return 1
    fi
}

# Read version cache
# Returns the cached latest version, or empty string if stale/missing
read_version_cache() {
    local cache_file="$1"

    if [[ ! -f "$cache_file" ]]; then
        echo ""
        return 1
    fi

    local checked_at
    checked_at=$(python3 -c "
import json, sys
try:
    data = json.load(open('$cache_file'))
    print(data.get('checked_at', ''))
except: pass
" 2>/dev/null)

    if [[ -z "$checked_at" ]]; then
        echo ""
        return 1
    fi

    # Check if cache is still fresh
    local cache_ts now_ts
    cache_ts=$(python3 -c "
from datetime import datetime
try:
    dt = datetime.fromisoformat('$checked_at'.replace('Z', '+00:00'))
    print(int(dt.timestamp()))
except: print(0)
" 2>/dev/null)
    now_ts=$(date +%s)

    local age=$((now_ts - cache_ts))
    if [[ "$age" -gt "$VERSION_CACHE_TTL" ]]; then
        echo ""
        return 1
    fi

    # Return cached version
    python3 -c "
import json
try:
    data = json.load(open('$cache_file'))
    print(data.get('latest_version', ''))
except: pass
" 2>/dev/null
}

# Write version cache
write_version_cache() {
    local cache_file="$1"
    local latest_version="$2"
    local current_version="$3"

    python3 -c "
import json
from datetime import datetime, timezone

data = {
    'latest_version': '$latest_version',
    'current_version': '$current_version',
    'checked_at': datetime.now(timezone.utc).isoformat(),
    'cache_ttl_hours': 24,
    'update_available': '$latest_version' != '$current_version',
    'notification_shown': False,
    'check_error': None
}

with open('$cache_file', 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null
}
