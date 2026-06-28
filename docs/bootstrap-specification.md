# TX Bootstrap Specification

## Overview

The TX Bootstrap is a self-contained Linux userspace image for Android devices. It contains all essential packages pre-installed in a standard FHS layout, ready to be extracted onto an Android device.

## Bootstrap Image

### File Format

| Property | Value |
|----------|-------|
| Primary Format | `bootstrap.tar.zst` |
| Fallback Format | `bootstrap.tar.gz` |
| Compression | zstd level 19 / gzip level 9 |
| Magic | None (plain tar archive) |

### Contents

```
bootstrap.tar.zst
|-- bootstrap.json        # Bootstrap manifest
|-- bin/                  # Essential binaries
|-- sbin/                 # System binaries
|-- lib/                  # Shared libraries
|-- include/              # Header files
|-- share/                # Documentation, data
|-- etc/                  # System configuration
|   |-- passwd
|   |-- group
|   |-- hosts
|   |-- resolv.conf
|   |-- nsswitch.conf
|   |-- profile
|   |-- bash.bashrc
|   |-- inputrc
|-- var/                  # Variable data
|-- tmp/                  # Temporary files
|-- opt/                  # Optional packages
```

## Manifest Format

The `bootstrap.json` manifest contains:

```json
{
  "name": "tx-bootstrap",
  "version": "1.0.0",
  "architecture": "aarch64",
  "api_level": 29,
  "build_date": "2026-01-15T10:30:00+00:00",
  "packages": ["bash", "coreutils", "openssl", "..."],
  "package_versions": {
    "bash": "5.2.21-1",
    "coreutils": "9.5-1",
    "openssl": "3.4.0-1"
  },
  "total_size": 52428800,
  "file_count": 5000,
  "checksum": "sha256:..."
}
```

## Prefix Layout

The bootstrap uses a private prefix to avoid conflicts with Android's system:

```
/data/data/tx.packages/files/usr/
|-- bin/          # User binaries
|-- sbin/         # System binaries
|-- lib/          # Shared libraries (.so files)
|   |-- pkgconfig/ # pkg-config files
|-- include/      # C/C++ headers
|-- share/        # Architecture-independent data
|   |-- man/      # Manual pages
|   |-- info/     # Info documentation
|   |-- doc/      # Package documentation
|   |-- locale/   # Localization files
|   |-- terminfo/ # Terminal definitions
|-- etc/          # Configuration
|-- var/          # Variable data
|-- tmp/          # Temporary directory
|-- opt/          # Optional software
```

## Default Configuration Files

### /etc/passwd
```
root:x:0:0:root:/root:/bin/bash
system:x:1000:1000:system:/data/data/tx.packages/files/home:/bin/bash
```

### /etc/group
```
root:x:0:
system:x:1000:
```

### /etc/hosts
```
127.0.0.1       localhost
::1             localhost ip6-localhost ip6-loopback
```

### /etc/resolv.conf
```
nameserver 8.8.8.8
nameserver 8.8.4.4
```

### /etc/profile
```sh
export PATH=/data/data/tx.packages/files/usr/bin:/data/data/tx.packages/files/usr/sbin:$PATH
export LD_LIBRARY_PATH=/data/data/tx.packages/files/usr/lib:$LD_LIBRARY_PATH
export HOME=/data/data/tx.packages/files/home
export TMPDIR=/data/data/tx.packages/files/tmp
export TERM=xterm-256color
export LANG=en_US.UTF-8
export EDITOR=vim
```

### /etc/bash.bashrc
```sh
[ -r /etc/profile ] && . /etc/profile
PS1='\u@\h:\w\$ '
```

## Installation

### From GitHub Release
```bash
# Download bootstrap
curl -LO https://github.com/tx-linux/tx-packages/releases/download/v1.0.0/bootstrap.tar.zst

# Create directory structure
mkdir -p /data/data/tx.packages/files/home

# Extract bootstrap
tar --zstd -xf bootstrap.tar.zst -C /data/data/tx.packages/files/
```

### Verification
```bash
# Check SHA-256
cat SHA256SUMS | grep bootstrap.tar.zst | sha256sum -c -

# Verify essential binaries exist
ls -la /data/data/tx.packages/files/usr/bin/{bash,ls,cp,mv,rm,cat,grep,sed,curl}

# Test execution
/data/data/tx.packages/files/usr/bin/bash --version
/data/data/tx.packages/files/usr/bin/ls --version
```

## Environment Setup

After extraction, set up the environment:

```bash
# Source the profile
source /data/data/tx.packages/files/usr/etc/profile

# Or set environment manually
export PATH=/data/data/tx.packages/files/usr/bin:$PATH
export LD_LIBRARY_PATH=/data/data/tx.packages/files/usr/lib:$LD_LIBRARY_PATH

# Verify
which bash
bash --version
```

## Package Management

After bootstrap installation, use the TX Package Manager:

```bash
# Update package list
tx-pkg update

# Install a package
tx-pkg install vim

# Remove a package
tx-pkg remove vim

# List installed packages
tx-pkg list

# Show package info
tx-pkg info openssl
```

## Validation

The bootstrap validation checks:

1. **Directory Structure**: All essential directories exist
2. **Essential Binaries**: coreutils, bash, grep, sed, etc.
3. **Library Dependencies**: Shared libraries are present
4. **Configuration Files**: passwd, hosts, resolv.conf exist
5. **Size Check**: Total size is reasonable (> 1KB)

## Generation Process

The bootstrap is generated automatically by:

1. Building all packages from recipes
2. Creating empty prefix directory
3. Extracting each `.txpkg` into the prefix
4. Generating default configuration files
5. Validating the userspace
6. Computing checksums
7. Creating `bootstrap.tar.zst` with manifest

## Size Estimates

| Package Set | Approximate Size |
|-------------|-----------------|
| Minimal (coreutils + bash + essential libs) | ~15-20 MB |
| Standard (all core utilities + networking) | ~40-60 MB |
| Full (all 80+ packages) | ~100-150 MB |
