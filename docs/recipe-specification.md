# TX-Packages Recipe Specification

## Overview

TX-Packages recipes define how to download, build, and package upstream software for the TX Linux userspace. Recipe files use a simple key-value format with support for lists and dictionaries.

## File Format

Recipes are plain text files with `.recipe` extension stored in the `recipes/` directory. The format uses `key = value` pairs with line continuations.

### Basic Structure

```
name = <package-name>
version = <upstream-version>
category = <category>
description = <short description>
homepage = <project-url>
license = <spdx-identifier>
maintainer = <name> <email>

source =
    <url>    <sha256-checksum>
    [<url>    <sha256-checksum>]

depends =
    [<dependency>]

makedepends =
    [<build-dependency>]

build_style = <build-system>
```

## Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Package name (lowercase, alphanumeric) | `bash` |
| `version` | Upstream version string | `5.2.21` |
| `category` | Package category | `shells` |
| `description` | Short description | `GNU Bourne Again Shell` |
| `homepage` | Project homepage URL | `https://www.gnu.org/software/bash/` |
| `license` | SPDX license identifier | `GPL-3.0-or-later` |
| `build_style` | Build system type | `gnu` |

### Source Definition

```
source =
    <url>    <sha256-checksum>    [<filename>]
```

Multiple sources can be listed (each on its own line). The checksum is SHA-256. An optional filename override can be provided.

## Optional Fields

| Field | Description | Default |
|-------|-------------|---------|
| `epoch` | Package epoch (for version scheme changes) | `0` |
| `release` | Package release number | `1` |
| `maintainer` | Package maintainer | From config |
| `upstream_author` | Original software author | `""` |

### Dependencies

```
depends =
    libfoo
    libbar

makedepends =
    cmake
    pkg-config

checkdepends =
    pytest

optdepends =
    feature-name=Description of optional feature

conflicts =
    old-package-name

provides =
    virtual-package-name

replaces =
    old-package-name

recommends =
    suggested-package
```

### Build Configuration

```
build_style = gnu|cmake|meson|python|make|custom|meta
build_dir = build

configure_args =
    --enable-feature
    --with-library=system

make_args =
    -C src

cmake_args =
    -DENABLE_TESTS=OFF
    -DBUILD_SHARED_LIBS=ON

meson_args =
    -Ddefault_library=both

check_args =
    check
```

### Environment Variables

```
env_vars =
    CUSTOM_VAR=value
    ANOTHER_VAR=/path/to/resource
```

### Pre/Post Commands

```
pre_build_cmds =
    autoreconf -fi
    ./script.sh

post_build_cmds =
    strip --strip-debug *.so

pre_install_cmds =
    install -Dm644 doc/man.1 $DESTDIR/usr/share/man/man1/

post_install_cmds =
    ln -s tool $DESTDIR/usr/bin/alternative-name
```

### Patches

```
patches =
    fix-android-build.patch
    disable-broken-feature.patch

patch_args = -p1
```

Patches are searched in `patches/<package-name>/` first, then in `patches/`.

### Scriptlets

```
pre_install_script = echo "Installing package..."
post_install_script = ldconfig
pre_remove_script = echo "Removing package..."
post_remove_script = rm -f /etc/package.conf
```

### File Lists

```
extra_files =
    README.md
    LICENSE

backup_files =
    etc/package.conf
```

### Build Options

```
strip_binaries = true
strip_static = true
strip_shared = false
static = false
shared = true
```

## Build Styles

| Style | Description | Typical Use |
|-------|-------------|-------------|
| `gnu` | GNU autotools (configure && make && make install) | Most traditional C/C++ projects |
| `cmake` | CMake (cmake -B build && cmake --build build) | Modern C++ projects |
| `meson` | Meson (meson setup build && meson compile) | GTK, systemd, etc. |
| `python` | Python setuptools (setup.py build/install) | Python packages |
| `make` | Simple Makefiles (make && make install) | Lightweight C projects |
| `custom` | Custom build via pre_build_cmds/post_build_cmds | Projects with unique build systems |
| `meta` | Meta package (no build, dependency-only) | Package groups |

## Categories

| Category | Description |
|----------|-------------|
| `tx-system` | TX system packages (runtime, base, cli, pkg) |
| `shells` | Command shells (bash, zsh, fish, dash) |
| `core-utils` | Core system utilities (coreutils, grep, sed, tar, etc.) |
| `networking` | Network tools and libraries (curl, wget, openssl, etc.) |
| `compression` | Compression libraries and tools (zlib, xz, zstd, etc.) |
| `build-tools` | Build systems (make, cmake, meson, autotools, etc.) |
| `compilers` | Compilers and compiler-rt |
| `languages` | Programming languages (python, lua, perl, ruby, nodejs) |
| `vcs` | Version control systems (git) |
| `editors` | Text editors (vim, nano) |
| `libraries` | System and utility libraries (ncurses, libxml2, pcre2, etc.) |
| `databases` | Database engines (sqlite) |
| `system` | System utilities (procps, iproute2, util-linux, etc.) |
| `devel` | Development tools (gdb, strace, file, which, etc.) |
| `doc` | Documentation tools (man-db, groff, texinfo) |

## Example Recipe

```
name = curl
version = 8.11.1
category = networking
description = Command line tool and library for transferring data with URLs
homepage = https://curl.se/
license = curl
maintainer = TX-Packages <packages@tx.dev>
epoch = 0
release = 1
build_style = gnu

source =
    https://curl.se/download/curl-8.11.1.tar.xz    5a8d9ed6c1c330b55f8f1f0f5b2e3c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1

depends =
    openssl
    zlib
    nghttp2
    libssh2
    libpsl

makedepends =
    autoconf
    automake
    libtool
    perl

configure_args =
    --enable-ipv6
    --enable-unix-sockets
    --enable-threaded-resolver
    --with-openssl
    --with-zlib
    --with-nghttp2
    --with-libssh2
    --with-libpsl
    --disable-manual
    --disable-docs
    --without-librtmp
    --without-libidn2

env_vars =
    CFLAGS=-O2 -fPIC
```

## Best Practices

1. **Always specify checksums**: Every source must have a SHA-256 checksum
2. **Use SPDX identifiers**: Use standard SPDX license identifiers
3. **Minimal dependencies**: Only list direct dependencies, not transitive ones
4. **Version pinning**: Pin specific versions for reproducible builds
5. **Patch naming**: Use descriptive patch names (e.g., `fix-android-api-29.patch`)
6. **One recipe per package**: Each upstream project gets its own recipe
7. **Consistent categories**: Use existing categories before creating new ones
