#!/usr/bin/env bash
# test-download.sh — Unit tests for download.sh
# Tests checksum computation, verification, version cache logic

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(cd "$SCRIPT_DIR/../../lib" && pwd)"

source "$LIB_DIR/download.sh"

PASS=0
FAIL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected='$expected', actual='$actual'" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_exit_code() {
    local desc="$1" expected="$2"
    shift 2
    local code=0
    "$@" || code=$?
    if [[ "$expected" == "$code" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected exit $expected, got $code" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "  Testing compute_sha256..."
# Create a test file with known content
tmpfile=$(mktemp)
echo -n "hello world" > "$tmpfile"

# Known SHA256 of "hello world"
expected_hash="b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
actual_hash=$(compute_sha256 "$tmpfile")
assert_eq "sha256 known content" "$expected_hash" "$actual_hash"

echo "  Testing verify_checksum..."
assert_exit_code "checksum match" 0 verify_checksum "$tmpfile" "$expected_hash"
assert_exit_code "checksum mismatch" 1 verify_checksum "$tmpfile" "0000000000000000000000000000000000000000000000000000000000000000"

rm -f "$tmpfile"

echo "  Testing version cache..."
cache_dir=$(mktemp -d)
cache_file="$cache_dir/.version-cache"

# Missing cache should return empty
result=$(read_version_cache "$cache_file" || true)
assert_eq "missing cache empty" "" "$result"

# Write a fresh cache
write_version_cache "$cache_file" "1.2.3" "1.0.0"

# Read should return the version
result=$(read_version_cache "$cache_file" || true)
assert_eq "fresh cache read" "1.2.3" "$result"

# Write a stale cache (set checked_at to far in the past)
python3 -c "
import json
data = json.load(open('$cache_file'))
data['checked_at'] = '2020-01-01T00:00:00+00:00'
with open('$cache_file', 'w') as f:
    json.dump(data, f)
" 2>/dev/null

# Stale cache should return empty
result=$(read_version_cache "$cache_file" || true)
assert_eq "stale cache empty" "" "$result"

rm -rf "$cache_dir"

# Summary
echo "  Results: $((PASS + FAIL)) tests, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
