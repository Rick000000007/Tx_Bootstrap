#!/bin/bash
# TX-Packages Full Build Script
# Runs the complete build pipeline locally

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Configuration
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
BUILD_LOG="${REPO_ROOT}/output/build.log"
FAILED_LOG="${REPO_ROOT}/output/failed.txt"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[BUILD]${NC} $1" | tee -a "$BUILD_LOG"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$BUILD_LOG"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$BUILD_LOG"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$BUILD_LOG"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
        exit 1
    fi
    info "Python: $(python3 --version)"

    # Check NDK
    if [ -z "${ANDROID_NDK_HOME:-}" ]; then
        error "ANDROID_NDK_HOME is not set. Run scripts/setup-ndk.sh first."
        exit 1
    fi
    info "NDK: ${ANDROID_NDK_HOME}"

    # Check Python dependencies
    if ! python3 -c "import zstandard" 2>/dev/null; then
        warn "zstandard not found. Installing..."
        pip install zstandard
    fi

    # Create directories
    mkdir -p "${REPO_ROOT}/output"
    mkdir -p "${REPO_ROOT}/cache"
    > "$BUILD_LOG"
    > "$FAILED_LOG"

    log "Prerequisites check passed"
}

# Step 1: Validate recipes
validate_recipes() {
    log "Step 1/6: Validating recipes..."

    cd "$REPO_ROOT"
    python3 -c "
from builders.recipe import RecipeParser
from pathlib import Path

parser = RecipeParser(Path('recipes'))
recipes = parser.load_all()
print(f'Loaded {len(recipes)} recipes')

if parser.parse_errors:
    print(f'Parse errors: {len(parser.parse_errors)}')
    for path, error in parser.parse_errors:
        print(f'  {path}: {error}')
    exit(1)
else:
    print('All recipes valid')
" 2>&1 | tee -a "$BUILD_LOG"

    log "Recipe validation complete"
}

# Step 2: Resolve dependencies
resolve_dependencies() {
    log "Step 2/6: Resolving dependencies..."

    cd "$REPO_ROOT"
    python3 -c "
from builders.recipe import RecipeParser
from builders.dependency import DependencyResolver
from pathlib import Path

parser = RecipeParser(Path('recipes'))
recipes = parser.load_all()

resolver = DependencyResolver(recipes)
try:
    order = resolver.resolve()
    print(f'Build order: {len(order)} packages')

    levels = resolver.get_build_levels()
    for depth, pkgs in sorted(levels.items()):
        print(f'  Level {depth}: {len(pkgs)} packages')

    if resolver.errors:
        print(f'Warnings: {len(resolver.errors)}')
        for e in resolver.errors:
            print(f'  {e}')
except Exception as ex:
    print(f'ERROR: {ex}')
    exit(1)
" 2>&1 | tee -a "$BUILD_LOG"

    log "Dependency resolution complete"
}

# Step 3: Download sources
download_sources() {
    log "Step 3/6: Downloading sources..."

    cd "$REPO_ROOT"
    python3 -c "
from builders.recipe import RecipeParser
from builders.downloader import SourceDownloader
from pathlib import Path

parser = RecipeParser(Path('recipes'))
recipes = parser.load_all()
downloader = SourceDownloader(Path('downloads'))

success = 0
failed = 0
for name, recipe in recipes.items():
    if not recipe.sources:
        continue
    try:
        result = downloader.download_source(recipe.sources[0], name)
        if result.success:
            success += 1
        else:
            failed += 1
            print(f'FAILED: {name}: {result.error}')
    except Exception as e:
        failed += 1
        print(f'ERROR: {name}: {e}')

print(f'\\nDownloads: {success} success, {failed} failed')
" 2>&1 | tee -a "$BUILD_LOG"

    log "Source download complete"
}

