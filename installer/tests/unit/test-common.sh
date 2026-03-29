#!/usr/bin/env bash
# test-common.sh — Unit tests for common.sh
# Tests logging, die(), OS detection, command verification

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(cd "$SCRIPT_DIR/../../lib" && pwd)"

source "$LIB_DIR/common.sh"

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

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — '$needle' not found in output" >&2
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

echo "  Testing logging functions..."
output=$(log_info "test message" 2>&1)
assert_contains "log_info output" "test message" "$output"

output=$(log_warning "warn message" 2>&1)
assert_contains "log_warning output" "warn message" "$output"

output=$(log_error "error message" 2>&1)
assert_contains "log_error output" "error message" "$output"

output=$(log_step "step message" 2>&1)
assert_contains "log_step output" "step message" "$output"

output=$(log_success "success message" 2>&1)
assert_contains "log_success output" "success message" "$output"

echo "  Testing die()..."
# die() should exit with code 1
output=$(bash -c 'source '"$LIB_DIR"'/common.sh; die "fatal error"' 2>&1 || true)
assert_contains "die output" "fatal error" "$output"

code=0
bash -c 'source '"$LIB_DIR"'/common.sh; die "fatal"' 2>/dev/null || code=$?
assert_eq "die exit code" "1" "$code"

echo "  Testing detect_os..."
os=$(detect_os)
case "$(uname -s)" in
    Darwin) assert_eq "detect_os macOS" "macos" "$os" ;;
    Linux)  assert_eq "detect_os Linux" "linux" "$os" ;;
    *)      assert_eq "detect_os unknown" "unknown" "$os" ;;
esac

echo "  Testing detect_arch..."
arch=$(detect_arch)
case "$(uname -m)" in
    x86_64|amd64)  assert_eq "detect_arch x86_64" "x86_64" "$arch" ;;
    arm64|aarch64) assert_eq "detect_arch arm64" "arm64" "$arch" ;;
esac

echo "  Testing require_command..."
assert_exit_code "require bash" 0 require_command "bash"
# require_command with missing command should exit 1
code=0
bash -c 'source '"$LIB_DIR"'/common.sh; require_command "nonexistent_command_xyz"' 2>/dev/null || code=$?
assert_eq "require missing cmd" "1" "$code"

echo "  Testing validate_path..."
assert_exit_code "valid path" 0 validate_path "/home/user/test"
assert_exit_code "valid relative" 0 validate_path "/tmp/memoria"

code=0
bash -c 'source '"$LIB_DIR"'/common.sh; validate_path "/foo/../bar"' 2>/dev/null || code=$?
assert_eq "reject path traversal" "1" "$code"

code=0
bash -c 'source '"$LIB_DIR"'/common.sh; validate_path "/etc/passwd"' 2>/dev/null || code=$?
assert_eq "reject /etc" "1" "$code"

code=0
bash -c 'source '"$LIB_DIR"'/common.sh; validate_path "/System/Library"' 2>/dev/null || code=$?
assert_eq "reject /System" "1" "$code"

echo "  Testing lock file mechanism..."
tmp_lock=$(mktemp -d)/test-lock
acquire_lock "$tmp_lock"
assert_eq "lock acquired" "0" "$?"
# Lock dir should exist
[[ -d "$tmp_lock" ]] && PASS=$((PASS + 1)) || { echo "  FAIL: lock dir missing" >&2; FAIL=$((FAIL + 1)); }
release_lock
# Lock dir should be gone
[[ ! -d "$tmp_lock" ]] && PASS=$((PASS + 1)) || { echo "  FAIL: lock dir still exists" >&2; FAIL=$((FAIL + 1)); }
rmdir "$(dirname "$tmp_lock")" 2>/dev/null || true

# Summary
echo "  Results: $((PASS + FAIL)) tests, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
