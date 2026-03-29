#!/usr/bin/env bash
# package-release.sh — Create release tarball with checksums and manifest
# Usage: bash scripts/package-release.sh <version>
# Creates: dist/memoria-{version}.tar.gz, dist/checksums.txt, dist/release-manifest.json

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>" >&2
    echo "  Example: $0 0.5.0" >&2
    exit 1
fi

# Strip leading 'v' if present
VERSION="${VERSION#v}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
TARBALL_NAME="memoria-${VERSION}.tar.gz"
STAGING_DIR=$(mktemp -d)

cleanup() {
    rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

echo "Packaging memoria v${VERSION}..."

# Create dist directory
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Create staging directory with release content
STAGE="$STAGING_DIR/memoria-${VERSION}"
mkdir -p "$STAGE"

# Included files/directories
cp -r "$REPO_ROOT/memoria" "$STAGE/"
cp "$REPO_ROOT/pyproject.toml" "$STAGE/"
cp "$REPO_ROOT/requirements.txt" "$STAGE/"
cp "$REPO_ROOT/VERSION" "$STAGE/"
cp "$REPO_ROOT/README.md" "$STAGE/"
cp -r "$REPO_ROOT/installer" "$STAGE/"

# Remove test files from installer in release
rm -rf "$STAGE/installer/tests"

# Remove __pycache__ directories
find "$STAGE" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -name "*.pyc" -delete 2>/dev/null || true

# Count files
FILE_COUNT=$(find "$STAGE" -type f | wc -l | tr -d ' ')

# Create tarball
echo "Creating tarball..."
(cd "$STAGING_DIR" && tar czf "$DIST_DIR/$TARBALL_NAME" "memoria-${VERSION}/")

# Compute checksums
echo "Computing checksums..."
TARBALL_SHA256=""
if command -v sha256sum &>/dev/null; then
    TARBALL_SHA256=$(sha256sum "$DIST_DIR/$TARBALL_NAME" | awk '{print $1}')
elif command -v shasum &>/dev/null; then
    TARBALL_SHA256=$(shasum -a 256 "$DIST_DIR/$TARBALL_NAME" | awk '{print $1}')
elif command -v openssl &>/dev/null; then
    TARBALL_SHA256=$(openssl dgst -sha256 "$DIST_DIR/$TARBALL_NAME" | awk '{print $NF}')
fi

# Write checksums.txt
echo "$TARBALL_SHA256  $TARBALL_NAME" > "$DIST_DIR/checksums.txt"

# Get git info
GIT_COMMIT=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_TAG="v${VERSION}"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Generate release manifest
python3 -c "
import json

manifest = {
    'version': '$VERSION',
    'build_date': '$BUILD_DATE',
    'git_commit': '$GIT_COMMIT',
    'git_tag': '$GIT_TAG',
    'file_count': $FILE_COUNT,
    'tarball_name': '$TARBALL_NAME',
    'tarball_sha256': '$TARBALL_SHA256',
    'python_min_version': '3.11',
    'dependencies_changed': False
}

with open('$DIST_DIR/release-manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"

# Compute checksum for manifest too
MANIFEST_SHA256=""
if command -v sha256sum &>/dev/null; then
    MANIFEST_SHA256=$(sha256sum "$DIST_DIR/release-manifest.json" | awk '{print $1}')
elif command -v shasum &>/dev/null; then
    MANIFEST_SHA256=$(shasum -a 256 "$DIST_DIR/release-manifest.json" | awk '{print $1}')
elif command -v openssl &>/dev/null; then
    MANIFEST_SHA256=$(openssl dgst -sha256 "$DIST_DIR/release-manifest.json" | awk '{print $NF}')
fi

echo "$MANIFEST_SHA256  release-manifest.json" >> "$DIST_DIR/checksums.txt"

# Summary
echo ""
echo "Release packaged successfully:"
echo "  Tarball:   dist/$TARBALL_NAME"
echo "  Checksums: dist/checksums.txt"
echo "  Manifest:  dist/release-manifest.json"
echo "  Files:     $FILE_COUNT"
echo "  SHA256:    $TARBALL_SHA256"
echo ""