# Step 4: Build packages
build_packages() {
    log "Step 4/6: Building packages..."

    cd "$REPO_ROOT"
    python3 -c "
import sys
from builders.config import BuildConfig
from builders.recipe import RecipeParser
from builders.dependency import DependencyResolver
from builders.builder import PackageBuilder
from builders.packager import PackageGenerator
from pathlib import Path

config = BuildConfig()
parser = RecipeParser(config.recipes_dir)
recipes = parser.load_all()

resolver = DependencyResolver(recipes)
order = resolver.resolve()

builder = PackageBuilder(config)
packager = PackageGenerator(config)

success = 0
failed = 0

for i, pkg_name in enumerate(order, 1):
    recipe = recipes[pkg_name]
    print(f'[{i}/{len(order)}] Building {pkg_name}...')

    try:
        result = builder.build(recipe)
        if result.success:
            success += 1
            if result.install_prefix:
                pkg_path = packager.generate(recipe, result.install_prefix)
                print(f'  Package: {pkg_path}')
        else:
            failed += 1
            print(f'  FAILED: {result.error}')
    except Exception as e:
        failed += 1
        print(f'  ERROR: {e}')

print(f'\\nBuild: {success} success, {failed} failed')
" 2>&1 | tee -a "$BUILD_LOG"

    log "Package build complete"
}

# Step 5: Generate bootstrap
generate_bootstrap() {
    log "Step 5/6: Generating bootstrap..."

    cd "$REPO_ROOT"
    python3 -c "
from builders.config import BuildConfig
from builders.recipe import RecipeParser
from builders.bootstrap import BootstrapGenerator
from pathlib import Path

config = BuildConfig()
parser = RecipeParser(config.recipes_dir)
recipes = parser.load_all()

# Separate recipes into standard and root
standard_recipes = [r for r in recipes.values() if r.name not in config.root_packages]
root_recipes = [r for r in recipes.values() if r.name in config.root_packages]

generator = BootstrapGenerator(config)
try:
    path_std = generator.generate(standard_recipes, config.packages_dir, 'bootstrap')
    print(f'Standard Bootstrap: {path_std}')
    path_root = generator.generate(root_recipes, config.packages_dir, 'bootstrap-root')
    print(f'Root Bootstrap: {path_root}')
except Exception as e:
    print(f'WARNING: Bootstrap generation failed: {e}')
    print('This is expected if package builds failed.')
" 2>&1 | tee -a "$BUILD_LOG"

    log "Bootstrap generation complete"
}

# Step 6: Generate repository
generate_repository() {
    log "Step 6/6: Generating repository..."

    cd "$REPO_ROOT"
    python3 -m tx_packages repository 2>&1 | tee -a "$BUILD_LOG" || true

    log "Repository generation complete"
}

# Main
main() {
    log "========================================"
    log "TX-Packages Full Build Pipeline"
    log "========================================"
    log "Start time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    log "Repository: ${REPO_ROOT}"
    log ""

    START_TIME=$(date +%s)

    check_prerequisites
    validate_recipes
    resolve_dependencies
    download_sources
    build_packages
    generate_bootstrap
    generate_repository

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log ""
    log "========================================"
    log "Build Complete"
    log "Duration: ${DURATION}s ($((DURATION/60))m $((DURATION%60))s)"
    log "Log: ${BUILD_LOG}"
    log "========================================"
}

# Handle arguments
case "${1:-all}" in
    validate)
        check_prerequisites
        validate_recipes
        ;;
    resolve)
        check_prerequisites
        resolve_dependencies
        ;;
    download)
        check_prerequisites
        download_sources
        ;;
    build)
        check_prerequisites
        build_packages
        ;;
    bootstrap)
        check_prerequisites
        generate_bootstrap
        ;;
    repository)
        check_prerequisites
        generate_repository
        ;;
    all|"")
        main
        ;;
    *)
        echo "Usage: $0 {all|validate|resolve|download|build|bootstrap|repository}"
        exit 1
        ;;
esac
