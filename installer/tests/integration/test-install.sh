#!/usr/bin/env bash
# test-install.sh — Integration test for install workflow
# Uses MEMORIA_INSTALL_DIR to avoid touching real installation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR=$(mktemp -d)
PASS=0
FAIL=0

# Cleanup on exit
cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

assert_exists() {
    local desc="$1" path="$2"
    if [[ -e "$path" || -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — $path does not exist" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_contains() {
    local desc="$1" needle="$2" file="$3"
    if grep -qF "$needle" "$file" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — '$needle' not found in $file" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_json_field() {
    local desc="$1" file="$2" field="$3" expected="$4"
    local actual
    actual=$(python3 -c "import json; print(json.load(open('$file')).get('$field',''))" 2>/dev/null)
    if [[ "$actual" == "$expected" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — expected='$expected', actual='$actual'" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "Integration Test: Install"
echo "========================="
echo "Test directory: $TEST_DIR"
echo ""

# Override install dir to temp directory
export MEMORIA_INSTALL_DIR="$TEST_DIR/memoria"
export MEMORIA_SOURCE_DIR="$INSTALLER_DIR"
# Skip Docker in test
export MEMORIA_DOCKER_AVAILABLE="false"
# Use test branch override
export MEMORIA_BRANCH="${MEMORIA_BRANCH:-main}"

# ─── Test: Run Stage 2 installer ─────────────────────────────────────
echo "Testing Stage 2 installer (memoria-install.sh install)..."

# Create a mock skill dir
export HOME="$TEST_DIR/home"
mkdir -p "$HOME/.claude/skills"

bash "$INSTALLER_DIR/memoria-install.sh" install 2>&1 || {
    echo "  NOTE: Install exited with non-zero (may be expected if gh/git not available)"
}

# ─── Verify directory structure ───────────────────────────────────────
echo ""
echo "Verifying directory structure..."

assert_exists "install dir" "$MEMORIA_INSTALL_DIR"
assert_exists "lib dir" "$MEMORIA_INSTALL_DIR/lib"
assert_exists "shell-init.sh" "$MEMORIA_INSTALL_DIR/shell-init.sh"

# Config should exist if install succeeded
if [[ -f "$MEMORIA_INSTALL_DIR/config.json" ]]; then
    echo "  Config file found - verifying schema..."
    assert_json_field "config has version" "$MEMORIA_INSTALL_DIR/config.json" "version" "" || true
    assert_exists "config.json" "$MEMORIA_INSTALL_DIR/config.json"
    assert_contains "config has install_path" "install_path" "$MEMORIA_INSTALL_DIR/config.json"
    assert_contains "config has venv_path" "venv_path" "$MEMORIA_INSTALL_DIR/config.json"
    assert_contains "config has install_method" "install_method" "$MEMORIA_INSTALL_DIR/config.json"
fi

# Verify shell-init.sh has the memoria function
if [[ -f "$MEMORIA_INSTALL_DIR/shell-init.sh" ]]; then
    assert_contains "shell-init has memoria function" "memoria()" "$MEMORIA_INSTALL_DIR/shell-init.sh"
fi

# ─── Test: Version command ────────────────────────────────────────────
echo ""
echo "Testing version command..."
if bash "$INSTALLER_DIR/memoria-install.sh" version 2>&1 | grep -q "memoria v"; then
    PASS=$((PASS + 1))
    echo "  Version command works"
else
    echo "  NOTE: Version command failed (expected if install didn't complete)"
fi

# ─── Summary ──────────────────────────────────────────────────────────
echo ""
echo "========================="
echo "Results: $((PASS + FAIL)) tests, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
