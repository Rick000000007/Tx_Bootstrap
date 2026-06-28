# TX-Packages Troubleshooting Guide

## Common Issues

### Android NDK Not Found

**Symptom:**
```
ERROR: Android NDK not found. Set ANDROID_NDK_HOME environment variable.
```

**Solutions:**

1. Install NDK via Android Studio
2. Download NDK manually:
```bash
wget https://dl.google.com/android/repository/android-ndk-r27c-linux.zip
unzip android-ndk-r27c-linux.zip
export ANDROID_NDK_HOME=$PWD/android-ndk-r27c
```
3. Use setup script:
```bash
AUTO_DOWNLOAD=1 ./scripts/setup-ndk.sh
source .env
```

### Recipe Parse Errors

**Symptom:**
```
Failed to parse recipes/mypackage.recipe: Invalid version string
```

**Solutions:**

1. Check recipe syntax:
```bash
cat recipes/mypackage.recipe
```

2. Validate version format:
```bash
python3 -m tx_packages info mypackage
```

3. Check for required fields (name, version, category, description, homepage, license)

### Download Failures

**Symptom:**
```
Failed to download source: HTTP 404
```

**Solutions:**

1. Check if upstream URL is accessible:
```bash
curl -I <source-url>
```

2. Update source URL in recipe
3. Check for mirror URLs
4. Verify checksum is correct

### Build Failures

**Symptom:**
```
Build failed for mypackage: Command failed (exit 1): ./configure ...
```

**Solutions:**

1. Check build logs:
```bash
ls artifacts/mypackage/
```

2. Try building manually:
```bash
cd sources/mypackage-1.0.0
export CC=aarch64-linux-android29-clang
./configure --host=aarch64-linux-android
make
```

3. Check for missing dependencies:
```bash
python3 -c "
from builders.recipe import RecipeParser
parser = RecipeParser('recipes')
recipe = parser.get_recipe('mypackage')
print('Dependencies:', recipe.depends)
print('Build deps:', recipe.makedepends)
"
```

4. Try with verbose output:
```bash
python3 -m tx_packages build --recipe mypackage -v
```

### Checksum Mismatch

**Symptom:**
```
Checksum mismatch: expected abc..., got def...
```

**Solutions:**

1. Re-download the source:
```bash
rm downloads/mypackage-1.0.0.tar.gz
python3 -m tx_packages build --recipe mypackage --force
```

2. Update checksum in recipe:
```bash
sha256sum downloads/mypackage-1.0.0.tar.gz
```

### Dependency Resolution Errors

**Symptom:**
```
DependencyError: Dependency cycles detected: 1
```

**Solutions:**

1. View dependency errors:
```bash
python3 -c "
from builders.recipe import RecipeParser
from builders.dependency import DependencyResolver
parser = RecipeParser('recipes')
recipes = parser.load_all()
resolver = DependencyResolver(recipes)
try:
    resolver.resolve()
except:
    pass
for error in resolver.errors:
    print(error)
"
```

2. Fix circular dependencies in recipes

### Bootstrap Generation Fails

**Symptom:**
```
Bootstrap generation failed: Userspace appears empty
```

**Solutions:**

1. Check that packages were built:
```bash
ls packages/
```

2. Run bootstrap manually:
```bash
python3 -m tx_packages bootstrap
```

3. Verify with verification script:
```bash
./scripts/verify-bootstrap.sh
```

## Platform-Specific Issues

### macOS

**Issue:** Clang not found
```bash
# Install Xcode Command Line Tools
xcode-select --install
```

**Issue:** Missing GNU tools
```bash
# Install via Homebrew
brew install coreutils findutils gnu-tar gnu-sed
```

### Windows (WSL2)

**Issue:** Slow file operations
```bash
# Keep NDK and repository in WSL filesystem
# Avoid /mnt/c paths
```

**Issue:** Network connectivity
```bash
# Check DNS resolution
cat /etc/resolv.conf
```

## Performance Issues

### Slow Builds

1. Enable parallel builds:
```bash
export MAKEFLAGS="-j$(nproc)"
```

2. Use ccache:
```bash
export USE_CCACHE=1
ccache -M 10G  # Set cache size
```

3. Skip unnecessary steps:
```bash
# Don't re-download sources
# Use incremental builds
python3 -m tx_packages build
```

### Out of Disk Space

1. Clean build artifacts:
```bash
python3 -m tx_packages clean --all
```

2. Remove downloaded sources:
```bash
python3 -m tx_packages clean --downloads
```

3. Check disk usage:
```bash
du -sh downloads/ sources/ artifacts/ packages/ cache/
```

## Getting Help

1. Check the logs:
```bash
tail -f output/build.log
```

2. Run diagnostics:
```bash
python3 -c "
from builders.config import BuildConfig
config = BuildConfig()
print('NDK:', config.ndk_path)
print('Clang:', config.clang_path)
print('Sysroot:', config.sysroot)
print('Target:', config.target_triple)
print('API:', config.min_api_level)
"
```

3. Open an issue with:
   - Full error message
   - Build log snippet
   - Recipe file content
   - Environment details
