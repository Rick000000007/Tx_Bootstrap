# TX Repository Specification

## Overview

The TX Package Repository is a collection of `.txpkg` files with generated metadata for package discovery and dependency resolution.

## Repository Structure

```
repository/
|-- Packages              # Debian-style package index
|-- Packages.json         # JSON package index
|-- SHA256SUMS            # Checksums for all repository files
|-- manifest.json         # Repository manifest
|-- metadata.json         # Repository metadata
|-- pkgs/                 # Package files
|   |-- pkg1-1.0.0-1.txpkg
|   |-- pkg2-2.0.0-1.txpkg
|   |-- ...
```

## Packages Index

The `Packages` file follows Debian's package index format:

```
Package: bash
Version: 5.2.21-1
Architecture: aarch64
Description: GNU Bourne Again Shell
Homepage: https://www.gnu.org/software/bash/
License: GPL-3.0-or-later
Category: shells
Size: 1234567
SHA256: abc123def456...
Depends: readline, ncurses
Conflicts: bash-light
Provides: sh

Package: coreutils
Version: 9.5-1
Architecture: aarch64
Description: GNU Core Utilities
...
```

### Fields

| Field | Description |
|-------|-------------|
| `Package` | Package name |
| `Version` | Full version (epoch:version-release) |
| `Architecture` | Target architecture |
| `Description` | Short description |
| `Homepage` | Project homepage |
| `License` | SPDX license identifier |
| `Category` | Package category |
| `Size` | Package file size in bytes |
| `SHA256` | SHA-256 checksum of .txpkg file |
| `Depends` | Runtime dependencies |
| `Build-Depends` | Build dependencies |
| `Conflicts` | Conflicting packages |
| `Provides` | Virtual packages provided |
| `Replaces` | Packages replaced |
| `Recommends` | Recommended packages |

## JSON Package Index

The `Packages.json` file provides machine-readable package data:

```json
{
  "repository": "TX-Packages",
  "codename": "tx-main",
  "architecture": "aarch64",
  "api_level": 29,
  "last_updated": "2026-01-15T10:30:00+00:00",
  "package_count": 132,
  "packages": [
    {
      "name": "bash",
      "version": "5.2.21",
      "epoch": 0,
      "release": 1,
      "full_version": "5.2.21-1",
      "architecture": "aarch64",
      "category": "shells",
      "description": "GNU Bourne Again Shell",
      "homepage": "https://www.gnu.org/software/bash/",
      "license": "GPL-3.0-or-later",
      "size": 1234567,
      "sha256": "abc123...",
      "depends": ["readline", "ncurses"],
      "conflicts": [],
      "provides": ["sh"],
      "build_style": "gnu"
    }
  ]
}
```

## SHA256SUMS

The `SHA256SUMS` file contains SHA-256 checksums for all repository files:

```
abc123def456...  Packages
789abcdef012...  Packages.json
def012abc345...  manifest.json
f012abc345de...  metadata.json
345def012abc...  pkgs/bash-5.2.21-1.txpkg
abc789def012...  pkgs/coreutils-9.5-1.txpkg
```

## Repository Manifest

The `manifest.json` contains repository-level metadata:

```json
{
  "repository": "TX-Packages",
  "codename": "tx-main",
  "description": "TX Linux Userspace for Android",
  "version": "1.0.0",
  "architecture": "aarch64",
  "api_level": 29,
  "min_android_version": "10",
  "components": ["main"],
  "last_updated": "2026-01-15T10:30:00+00:00",
  "package_count": 132,
  "packages": ["bash", "coreutils", "..."],
  "categories": ["shells", "core-utils", "networking", "..."],
  "toolchain": {
    "ndk": "/path/to/ndk",
    "clang": "/path/to/clang",
    "target": "aarch64-linux-android"
  }
}
```

## Metadata

The `metadata.json` contains high-level repository statistics:

```json
{
  "name": "TX-Packages",
  "codename": "tx-main",
  "description": "TX Linux Userspace for Android",
  "version": "1.0.0",
  "architecture": "aarch64",
  "api_level": 29,
  "components": ["main"],
  "last_updated": "2026-01-15T10:30:00+00:00",
  "package_count": 132,
  "total_size": 524288000
}
```

## Repository API

### Client Usage

```python
import urllib.request
import json

REPO_URL = "https://github.com/tx-linux/tx-packages/releases/download/v1.0.0"

# Download package index
with urllib.request.urlopen(f"{REPO_URL}/Packages.json") as r:
    index = json.loads(r.read())

# Find package
for pkg in index["packages"]:
    if pkg["name"] == "bash":
        print(f"Found: {pkg['name']} {pkg['full_version']}")
        print(f"SHA256: {pkg['sha256']}")
        
        # Download package
        pkg_url = f"{REPO_URL}/pkgs/{pkg['name']}-{pkg['full_version']}.txpkg"
        urllib.request.urlretrieve(pkg_url, f"{pkg['name']}.txpkg")
```

## Future Enhancements

- **Signed Repository**: GPG/Ed25519 signatures for repository metadata
- **Delta Index**: Incremental package list updates
- **Mirror Lists**: Multiple repository mirrors with failover
- **Search API**: Full-text search over package descriptions
