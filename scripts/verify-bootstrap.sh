#!/bin/bash
# TX-Packages Bootstrap Verification Script
# Validates a generated bootstrap image

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BOOTSTRAP_DIR="${1:-${REPO_ROOT}/bootstrap/rootfs}"
PREFIX="${BOOTSTRAP_DIR}/data/data/tx.packages/files/usr"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASS++)) || true
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAIL++)) || true
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARN++)) || true
}

info() {
    echo "[INFO] $1"
}

echo "========================================"
echo "TX-Packages Bootstrap Verification"
echo "========================================"
echo "Prefix: ${PREFIX}"
echo ""

# Check prefix exists
if [ ! -d "$PREFIX" ]; then
    fail "Prefix directory does not exist: ${PREFIX}"
    exit 1
fi

# Check essential directories
info "Checking essential directories..."
ESSENTIAL_DIRS=("bin" "lib" "include" "share" "etc" "var" "tmp")
for dir in "${ESSENTIAL_DIRS[@]}"; do
    if [ -d "${PREFIX}/${dir}" ]; then
        pass "Directory exists: ${dir}/"
    else
        warn "Missing directory: ${dir}/"
    fi
done

echo ""

# Check essential binaries
info "Checking essential binaries..."
ESSENTIAL_BINS=("bash" "sh" "ls" "cp" "mv" "rm" "cat" "echo" "grep" "sed" "tar" "gzip")
for bin in "${ESSENTIAL_BINS[@]}"; do
    if [ -f "${PREFIX}/bin/${bin}" ] || [ -L "${PREFIX}/bin/${bin}" ]; then
        pass "Binary exists: ${bin}"
    else
        # Search in other locations
        found=$(find "$PREFIX" -name "$bin" -type f 2>/dev/null | head -1 || true)
        if [ -n "$found" ]; then
            pass "Binary exists: ${bin} (at ${found#${PREFIX}/})"
        else
            warn "Missing binary: ${bin}"
        fi
    fi
done

echo ""

# Check configuration files
info "Checking configuration files..."
CONFIG_FILES=("etc/passwd" "etc/group" "etc/hosts" "etc/resolv.conf" "etc/profile")
for file in "${CONFIG_FILES[@]}"; do
    if [ -f "${PREFIX}/${file}" ]; then
        pass "Config exists: ${file}"
    else
        warn "Missing config: ${file}"
    fi
done

echo ""

# Check libraries
info "Checking shared libraries..."
LIB_COUNT=$(find "${PREFIX}/lib" -name "*.so*" -type f 2>/dev/null | wc -l || echo "0")
if [ "$LIB_COUNT" -gt 0 ]; then
    pass "Found ${LIB_COUNT} shared libraries"
else
    warn "No shared libraries found"
fi

echo ""

# Calculate sizes
info "Calculating sizes..."
TOTAL_SIZE=$(du -sb "$PREFIX" 2>/dev/null | awk '{print $1}' || echo "0")
FILE_COUNT=$(find "$PREFIX" -type f 2>/dev/null | wc -l || echo "0")

info "Total size: $(numfmt --to=iec-i --suffix=B ${TOTAL_SIZE} 2>/dev/null || echo "${TOTAL_SIZE} bytes")"
info "Total files: ${FILE_COUNT}"

if [ "$TOTAL_SIZE" -lt 1024 ]; then
    fail "Bootstrap appears empty (${TOTAL_SIZE} bytes)"
elif [ "$TOTAL_SIZE" -lt 1048576 ]; then
    warn "Bootstrap is very small ($((TOTAL_SIZE / 1024)) KB)"
else
    pass "Bootstrap size is reasonable ($((TOTAL_SIZE / 1024 / 1024)) MB)"
fi

echo ""

# Check if manifest exists
if [ -f "${REPO_ROOT}/output/bootstrap.json" ]; then
    pass "Bootstrap manifest exists"
    info "Packages: $(cat "${REPO_ROOT}/output/bootstrap.json" | grep -c '"name"' || echo "N/A")"
else
    warn "Bootstrap manifest not found"
fi

echo ""
echo "========================================"
echo "Verification Summary"
echo "========================================"
echo -e "Passed:  ${GREEN}${PASS}${NC}"
echo -e "Failed:  ${RED}${FAIL}${NC}"
echo -e "Warnings: ${YELLOW}${WARN}${NC}"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Verification FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}Verification PASSED${NC}"
    exit 0
fi
