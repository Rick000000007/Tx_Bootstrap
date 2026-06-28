"""
Package Generator Module

Generates TX Package files (.txpkg) from built artifacts.
Implements the TX Package format specification.
"""

import os
import io
import json
import hashlib
import tarfile
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .config import BuildConfig
from .recipe import Recipe

logger = logging.getLogger(__name__)


TXPKG_MAGIC = b"TXPKG\x00"
TXPKG_VERSION = 1


@dataclass
class PackageManifest:
    """TX Package manifest structure."""
    # Identity
    name: str
    version: str
    epoch: int = 0
    release: int = 1
    architecture: str = "aarch64"
    category: str = "misc"

    # Metadata
    description: str = ""
    homepage: str = ""
    license: str = ""
    maintainer: str = ""
    upstream_author: str = ""

    # Dependencies
    depends: List[str] = field(default_factory=list)
    makedepends: List[str] = field(default_factory=list)
    optdepends: Dict[str, str] = field(default_factory=dict)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    recommends: List[str] = field(default_factory=list)

    # Files
    files: Dict[str, str] = field(default_factory=dict)  # path -> checksum
    directories: List[str] = field(default_factory=list)
    symlinks: Dict[str, str] = field(default_factory=dict)  # link -> target
    total_size: int = 0
    file_count: int = 0

    # Build info
    built_by: str = "tx-packages"
    build_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    build_toolchain: str = "llvm"
    build_api_level: int = 29

    # Verification
    checksums: Dict[str, str] = field(default_factory=dict)

    # Scriptlets
    pre_install: str = ""
    post_install: str = ""
    pre_remove: str = ""
    post_remove: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class PackageGenerator:
    """Generates .txpkg files from built artifacts."""

    COMPRESSION_FORMATS = {
        'gz': ('w:gz', 9),
        'bz2': ('w:bz2', 9),
        'xz': ('w:xz', 9),
        'zst': ('w', 'zstd'),
    }

    def __init__(self, config: BuildConfig):
        self.config = config
        self.packages_dir = config.packages_dir
        self.packages_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, recipe: Recipe, install_prefix: Path) -> Path:
        """
        Generate a .txpkg file from built artifacts.

        Args:
            recipe: The recipe used to build the package
            install_prefix: Directory containing installed files

        Returns:
            Path to the generated .txpkg file
        """
        logger.info(f"Generating package: {recipe.name} {recipe.full_version}")

        # Create manifest
        manifest = self._create_manifest(recipe, install_prefix)

        # Create package archive
        pkg_path = self.packages_dir / manifest.name / manifest.pkg_filename
        pkg_path.parent.mkdir(parents=True, exist_ok=True)

        # Build the .txpkg file
        self._write_txpkg(pkg_path, manifest, install_prefix)

        logger.info(f"Package generated: {pkg_path}")
        return pkg_path

    def _create_manifest(self, recipe: Recipe, install_prefix: Path) -> PackageManifest:
        """Create a package manifest from a recipe and install prefix."""
        manifest = PackageManifest(
            name=recipe.name,
            version=recipe.version,
            epoch=recipe.epoch,
            release=recipe.release,
            architecture=self.config.target_arch,
            category=recipe.category,
            description=recipe.description,
            homepage=recipe.homepage,
            license=recipe.license,
            maintainer=recipe.maintainer or self.config.maintainer,
            upstream_author=recipe.upstream_author,
            depends=recipe.depends,
            makedepends=recipe.makedepends,
            optdepends=recipe.optdepends,
            conflicts=recipe.conflicts,
            provides=recipe.provides,
            replaces=recipe.replaces,
            recommends=recipe.recommends,
            pre_install=recipe.pre_install_script,
            post_install=recipe.post_install_script,
            pre_remove=recipe.pre_remove_script,
            post_remove=recipe.post_remove_script,
            build_api_level=self.config.min_api_level,
        )

        # Scan installed files
        if install_prefix.exists():
            for root, dirs, files in os.walk(install_prefix):
                # Directories
                for d in dirs:
                    dir_path = Path(root) / d
                    rel_path = str(dir_path.relative_to(install_prefix))
                    if rel_path not in manifest.directories:
                        manifest.directories.append(rel_path)

                # Files
                for f in files:
                    file_path = Path(root) / f
                    rel_path = str(file_path.relative_to(install_prefix))

                    # Check for symlinks
                    if file_path.is_symlink():
                        target = os.readlink(file_path)
                        manifest.symlinks[rel_path] = target
                    else:
                        # Calculate checksum
                        checksum = self._file_checksum(file_path)
                        manifest.files[rel_path] = checksum
                        manifest.total_size += file_path.stat().st_size
                        manifest.file_count += 1

        # Calculate manifest checksum
        manifest_data = manifest.to_json().encode('utf-8')
        manifest.checksums['manifest'] = hashlib.sha256(manifest_data).hexdigest()

        return manifest

    def _write_txpkg(self, pkg_path: Path, manifest: PackageManifest,
                     install_prefix: Path) -> None:
        """Write the .txpkg archive file."""
        compression = self.config.pkg_compression

        if compression == 'zst':
            self._write_txpkg_zstd(pkg_path, manifest, install_prefix)
        else:
            self._write_txpkg_tar(pkg_path, manifest, install_prefix, compression)

    def _write_txpkg_tar(self, pkg_path: Path, manifest: PackageManifest,
                         install_prefix: Path, compression: str) -> None:
        """Write .txpkg using tar compression."""
        format_str, level = self.COMPRESSION_FORMATS[compression]

        with tarfile.open(pkg_path, format_str, compresslevel=level) as tf:
            # Write manifest
            manifest_data = manifest.to_json().encode('utf-8')
            manifest_info = tarfile.TarInfo(name=".TXPKG/MANIFEST")
            manifest_info.size = len(manifest_data)
            tf.addfile(manifest_info, io.BytesIO(manifest_data))

            # Write control metadata
            control = self._generate_control(manifest)
            control_data = control.encode('utf-8')
            control_info = tarfile.TarInfo(name=".TXPKG/CONTROL")
            control_info.size = len(control_data)
            tf.addfile(control_info, io.BytesIO(control_data))

            # Write files
            self._add_files_to_tar(tf, install_prefix, manifest)

    def _write_txpkg_zstd(self, pkg_path: Path, manifest: PackageManifest,
                          install_prefix: Path) -> None:
        """Write .txpkg using zstd compression."""
        try:
            import zstandard as zstd
        except ImportError:
            # Fallback to gzip
            logger.warning("zstandard not available, falling back to gzip")
            self._write_txpkg_tar(pkg_path.with_suffix('.txpkg.gz'), manifest, install_prefix, 'gz')
            return

        # Create uncompressed tar in memory first
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w') as tf:
            # Write manifest
            manifest_data = manifest.to_json().encode('utf-8')
            manifest_info = tarfile.TarInfo(name=".TXPKG/MANIFEST")
            manifest_info.size = len(manifest_data)
            tf.addfile(manifest_info, io.BytesIO(manifest_data))

            # Write control metadata
            control = self._generate_control(manifest)
            control_data = control.encode('utf-8')
            control_info = tarfile.TarInfo(name=".TXPKG/CONTROL")
            control_info.size = len(control_data)
            tf.addfile(control_info, io.BytesIO(control_data))

            # Write files
            self._add_files_to_tar(tf, install_prefix, manifest)

        # Compress with zstd
        cctx = zstd.ZstdCompressor(level=self.config.pkg_compression_level)
        compressed = cctx.compress(tar_buffer.getvalue())

        # Write magic header + version + compressed data
        with open(pkg_path, 'wb') as f:
            f.write(TXPKG_MAGIC)
            f.write(TXPKG_VERSION.to_bytes(2, 'big'))
            f.write(compressed)

    def _add_files_to_tar(self, tf: tarfile.TarFile, install_prefix: Path,
                          manifest: PackageManifest) -> None:
         """Add installed files to the tar archive."""
         prefix = ".TXPKG/ROOT"

         if not install_prefix.exists():
             return

         # Clean any absolute symlinks pointing to build tree
         self._clean_absolute_symlinks(install_prefix)

         for root, dirs, files in os.walk(install_prefix):
             for filename in files:
                 file_path = Path(root) / filename
                 rel_path = file_path.relative_to(install_prefix)
                 arcname = f"{prefix}/{rel_path}"

                 try:
                     tf.add(file_path, arcname=arcname)
                 except Exception as e:
                     logger.warning(f"Failed to add {rel_path} to package: {e}")

    def _clean_absolute_symlinks(self, install_prefix: Path) -> None:
        """Find and fix absolute symlinks pointing to the build-time destination directory."""
        if not install_prefix.exists():
            return

        runtime_prefix = "/data/data/tx.packages/files/usr"

        for root, dirs, files in os.walk(install_prefix, followlinks=False):
            for name in files + dirs:
                path = Path(root) / name
                if path.is_symlink():
                    try:
                        target = os.readlink(path)
                        # Check if target points to host build paths or DESTDIR
                        if str(install_prefix) in target or "/home/runner/work/" in target:
                            build_prefix_str = str(install_prefix)
                            if target.startswith(build_prefix_str):
                                suffix = target[len(build_prefix_str):]
                                cleaned_target = f"{runtime_prefix}{suffix}"
                            else:
                                idx = target.find("/data/data/tx.packages/files/usr")
                                if idx != -1:
                                    cleaned_target = target[idx:]
                                else:
                                    cleaned_target = os.path.basename(target)
                            
                            path.unlink()
                            path.symlink_to(cleaned_target)
                            logger.info(f"Fixed absolute symlink: {path.relative_to(install_prefix)} -> {cleaned_target}")
                    except Exception as e:
                        logger.warning(f"Failed to clean symlink {path}: {e}")

    def _generate_control(self, manifest: PackageManifest) -> str:
        """Generate Debian-like control file for compatibility."""
        lines = [
            f"Package: {manifest.name}",
            f"Version: {manifest.epoch}:{manifest.version}-{manifest.release}",
            f"Architecture: {manifest.architecture}",
            f"Description: {manifest.description}",
            f"Homepage: {manifest.homepage}",
            f"License: {manifest.license}",
            f"Maintainer: {manifest.maintainer}",
            f"Installed-Size: {manifest.total_size // 1024}",
            f"Build-Date: {manifest.build_date}",
        ]

        if manifest.depends:
            lines.append(f"Depends: {', '.join(manifest.depends)}")
        if manifest.makedepends:
            lines.append(f"Build-Depends: {', '.join(manifest.makedepends)}")
        if manifest.conflicts:
            lines.append(f"Conflicts: {', '.join(manifest.conflicts)}")
        if manifest.provides:
            lines.append(f"Provides: {', '.join(manifest.provides)}")
        if manifest.replaces:
            lines.append(f"Replaces: {', '.join(manifest.replaces)}")
        if manifest.recommends:
            lines.append(f"Recommends: {', '.join(manifest.recommends)}")

        return '\n'.join(lines) + '\n'

    def _file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def verify_package(self, pkg_path: Path) -> bool:
        """Verify a .txpkg file integrity."""
        logger.info(f"Verifying package: {pkg_path}")

        try:
            with open(pkg_path, 'rb') as f:
                magic = f.read(6)
                if magic == TXPKG_MAGIC:
                    # zstd format
                    version = int.from_bytes(f.read(2), 'big')
                    compressed_data = f.read()

                    import zstandard as zstd
                    dctx = zstd.ZstdDecompressor()
                    decompressed = dctx.decompress(compressed_data)

                    with tarfile.open(fileobj=io.BytesIO(decompressed), mode='r') as tf:
                        return self._verify_tar_contents(tf)
                else:
                    # Regular tar
                    with tarfile.open(pkg_path, 'r') as tf:
                        return self._verify_tar_contents(tf)
        except Exception as e:
            logger.error(f"Package verification failed: {e}")
            return False

    def _verify_tar_contents(self, tf: tarfile.TarFile) -> bool:
        """Verify contents of a tar archive."""
        has_manifest = False
        has_control = False

        for member in tf.getmembers():
            if member.name == ".TXPKG/MANIFEST":
                has_manifest = True
                f = tf.extractfile(member)
                if f:
                    manifest_data = f.read()
                    try:
                        manifest = json.loads(manifest_data)
                        logger.debug(f"Manifest: {manifest.get('name')} {manifest.get('version')}")
                    except json.JSONDecodeError:
                        logger.error("Invalid manifest JSON")
                        return False
            elif member.name == ".TXPKG/CONTROL":
                has_control = True

        if not has_manifest:
            logger.error("Package missing manifest")
            return False

        logger.info("Package verification passed")
        return True


# Monkey-patch manifest for pkg_filename property
PackageManifest.pkg_filename = property(
    lambda self: (
        f"{self.name}-{self.epoch}_{self.version}-{self.release}.txpkg"
        if self.epoch and self.epoch > 0
        else f"{self.name}-{self.version}-{self.release}.txpkg"
    )
)
