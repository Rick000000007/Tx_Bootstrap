# TX-Packages Architecture

## Overview

TX-Packages is a production-grade Linux userspace build system designed specifically for Android (arm64-v8a). It automates the entire process of downloading upstream sources, cross-compiling for Android, packaging into `.txpkg` format, and generating a bootstrappable repository.

## System Architecture

```
                    +-------------------+
                    |   GitHub Actions   |
                    |     CI/CD Pipeline |
                    +--------+----------+
                             |
           +-----------------+-----------------+
           |                                   |
    +------v------+                     +------v------+
    |   Recipe    |                     |   Source    |
    |   Parser    |                     |   Downloader |
    +------+------+                     +------+------+
           |                                   |
           |    +-------------------------+    |
           +---->   Dependency Resolver   <----+
                +-------------------------+
                             |
                    +--------v--------+
                    |  Build Scheduler |
                    | (Parallel Build) |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
       +------v------+ +-----v-----+ +-----v-----+
       | GNU Builder | | CMake     | | Meson     |
       +------+------+ +-----+-----+ +-----+-----+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v--------+
                    | Package Builder |
                    | (.txpkg format) |
                    +--------+--------+
                             |
           +-----------------+------------------+
           |                                  |
    +------v-------+                 +--------v-------+
    |  Bootstrap    |                 |  Repository    |
    |  Generator    |                 |  Generator     |
    +------+-------+                 +--------+-------+
           |                                  |
    +------v-------+                 +--------v-------+
    | bootstrap.   |                 | Packages index |
    | tar.zst      |                 | SHA256SUMS     |
    +--------------+                 +----------------+
```

## Core Components

### 1. Recipe Parser (`builders/recipe.py`)

The recipe parser reads `.recipe` files that define how to build each package. Recipes specify:
- Package metadata (name, version, description, license)
- Upstream source URLs with SHA-256 checksums
- Build dependencies and runtime dependencies
- Build system type (GNU autotools, CMake, Meson, Python, etc.)
- Configuration arguments and environment variables
- Patches to apply

### 2. Dependency Resolver (`builders/dependency.py`)

Resolves inter-package dependencies using topological sorting:
- **Graph Construction**: Builds a directed graph from recipe dependencies
- **Cycle Detection**: Uses DFS to detect and report circular dependencies
- **Topological Sort**: Kahn's algorithm produces a valid build order
- **Parallel Groups**: Groups packages by dependency depth for parallel execution

### 3. Source Downloader (`builders/downloader.py`)

Downloads upstream source tarballs with production features:
- **HTTP Download**: urllib-based with configurable timeout
- **Resume Support**: Continues interrupted downloads via Range headers
- **Mirror Fallback**: Tries multiple URLs if primary fails
- **Retry Logic**: Exponential backoff with configurable retry count
- **Checksum Verification**: SHA-256 verification of downloaded files
- **Progress Callbacks**: Optional progress reporting

### 4. Package Builder (`builders/builder.py`)

Cross-compiles packages for Android using the NDK toolchain:
- **Build Systems**: Supports GNU autotools, CMake, Meson, Python setuptools, Make
- **Incremental Builds**: Content-addressable cache keys skip unchanged packages
- **Parallel Compilation**: Uses `-j$(nproc)` for parallel make/ninja
- **Environment Setup**: Configures CC, CXX, LD, AR, etc. for cross-compilation
- **Patch Application**: Applies patches in order with error handling

### 5. Package Generator (`builders/packager.py`)

Creates `.txpkg` package files:
- **Manifest Generation**: JSON manifest with file list and checksums
- **Control File**: Debian-style control metadata for compatibility
- **Archive Creation**: zstd-compressed tar archive with magic header
- **Package Verification**: Validates archive integrity and structure

### 6. Bootstrap Generator (`builders/bootstrap.py`)

Assembles the complete TX Linux userspace:
- **Package Installation**: Extracts all packages into a clean prefix
- **Config Generation**: Creates passwd, hosts, resolv.conf, profile, etc.
- **Userspace Validation**: Verifies essential binaries and directories
- **Archive Creation**: Produces `bootstrap.tar.zst` with manifest

### 7. Repository Generator (`builders/repository.py`)

Generates package repository metadata:
- **Packages Index**: Debian-style package list with metadata
- **JSON Index**: Machine-readable package information
- **SHA256SUMS**: Checksums for all repository files
- **Manifest**: Repository-level metadata (toolchain, versions, etc.)

## Build Flow

### Full Build Pipeline

1. **Recipe Loading**: Parse all `.recipe` files in `recipes/`
2. **Dependency Resolution**: Build dependency graph and compute build order
3. **Source Download**: Download and verify all upstream sources
4. **Build**: Cross-compile each package for Android arm64
5. **Package**: Generate `.txpkg` files from build artifacts
6. **Bootstrap**: Install all packages into empty prefix and archive
7. **Repository**: Generate package index and metadata

### Incremental Build

1. Compute content-addressable cache key from recipe + sources
2. Check for existing cache marker
3. Skip build if cache marker exists and is valid
4. Build and create cache marker if missing

### Parallel Build

1. Resolve dependencies and compute build levels
2. Level 0 packages (no dependencies) build first in parallel
3. Level N packages build after all Level N-1 dependencies complete
4. Continue until all levels complete

## Data Flow

```
Recipe Files (.recipe)
    |
    v
Parsed Recipe Objects
    |
    v
Dependency Graph ----> Topological Sort ----> Build Order
    |                                              |
    v                                              v
Source URLs <---------------------------- Build Queue
    |
    v
Downloaded Tarballs (downloads/)
    |
    v
Extracted Sources (sources/)
    |
    v
Built Artifacts (artifacts/)
    |
    v
.txpkg Files (packages/)
    |
    +------------+------------+
    |                         |
    v                         v
Bootstrap Image            Repository
(bootstrap.tar.zst)        (Packages, SHA256SUMS)
```

## Configuration

The `BuildConfig` class centralizes all configuration:

### Paths
- `recipes/`: Package recipes
- `downloads/`: Downloaded source tarballs
- `sources/`: Extracted source trees
- `cache/`: Build cache markers
- `artifacts/`: Build output staging
- `packages/`: Generated `.txpkg` files
- `bootstrap/`: Bootstrap assembly directory
- `repository/`: Package repository output

### Toolchain
- `ndk_path`: Android NDK location
- `*_path`: LLVM tool paths (clang, lld, ar, etc.)
- `sysroot`: Android sysroot path
- `target_triple`: `aarch64-linux-android`

### Flags
- `cflags`: Compiler flags (target, sysroot, PIC, optimizations)
- `cxxflags`: C++ flags (includes `-stdlib=libc++`)
- `ldflags`: Linker flags (lld, libc++, section GC)
- `cppflags`: Preprocessor flags (ANDROID, API level)

## Error Handling

- **DependencyError**: Circular dependencies, missing packages
- **BuildError**: Compilation failures, configuration errors
- **BootstrapError**: Empty/incomplete userspace validation failures

All errors are logged with context and propagated up the call chain.

## Logging

Structured logging at multiple levels:
- **DEBUG**: Detailed operation steps
- **INFO**: Build progress and milestones
- **WARNING**: Non-fatal issues (missing optional deps)
- **ERROR**: Build failures and validation errors
