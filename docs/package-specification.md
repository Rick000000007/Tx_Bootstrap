# TX Package (.txpkg) Specification

## Overview

TX Packages (`.txpkg`) are the native package format for the TX Linux userspace. They are zstd-compressed tar archives containing a manifest, control metadata, and the package file tree.

## File Format

### Magic Header

| Offset | Size | Value | Description |
|--------|------|-------|-------------|
| 0x00 | 6 bytes | `TXPKG\0` | Magic identifier |
| 0x06 | 2 bytes | `0x0001` | Format version (big-endian) |

### Archive Structure

After the 8-byte header, the archive contains zstd-compressed tar data:

```
bootstrap.tar.zst
|-- .TXPKG/
|   |-- MANIFEST       # JSON package manifest
|   |-- CONTROL        # Debian-style control file
|-- .TXPKG/ROOT/       # Package file tree
|   |-- bin/
|   |   |-- executable
|   |-- lib/
|   |   |-- library.so
|   |-- share/
|   |   |-- doc/
|   |   |   |-- package/
```

## Manifest Format

The manifest is a JSON file (`MANIFEST`) containing:

```json
{
  "name": "package-name",
  "version": "1.0.0",
  "epoch": 0,
  "release": 1,
  "architecture": "aarch64",
  "category": "core-utils",
  "description": "Package description",
  "homepage": "https://example.com",
  "license": "MIT",
  "maintainer": "TX-Packages <packages@tx.dev>",
  "upstream_author": "Author Name",
  "depends": ["libfoo", "libbar"],
  "makedepends": ["cmake"],
  "optdepends": {"feature": "Description"},
  "conflicts": ["oldpkg"],
  "provides": ["virtual-pkg"],
  "replaces": ["oldpkg"],
  "recommends": ["optional-pkg"],
  "files": {
    "bin/executable": "sha256:abc123...",
    "lib/library.so": "sha256:def456..."
  },
  "directories": ["bin", "lib", "share"],
  "symlinks": {
    "bin/alt-name": "bin/executable"
  },
  "total_size": 102400,
  "file_count": 42,
  "built_by": "tx-packages",
  "build_date": "2026-01-15T10:30:00+00:00",
  "build_toolchain": "llvm",
  "build_api_level": 29,
  "checksums": {
    "manifest": "sha256:..."
  },
  "pre_install": "",
  "post_install": "",
  "pre_remove": "",
  "post_remove": ""
}
```

### Manifest Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Package name |
| `version` | string | Yes | Upstream version |
| `epoch` | int | No | Package epoch |
| `release` | int | No | Package release |
| `architecture` | string | Yes | Target architecture |
| `category` | string | Yes | Package category |
| `description` | string | No | Package description |
| `homepage` | string | No | Project homepage |
| `license` | string | No | SPDX license identifier |
| `maintainer` | string | No | Package maintainer |
| `depends` | [string] | No | Runtime dependencies |
| `makedepends` | [string] | No | Build dependencies |
| `optdepends` | {string: string} | No | Optional dependencies |
| `conflicts` | [string] | No | Conflicting packages |
| `provides` | [string] | No | Virtual packages provided |
| `replaces` | [string] | No | Packages replaced |
| `recommends` | [string] | No | Recommended packages |
| `files` | {string: string} | Yes | File path -> checksum |
| `directories` | [string] | Yes | Directory list |
| `symlinks` | {string: string} | No | Link -> target |
| `total_size` | int | Yes | Total installed size (bytes) |
| `file_count` | int | Yes | Number of files |
| `built_by` | string | No | Build system identifier |
| `build_date` | string | No | ISO 8601 build timestamp |
| `build_toolchain` | string | No | Toolchain used |
| `build_api_level` | int | No | Android API level |
| `checksums` | {string: string} | No | Additional checksums |

## Control File Format

The control file (`CONTROL`) uses Debian's control format for compatibility:

```
Package: package-name
Version: 0:1.0.0-1
Architecture: aarch64
Description: Package description
Homepage: https://example.com
License: MIT
Maintainer: TX-Packages <packages@tx.dev>
Installed-Size: 100
Build-Date: 2026-01-15T10:30:00+00:00
Depends: libfoo, libbar
Conflicts: oldpkg
Provides: virtual-pkg
Replaces: oldpkg
Recommends: optional-pkg
```

## File Tree Layout

Package files are stored under `.TXPKG/ROOT/` with paths relative to the installation prefix (`/data/data/tx.packages/files/usr`):

```
.TXPKG/ROOT/
|-- bin/              # Executables
|-- sbin/             # System executables
|-- lib/              # Libraries
|-- include/          # Header files
|-- share/
|   |-- doc/          # Documentation
|   |-- man/          # Manual pages
|   |-- info/         # Info pages
|-- etc/              # Configuration files
```

## Compression

Packages use zstd compression at level 19 for maximum compression ratio while maintaining reasonable decompression speed.

| Format | Extension | Compression |
|--------|-----------|-------------|
| zstd (default) | `.txpkg` | zstd level 19 |
| gzip (fallback) | `.txpkg.gz` | gzip level 9 |

## Verification

Package verification checks:
1. Magic header matches `TXPKG\0`
2. Version is supported (currently 1)
3. Archive is valid zstd-compressed tar
4. Manifest exists and is valid JSON
5. Control file exists
6. File tree is non-empty

## Package Installation

Installation extracts `.TXPKG/ROOT/` to the target prefix:

```bash
# Extract package
python3 -c "
import zstandard, tarfile, io
with open('package.txpkg', 'rb') as f:
    magic = f.read(6)      # TXPKG\0
    version = f.read(2)    # 0x0001
    compressed = f.read()
    dctx = zstandard.ZstdDecompressor()
    decompressed = dctx.decompress(compressed)
    tf = tarfile.open(fileobj=io.BytesIO(decompressed), mode='r')
    for m in tf.getmembers():
        if m.name.startswith('.TXPKG/ROOT/'):
            target = m.name[len('.TXPKG/ROOT/'):]
            tf.extract(m, path='/data/data/tx.packages/files/usr/' + target)
"
```

## Future Enhancements

- **Signatures**: Ed25519 package signatures for verification
- **Delta Packages**: Binary diff packages for updates
- **Multi-arch**: Support for x86_64 and other architectures
- **Reproducible Builds**: Deterministic output bit-for-bit
