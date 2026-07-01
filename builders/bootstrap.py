"""
Bootstrap Generator Module

Generates the bootstrap tarball by installing all packages into an empty
prefix, validating the userspace, and creating the bootstrap archive.
"""

import os
import json
import hashlib
import tarfile
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .config import BuildConfig
from .recipe import Recipe
from .packager import PackageGenerator, PackageManifest

logger = logging.getLogger(__name__)


@dataclass
class BootstrapManifest:
    """Bootstrap image manifest."""
    name: str = "tx-bootstrap"
    version: str = "1.0.0"
    architecture: str = "aarch64"
    api_level: int = 29
    build_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    packages: List[str] = field(default_factory=list)
    package_versions: Dict[str, str] = field(default_factory=dict)
    total_size: int = 0
    file_count: int = 0
    checksum: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class BootstrapGenerator:
    """Generates the TX Linux userspace bootstrap image."""

    BOOTSTRAP_PREFIX = "/data/data/tx.packages/files/usr"

    def __init__(self, config: BuildConfig):
        self.config = config
        self.bootstrap_dir = config.bootstrap_dir
        self.rootfs_dir = self.bootstrap_dir / "rootfs"
        self.output_dir = config.output_dir

    def generate(self, recipes: List[Recipe], packages_dir: Path, name: str = "bootstrap") -> Path:
        """
        Generate the bootstrap tarball.

        Args:
            recipes: List of recipes to include in bootstrap
            packages_dir: Directory containing .txpkg files
            name: Name of the generated bootstrap archive

        Returns:
            Path to the generated bootstrap tarball
        """
        logger.info(f"Generating bootstrap {name} with {len(recipes)} packages")

        # Clean and create rootfs directory
        if self.rootfs_dir.exists():
            shutil.rmtree(self.rootfs_dir)
        self.rootfs_dir.mkdir(parents=True, exist_ok=True)

        # Create prefix directories
        prefix = self.rootfs_dir / self.BOOTSTRAP_PREFIX.lstrip('/')
        for subdir in ['bin', 'lib', 'include', 'share', 'etc', 'var', 'tmp', 'opt']:
            (prefix / subdir).mkdir(parents=True, exist_ok=True)

        # Install each package into rootfs
        installed_packages = []
        for recipe in recipes:
            try:
                self._install_package(recipe, packages_dir, prefix)
                installed_packages.append(recipe.name)
                logger.info(f"Installed: {recipe.name}")
            except Exception as e:
                logger.error(f"Failed to install {recipe.name}: {e}")
                # Continue with other packages

        # Generate default configuration files
        self._generate_config_files(prefix)

        # Generate shell configuration
        self._generate_shell_config(prefix)

        # Validate the userspace
        self._validate_userspace(prefix, installed_packages)

        # Generate manifest
        manifest = self._generate_manifest(recipes, prefix, name)

        # Create bootstrap archive
        bootstrap_path = self._create_archive(prefix, manifest, name)

        logger.info(f"Bootstrap {name} generated: {bootstrap_path}")
        return bootstrap_path

    def _install_package(self, recipe: Recipe, packages_dir: Path, prefix: Path) -> None:
        """Install a package into the bootstrap prefix."""
        pkg_file = packages_dir / recipe.name / recipe.pkg_filename
        if not pkg_file.exists():
            # Try alternative naming
            for ext in ['.txpkg', '.txpkg.gz', '.txpkg.zst']:
                alt = packages_dir / f"{recipe.name}-{recipe.full_version.replace(':', '_')}{ext}"
                if not alt.exists():
                    alt = packages_dir / f"{recipe.name}-{recipe.full_version}{ext}"
                if alt.exists():
                    pkg_file = alt
                    break

        if not pkg_file.exists():
            raise BootstrapError(f"Package file not found for {recipe.name}")

        # Extract package
        self._extract_package(pkg_file, prefix)

    def _extract_package(self, pkg_file: Path, prefix: Path) -> None:
        """Extract a .txpkg file into the prefix."""
        with open(pkg_file, 'rb') as f:
            magic = f.read(6)
            f.seek(0)

            if magic == b"TXPKG\x00":
                # zstd format
                f.read(6)  # magic
                f.read(2)  # version
                compressed = f.read()

                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(compressed)

                with tarfile.open(fileobj=__import__('io').BytesIO(decompressed), mode='r') as tf:
                    self._extract_tar_contents(tf, prefix)
            else:
                # Regular tar
                with tarfile.open(pkg_file, 'r') as tf:
                    self._extract_tar_contents(tf, prefix)

    def _extract_tar_contents(self, tf: tarfile.TarFile, prefix: Path) -> None:
        """Extract relevant files from a tar archive to the prefix."""
        for member in tf.getmembers():
            if member.name.startswith(".TXPKG/ROOT/"):
                # Extract to prefix
                target_path = prefix / member.name[len(".TXPKG/ROOT/"):]
                
                if target_path.exists() or target_path.is_symlink():
                    try:
                        if target_path.is_dir() and not target_path.is_symlink():
                            shutil.rmtree(target_path)
                        else:
                            target_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to remove existing path {target_path}: {e}")

                target_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    if member.issym():
                        # Create symbolic link
                        target_path.symlink_to(member.linkname)
                    elif member.islnk():
                        # Create hard link
                        if member.linkname.startswith(".TXPKG/ROOT/"):
                            link_target = prefix / member.linkname[len(".TXPKG/ROOT/"):]
                        else:
                            link_target = prefix / member.linkname.lstrip("/")
                        os.link(link_target, target_path)
                    elif member.isreg():
                        # Regular file
                        f = tf.extractfile(member)
                        if f:
                            target_path.write_bytes(f.read())
                            os.chmod(target_path, member.mode)
                    elif member.isdir():
                        target_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to extract member {member.name}: {e}")

    def _generate_config_files(self, prefix: Path) -> None:
        """Generate default system configuration files."""
        etc = prefix / "etc"
        etc.mkdir(parents=True, exist_ok=True)

        # passwd
        (etc / "passwd").write_text("""root:x:0:0:root:/root:/bin/bash
system:x:1000:1000:system:/data/data/tx.packages/files/home:/bin/bash
""")

        # group
        (etc / "group").write_text("""root:x:0:
system:x:1000:
""")

        # hosts
        (etc / "hosts").write_text("""127.0.0.1       localhost
::1             localhost ip6-localhost ip6-loopback
""")

        # resolv.conf
        (etc / "resolv.conf").write_text("""nameserver 8.8.8.8
nameserver 8.8.4.4
""")

        # nsswitch.conf
        (etc / "nsswitch.conf").write_text("""passwd:     files
 group:      files
 hosts:      files dns
 networks:   files
""")

        # profile
        (etc / "profile").write_text(f"""# TX Linux system-wide profile
export PATH={self.BOOTSTRAP_PREFIX}/bin:{self.BOOTSTRAP_PREFIX}/sbin:$PATH
export LD_LIBRARY_PATH={self.BOOTSTRAP_PREFIX}/lib:$LD_LIBRARY_PATH
export HOME=/data/data/tx.packages/files/home
export TMPDIR=/data/data/tx.packages/files/tmp
export TERM=xterm-256color
export LANG=en_US.UTF-8
export EDITOR=vim
""")

    def _generate_shell_config(self, prefix: Path) -> None:
        """Generate shell configuration files."""
        etc = prefix / "etc"

        # bash.bashrc
        (etc / "bash.bashrc").write_text("""# TX Linux bash configuration
[ -r /etc/profile ] && . /etc/profile
PS1='\\u@\\h:\\w\\$ '
""")

        # Inputrc
        (etc / "inputrc").write_text("""# TX Linux readline configuration
set editing-mode emacs
set bell-style none
""")

    def _validate_userspace(self, prefix: Path, expected_packages: List[str]) -> None:
        """Validate the generated userspace."""
        logger.info("Validating userspace...")

        # Check essential directories
        essential_dirs = ['bin', 'lib', 'include', 'share', 'etc']
        for d in essential_dirs:
            dir_path = prefix / d
            if not dir_path.exists():
                logger.warning(f"Missing essential directory: {d}")

        # Check essential binaries
        essential_bins = ['bash', 'sh', 'ls', 'cp', 'mv', 'rm', 'cat', 'echo', 'grep', 'sed']
        bin_dir = prefix / "bin"
        for binary in essential_bins:
            bin_path = bin_dir / binary
            if not bin_path.exists():
                # Check libexec or other locations
                found = False
                for root, dirs, files in os.walk(prefix):
                    if binary in files:
                        found = True
                        break
                if not found:
                    logger.warning(f"Missing essential binary: {binary}")

        # Check library dependencies (basic)
        lib_dir = prefix / "lib"
        if lib_dir.exists():
            libs = list(lib_dir.glob("*.so*"))
            logger.info(f"Found {len(libs)} shared libraries")

        # Validate total size
        total_size = sum(
            f.stat().st_size for f in prefix.rglob("*") if f.is_file()
        )
        logger.info(f"Total userspace size: {total_size / (1024*1024):.1f} MB")

        if total_size < 1024:  # Less than 1KB is suspicious
            raise BootstrapError("Userspace appears empty or incomplete")

    def _generate_manifest(self, recipes: List[Recipe], prefix: Path, name: str) -> BootstrapManifest:
        """Generate the bootstrap manifest."""
        manifest = BootstrapManifest(
            name=name,
            architecture=self.config.target_arch,
            api_level=self.config.min_api_level,
            packages=[r.name for r in recipes],
            package_versions={r.name: r.full_version for r in recipes},
        )

        # Calculate stats
        file_count = 0
        total_size = 0
        for f in prefix.rglob("*"):
            if f.is_file():
                file_count += 1
                total_size += f.stat().st_size

        manifest.total_size = total_size
        manifest.file_count = file_count

        # Calculate checksum
        hasher = hashlib.sha256()
        for f in sorted(prefix.rglob("*"), key=lambda x: str(x.relative_to(prefix))):
            if f.is_file() and not f.is_symlink():
                rel_path = str(f.relative_to(prefix))
                hasher.update(rel_path.encode())
                hasher.update(f.read_bytes())
            elif f.is_symlink():
                rel_path = str(f.relative_to(prefix))
                hasher.update(rel_path.encode())
                hasher.update(os.readlink(f).encode())

        manifest.checksum = hasher.hexdigest()

        return manifest

    def _create_archive(self, prefix: Path, manifest: BootstrapManifest, name: str = "bootstrap") -> Path:
        """Create the bootstrap archive."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Paths
        bootstrap_tar = self.output_dir / f"{name}.tar.gz"
        bootstrap_json = self.output_dir / f"{name}.json"
        sha256_file = self.output_dir / "SHA256SUMS"

        # Write manifest JSON
        bootstrap_json.write_text(manifest.to_json())
        logger.info(f"Manifest written: {bootstrap_json}")

        # Create tar.gz archive
        logger.info(f"Creating {name}.tar.gz...")
        with tarfile.open(bootstrap_tar, 'w:gz', compresslevel=9) as tf:
            tf.add(bootstrap_json, arcname="bootstrap.json")
            for item in prefix.rglob("*"):
                if item.is_file() or item.is_dir() or item.is_symlink():
                    arcname = str(item.relative_to(prefix))
                    tf.add(item, arcname=arcname, recursive=False)

        # Calculate SHA-256
        sha256 = hashlib.sha256(bootstrap_tar.read_bytes()).hexdigest()

        # Read existing checksums
        checksums = {}
        if sha256_file.exists():
            for line in sha256_file.read_text().splitlines():
                if line.strip():
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        checksums[parts[1]] = parts[0]

        # Add/update new checksums
        checksums[bootstrap_tar.name] = sha256
        checksums[bootstrap_json.name] = hashlib.sha256(bootstrap_json.read_bytes()).hexdigest()

        # Write all back
        sha256sums_content = "".join(f"{chsum}  {filename}\n" for filename, chsum in sorted(checksums.items()))
        sha256_file.write_text(sha256sums_content)

        logger.info(f"SHA256: {sha256}")
        logger.info(f"Bootstrap archive: {bootstrap_tar}")
        logger.info(f"Bootstrap size: {bootstrap_tar.stat().st_size / (1024*1024):.1f} MB")

        return bootstrap_tar


class BootstrapError(Exception):
    """Exception raised for bootstrap generation errors."""
    pass
