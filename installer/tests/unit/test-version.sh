#!/usr/bin/env bash
# test-version.sh — Unit tests for version.sh
# Tests semver parsing, comparison, normalization

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(cd "$SCRIPT_DIR/../../lib" && pwd)"

source "$LIB_DIR/version.sh"

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

assert_exit() {
    local desc="$1" expected_code="$2"
    shift 2
    local actual_code=0
    "$@" || actual_code=$?
    if [[ "$expected_code" == "$actual_code" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected exit $expected_code, got $actual_code" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "  Testing validate_semver..."
assert_exit "valid 1.2.3" 0 validate_semver "1.2.3"
assert_exit "valid 0.0.1" 0 validate_semver "0.0.1"
assert_exit "valid 10.20.30" 0 validate_semver "10.20.30"
assert_exit "valid with pre-release" 0 validate_semver "1.2.3-beta"
assert_exit "valid with v prefix" 0 validate_semver "v1.2.3"
assert_exit "valid pre-release dot" 0 validate_semver "1.2.3-rc.1"
assert_exit "invalid no dots" 1 validate_semver "123"
assert_exit "invalid one dot" 1 validate_semver "1.2"
assert_exit "invalid letters" 1 validate_semver "a.b.c"
assert_exit "invalid empty" 1 validate_semver ""

echo "  Testing parse_semver..."
parse_semver "1.2.3"
assert_eq "major 1.2.3" "1" "$SEMVER_MAJOR"
assert_eq "minor 1.2.3" "2" "$SEMVER_MINOR"
assert_eq "patch 1.2.3" "3" "$SEMVER_PATCH"
assert_eq "pre 1.2.3" "" "$SEMVER_PRE"

parse_semver "v10.20.30-beta"
assert_eq "major v10.20.30-beta" "10" "$SEMVER_MAJOR"
assert_eq "minor v10.20.30-beta" "20" "$SEMVER_MINOR"
assert_eq "patch v10.20.30-beta" "30" "$SEMVER_PATCH"
assert_eq "pre v10.20.30-beta" "beta" "$SEMVER_PRE"

echo "  Testing normalize_version..."
assert_eq "normalize 1" "1.0.0" "$(normalize_version "1")"
assert_eq "normalize 1.2" "1.2.0" "$(normalize_version "1.2")"
assert_eq "normalize 1.2.3" "1.2.3" "$(normalize_version "1.2.3")"
assert_eq "normalize v1.2.3" "1.2.3" "$(normalize_version "v1.2.3")"

echo "  Testing compare_versions..."
assert_exit "equal" 0 compare_versions "1.0.0" "1.0.0"
assert_exit "newer major" 1 compare_versions "2.0.0" "1.0.0"
assert_exit "older major" 2 compare_versions "1.0.0" "2.0.0"
assert_exit "newer minor" 1 compare_versions "1.2.0" "1.1.0"
assert_exit "older minor" 2 compare_versions "1.1.0" "1.2.0"
assert_exit "newer patch" 1 compare_versions "1.0.2" "1.0.1"
assert_exit "older patch" 2 compare_versions "1.0.1" "1.0.2"
assert_exit "release > pre-release" 1 compare_versions "1.0.0" "1.0.0-beta"
assert_exit "pre-release < release" 2 compare_versions "1.0.0-alpha" "1.0.0"
assert_exit "v-prefix equal" 0 compare_versions "v1.0.0" "1.0.0"

echo "  Testing is_newer / is_older..."
assert_exit "is_newer true" 0 is_newer "2.0.0" "1.0.0"
assert_exit "is_newer false" 1 is_newer "1.0.0" "2.0.0"
assert_exit "is_older true" 0 is_older "1.0.0" "2.0.0"
assert_exit "is_older false" 1 is_older "2.0.0" "1.0.0"

echo "  Testing read_version_file..."
tmpfile=$(mktemp)
echo "3.0.0" > "$tmpfile"
assert_eq "read version file" "3.0.0" "$(read_version_file "$tmpfile")"
rm -f "$tmpfile"

result=$(read_version_file "/nonexistent/path" || true)
assert_eq "read missing file" "" "$result"

# Summary
echo "  Results: $((PASS + FAIL)) tests, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
