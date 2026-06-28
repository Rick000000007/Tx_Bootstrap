# TX-Packages Build Guide

## Prerequisites

### Required Software

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.10+ | Build system |
| Android NDK | r25+ | Cross-compilation toolchain |
| Clang/LLVM | 14+ | Compiler (bundled with NDK) |
| CMake | 3.20+ | CMake-based packages |
| Meson | 0.60+ | Meson-based packages |
| Ninja | 1.10+ | Build tool |
| Git | 2.30+ | Version control |

### Python Dependencies

```bash
pip install zstandard requests pytest
```

### Android NDK Setup

```bash
# Download NDK
wget https://dl.google.com/android/repository/android-ndk-r27c-linux.zip
unzip android-ndk-r27c-linux.zip

# Set environment
export ANDROID_NDK_HOME=$PWD/android-ndk-r27c
export ANDROID_NDK=$ANDROID_NDK_HOME
export PATH=$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH
```

## Local Build

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd tx-packages

# Build everything
python3 -m tx_packages full-build
```

### Step-by-Step Build

#### 1. List Available Packages

```bash
python3 -m tx_packages list
python3 -m tx_packages list --category shells
```

#### 2. Build Specific Packages

```bash
# Build a single package
python3 -m tx_packages build --recipe bash

# Build multiple packages
python3 -m tx_packages build --recipe bash coreutils openssl

# Force rebuild
python3 -m tx_packages build --recipe bash --force
```

#### 3. Build All Packages

```bash
python3 -m tx_packages build
```

#### 4. Generate Bootstrap

```bash
python3 -m tx_packages bootstrap
```

#### 5. Generate Repository

```bash
python3 -m tx_packages repository
```

### Using GitHub Actions

The repository includes a complete CI/CD pipeline:

1. Push to `main` branch triggers automatic builds
2. Pull requests run validation and tests
3. Tags create releases with bootstrap image
4. Manual dispatch allows custom builds

## Build Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANDROID_NDK_HOME` | Android NDK path | Auto-detected |
| `ANDROID_API` | Target API level | 29 |
| `ANDROID_ABI` | Target ABI | arm64-v8a |

### Build Options

Edit `configs/build_config.json` or use environment variables:

```json
{
  "parallel_jobs": 8,
  "optimize": "O2",
  "debug": false,
  "strip_binaries": true,
  "pkg_compression": "zst",
  "pkg_compression_level": 19
}
```

## Debugging Builds

### Verbose Output

```bash
python3 -m tx_packages build --recipe bash -v
```

### Inspect Build Environment

```bash
python3 -c "
from builders.config import BuildConfig
config = BuildConfig()
import json
print(json.dumps(config.env, indent=2))
"
```

### Check Recipe

```bash
python3 -m tx_packages info bash
```

### Clean Build

```bash
# Clean everything
python3 -m tx_packages clean --all

# Clean specific parts
python3 -m tx_packages clean --cache
python3 -m tx_packages clean --sources
python3 -m tx_packages clean --downloads
```

## Testing

### Run Test Suite

```bash
python3 -m tx_packages test -v
```

### Run Specific Tests

```bash
python3 -m pytest tests/test_recipe_parser.py -v
python3 -m pytest tests/test_version.py -v
python3 -m pytest tests/test_dependency_resolver.py -v
```

### Test Coverage

```bash
python3 -m pytest tests/ --cov=builders --cov-report=html
```

## Troubleshooting

### NDK Not Found

```bash
# Verify NDK path
echo $ANDROID_NDK_HOME
ls $ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-clang

# Set manually
export ANDROID_NDK_HOME=/path/to/ndk
```

### Build Failures

1. Check recipe dependencies are built first
2. Verify upstream source URL is accessible
3. Check checksum matches downloaded file
4. Review build logs in artifacts/

### Missing Dependencies

```bash
# Check dependency resolution
python3 -c "
from builders.recipe import RecipeParser
from builders.dependency import DependencyResolver
parser = RecipeParser('recipes')
recipes = parser.load_all()
resolver = DependencyResolver(recipes)
resolver.resolve()
for error in resolver.errors:
    print(f'ERROR: {error}')
"
```

## Performance Tuning

### Parallel Builds

Set `parallel_jobs` to match CPU cores:

```bash
export TX_PARALLEL_JOBS=$(nproc)
```

### CCache

Install and enable ccache for faster rebuilds:

```bash
sudo apt-get install ccache
export USE_CCACHE=1
export CCACHE_DIR=$HOME/.ccache-tx
```

### Download Cache

Downloaded sources are cached in `downloads/` and reused across builds.

## Platform-Specific Notes

### Linux

- Native build environment, all features supported
- Requires standard build tools (gcc, make, etc.)

### macOS

- Install Homebrew dependencies: `brew install cmake meson ninja pkg-config`
- NDK path typically: `$HOME/Library/Android/sdk/ndk`

### Windows (WSL2)

- Use WSL2 Ubuntu for best compatibility
- NDK path should be in WSL filesystem for performance
