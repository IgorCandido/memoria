#!/usr/bin/env bash
# run-all-tests.sh — Test runner for shell unit tests
# Sources each test file and reports pass/fail

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0
FAILED_TESTS=()

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}Running memoria shell unit tests${NC}"
echo "=================================="
echo ""

# Find all test files
for test_file in "$SCRIPT_DIR"/test-*.sh; do
    if [[ ! -f "$test_file" ]]; then
        continue
    fi

    test_name="$(basename "$test_file")"
    echo -e "${BOLD}Running: ${test_name}${NC}"

    if bash "$test_file"; then
        echo -e "  ${GREEN}PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "  ${RED}FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$test_name")
    fi
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo ""
done

# Summary
echo "=================================="
echo -e "${BOLD}Results:${NC} ${TESTS_TOTAL} tests, ${GREEN}${TESTS_PASSED} passed${NC}, ${RED}${TESTS_FAILED} failed${NC}"

if [[ "${#FAILED_TESTS[@]}" -gt 0 ]]; then
    echo -e "\n${RED}Failed tests:${NC}"
    for t in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}✗${NC} $t"
    done
    exit 1
fi

echo -e "\n${GREEN}All tests passed!${NC}"
exit 0
