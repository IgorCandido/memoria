#!/usr/bin/env bash
# test-uninstall.sh — Integration test for uninstall workflow
# Installs then uninstalls, verifies complete cleanup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR=$(mktemp -d)
PASS=0
FAIL=0

cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

assert_not_exists() {
    local desc="$1" path="$2"
    if [[ ! -e "$path" && ! -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — $path should not exist but does" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_exists() {
    local desc="$1" path="$2"
    if [[ -e "$path" || -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — $path does not exist" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" file="$3"
    if [[ ! -f "$file" ]] || ! grep -qF "$needle" "$file" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc — '$needle' still found in $file" >&2
        FAIL=$((FAIL + 1))
    fi
}

echo "Integration Test: Uninstall"
echo "==========================="
echo "Test directory: $TEST_DIR"
echo ""

# Override paths for testing
export MEMORIA_INSTALL_DIR="$TEST_DIR/memoria"
export MEMORIA_SOURCE_DIR="$INSTALLER_DIR"
export MEMORIA_DOCKER_AVAILABLE="false"
export HOME="$TEST_DIR/home"
mkdir -p "$HOME/.claude/skills"

# Create fake shell RC files
mkdir -p "$HOME"
echo "# test bashrc" > "$HOME/.bashrc"
echo "# test zshrc" > "$HOME/.zshrc"

# ─── Step 1: Install first ───────────────────────────────────────────
echo "Step 1: Installing memoria for uninstall test..."
bash "$INSTALLER_DIR/memoria-install.sh" install 2>&1 || {
    echo "  NOTE: Install may fail if gh/git unavailable"
}

# Verify install created something
if [[ -d "$MEMORIA_INSTALL_DIR" ]]; then
    assert_exists "install dir exists" "$MEMORIA_INSTALL_DIR"
    echo "  Installation completed"
else
    echo "  NOTE: Installation didn't complete (expected without gh/git)"
    echo "  Creating mock installation for uninstall test..."

    # Create mock installation
    mkdir -p "$MEMORIA_INSTALL_DIR/repo/memoria"
    mkdir -p "$MEMORIA_INSTALL_DIR/.venv/bin"
    mkdir -p "$MEMORIA_INSTALL_DIR/lib"

    # Copy libs
    cp "$INSTALLER_DIR/lib/"*.sh "$MEMORIA_INSTALL_DIR/lib/"
    cp "$INSTALLER_DIR/memoria-install.sh" "$MEMORIA_INSTALL_DIR/"
    chmod +x "$MEMORIA_INSTALL_DIR/memoria-install.sh"

    # Create config
    python3 -c "
import json
from datetime import datetime, timezone
config = {
    'version': '1.0.0',
    'install_date': datetime.now(timezone.utc).isoformat(),
    'install_path': '$MEMORIA_INSTALL_DIR',
    'repo_path': '$MEMORIA_INSTALL_DIR/repo',
    'venv_path': '$MEMORIA_INSTALL_DIR/.venv',
    'installer_version': '1.0.0',
    'python_version': '3.13.0',
    'install_method': 'clone',
    'git_commit': 'abc1234'
}
with open('$MEMORIA_INSTALL_DIR/config.json', 'w') as f:
    json.dump(config, f, indent=2)
"

    # Create skill symlink
    ln -sf "$MEMORIA_INSTALL_DIR/repo" "$HOME/.claude/skills/memoria"

    # Add shell integration
    echo '[ -f "'"$MEMORIA_INSTALL_DIR/shell-init.sh"'" ] && source "'"$MEMORIA_INSTALL_DIR/shell-init.sh"'" # Added by memoria installer' >> "$HOME/.bashrc"
    echo '[ -f "'"$MEMORIA_INSTALL_DIR/shell-init.sh"'" ] && source "'"$MEMORIA_INSTALL_DIR/shell-init.sh"'" # Added by memoria installer' >> "$HOME/.zshrc"

    assert_exists "mock install dir" "$MEMORIA_INSTALL_DIR"
fi

# ─── Step 2: Uninstall with --yes ────────────────────────────────────
echo ""
echo "Step 2: Running uninstall..."
bash "$INSTALLER_DIR/memoria-install.sh" uninstall "true" 2>&1

# ─── Step 3: Verify cleanup ──────────────────────────────────────────
echo ""
echo "Step 3: Verifying cleanup..."

assert_not_exists "install dir removed" "$MEMORIA_INSTALL_DIR"
assert_not_exists "skill symlink removed" "$HOME/.claude/skills/memoria"
assert_not_contains "bashrc cleaned" "Added by memoria installer" "$HOME/.bashrc"
assert_not_contains "zshrc cleaned" "Added by memoria installer" "$HOME/.zshrc"

# ─── Step 4: Uninstall again (should report not installed) ───────────
echo ""
echo "Step 4: Running uninstall again (idempotency test)..."
output=$(bash "$INSTALLER_DIR/memoria-install.sh" uninstall "true" 2>&1)
PASS=$((PASS + 1))  # If it didn't error, that's a pass

# ─── Summary ──────────────────────────────────────────────────────────
echo ""
echo "==========================="
echo "Results: $((PASS + FAIL)) tests, $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
