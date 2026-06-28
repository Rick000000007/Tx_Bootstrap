# TX-Packages

**TX Linux Userspace Build System for Android**

A production-grade, fully automated Linux distribution build system targeting Android arm64-v8a (aarch64-linux-android). TX-Packages builds a complete Linux userspace from official upstream sources, packages them into the TX Package format (.txpkg), and generates a bootstrappable repository.

## Features

- **Complete Android NDK Integration** — Automatic toolchain detection, sysroot generation, and cross-compilation
- **80+ Production Recipes** — Core utilities, shells, networking, compression, build systems, programming languages, editors, libraries
- **TX Package Format (.txpkg)** — Manifest-based packages with dependency resolution, checksums, and signatures
- **Automated Bootstrap Generation** — Deterministic bootstrap.tar.zst creation with validation
- **GitHub Actions CI/CD** — Full automated build, test, and publish pipeline
- **Deterministic & Reproducible Builds** — Content-addressable cache, pinned versions, verified checksums
- **Parallel & Incremental Builds** — Dependency graph execution with build artifact caching

## Target Platform

| Property | Value |
|----------|-------|
| Architecture | arm64-v8a / aarch64-linux-android |
| Minimum API | 29 (Android 10) |
| Toolchain | LLVM / Clang / LLD |
| libc | Bionic |
| C++ Runtime | libc++ |

## Quick Start

```bash
# Clone and enter repository
git clone <repository-url>
cd tx-packages

# GitHub Actions handles the full build automatically on push
# For local development:
python3 -m tx_packages --help
```

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `.github/workflows/` | CI/CD pipeline definitions |
| `recipes/` | Package build recipes (80+ packages) |
| `patches/` | Source patches for packages |
| `sources/` | Extracted source trees |
| `downloads/` | Downloaded upstream tarballs |
| `cache/` | Build artifact cache |
| `profiles/` | Build profiles and configurations |
| `builders/` | Builder modules (Python) |
| `scripts/` | Utility shell scripts |
| `toolchains/` | Toolchain detection and configuration |
| `bootstrap/` | Bootstrap image generation |
| `repository/` | Package repository output |
| `packages/` | Generated .txpkg files |
| `artifacts/` | Build artifacts |
| `output/` | Final output directory |
| `docs/` | Complete documentation |
| `tests/` | Automated test suite |
| `configs/` | System configuration templates |

## Build System

The TX build framework (`python/tx_packages/`) provides:

- Recipe parser with dependency resolution
- Semantic version handling
- Multi-mirror HTTP downloader with resume and retry
- SHA-256 checksum verification
- Automatic patch application with ordering
- Android NDK toolchain integration
- Parallel job execution with dependency graph
- Incremental build support with content-addressable cache
- Package staging and .txpkg generation
- Repository metadata and index generation
- Bootstrap assembly and validation

## Package Categories

- **TX Runtime** — Core system libraries and runtime support
- **TX Base** — Base system configuration and defaults
- **TX CLI** — Command-line interface utilities
- **Shells** — bash, dash, zsh, fish
- **Core Utilities** — coreutils, grep, sed, findutils, diffutils, patch, tar, gzip, etc.
- **Networking** — curl, wget, openssl, ca-certificates, libssh2, nghttp2
- **Compression Libraries** — zlib, bzip2, xz, zstd, lz4, brotli
- **Build Systems** — make, cmake, meson, ninja, pkg-config, autotools
- **Programming Languages** — python, nodejs, lua, perl, ruby
- **Version Control** — git
- **Editors** — vim, nano
- **Terminal Libraries** — ncurses, readline, libedit
- **Databases** — sqlite
- **System Libraries** — libarchive, libffi, libiconv, libxml2, expat, libevent, pcre2
- **Developer Tools** — file, which, tree, less, more

## License

TX-Packages is released under the MIT License. See `LICENSE` for details.

Individual packages retain their respective upstream licenses.
