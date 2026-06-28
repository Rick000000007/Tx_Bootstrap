"""
Repository Generator Module

Generates TX-Packages repository metadata including package index,
SHA256SUMS, manifests, and repository versions.
"""

import os
import json
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .config import BuildConfig
from .recipe import Recipe

logger = logging.getLogger(__name__)


@dataclass
class RepositoryMetadata:
    """Repository metadata structure."""
    name: str = "TX-Packages"
    codename: str = "tx-main"
    description: str = "TX Linux Userspace for Android"
    version: str = "1.0.0"
    architecture: str = "aarch64"
    api_level: int = 29
    components: List[str] = field(default_factory=lambda: ["main"])
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    package_count: int = 0
    total_size: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class RepositoryGenerator:
    """Generates TX-Packages repository metadata and index."""

    def __init__(self, config: BuildConfig):
        self.config = config
        self.repository_dir = config.repository_dir
        self.packages_dir = config.packages_dir

    def generate(self, recipes: List[Recipe]) -> Path:
        """
        Generate the complete repository.

        Args:
            recipes: List of all recipes/packages in the repository

        Returns:
            Path to the repository directory
        """
        logger.info(f"Generating repository with {len(recipes)} packages")

        self.repository_dir.mkdir(parents=True, exist_ok=True)

        # Generate package index
        self._generate_packages_index(recipes)

        # Generate JSON package index
        self._generate_packages_json(recipes)

        # Generate SHA256SUMS
        self._generate_sha256sums()

        # Generate repository manifest
        self._generate_manifest(recipes)

        # Generate repository metadata
        self._generate_metadata(recipes)

        # Copy packages to repository
        self._copy_packages_to_repo()

        logger.info(f"Repository generated: {self.repository_dir}")
        return self.repository_dir

    def _generate_packages_index(self, recipes: List[Recipe]) -> Path:
        """Generate the Packages index file (Debian-style)."""
        packages_file = self.repository_dir / "Packages"

        lines = []
        for recipe in recipes:
            # Find the actual package file
            pkg_file = self._find_package_file(recipe)
            size = pkg_file.stat().st_size if pkg_file else 0
            checksum = self._file_checksum(pkg_file) if pkg_file else ""

            lines.append(f"Package: {recipe.name}")
            lines.append(f"Version: {recipe.full_version}")
            lines.append(f"Architecture: {self.config.target_arch}")
            lines.append(f"Description: {recipe.description}")
            lines.append(f"Homepage: {recipe.homepage}")
            lines.append(f"License: {recipe.license}")
            lines.append(f"Category: {recipe.category}")
            lines.append(f"Size: {size}")
            lines.append(f"SHA256: {checksum}")

            if recipe.depends:
                lines.append(f"Depends: {', '.join(recipe.depends)}")
            if recipe.makedepends:
                lines.append(f"Build-Depends: {', '.join(recipe.makedepends)}")
            if recipe.conflicts:
                lines.append(f"Conflicts: {', '.join(recipe.conflicts)}")
            if recipe.provides:
                lines.append(f"Provides: {', '.join(recipe.provides)}")
            if recipe.replaces:
                lines.append(f"Replaces: {', '.join(recipe.replaces)}")
            if recipe.recommends:
                lines.append(f"Recommends: {', '.join(recipe.recommends)}")

            lines.append("")  # Blank line between packages

        content = '\n'.join(lines)
        packages_file.write_text(content)
        logger.info(f"Packages index written: {packages_file}")
        return packages_file

    def _generate_packages_json(self, recipes: List[Recipe]) -> Path:
        """Generate JSON package index."""
        packages_json = self.repository_dir / "Packages.json"

        packages = []
        for recipe in recipes:
            pkg_file = self._find_package_file(recipe)
            size = pkg_file.stat().st_size if pkg_file else 0
            checksum = self._file_checksum(pkg_file) if pkg_file else ""

            packages.append({
                "name": recipe.name,
                "version": recipe.version,
                "epoch": recipe.epoch,
                "release": recipe.release,
                "full_version": recipe.full_version,
                "architecture": self.config.target_arch,
                "category": recipe.category,
                "description": recipe.description,
                "homepage": recipe.homepage,
                "license": recipe.license,
                "size": size,
                "sha256": checksum,
                "depends": recipe.depends,
                "makedepends": recipe.makedepends,
                "conflicts": recipe.conflicts,
                "provides": recipe.provides,
                "replaces": recipe.replaces,
                "recommends": recipe.recommends,
                "build_style": recipe.build_style,
            })

        content = json.dumps({
            "repository": self.config.repo_name,
            "codename": self.config.repo_codename,
            "architecture": self.config.target_arch,
            "api_level": self.config.min_api_level,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "package_count": len(packages),
            "packages": packages,
        }, indent=2)

        packages_json.write_text(content)
        logger.info(f"JSON packages index written: {packages_json}")
        return packages_json

    def _generate_sha256sums(self) -> Path:
        """Generate SHA256SUMS file for all repository files."""
        sha256_file = self.repository_dir / "SHA256SUMS"

        checksums = []
        for file_path in sorted(self.repository_dir.rglob("*")):
            if file_path.is_file() and file_path.name != "SHA256SUMS":
                rel_path = file_path.relative_to(self.repository_dir)
                checksum = self._file_checksum(file_path)
                checksums.append(f"{checksum}  {rel_path}")

        content = '\n'.join(sorted(checksums)) + '\n'
        sha256_file.write_text(content)
        logger.info(f"SHA256SUMS written: {sha256_file}")
        return sha256_file

    def _generate_manifest(self, recipes: List[Recipe]) -> Path:
        """Generate repository manifest."""
        manifest_file = self.repository_dir / "manifest.json"

        manifest = {
            "repository": self.config.repo_name,
            "codename": self.config.repo_codename,
            "description": self.config.repo_description,
            "version": "1.0.0",
            "architecture": self.config.target_arch,
            "api_level": self.config.min_api_level,
            "min_android_version": self.config.android_version,
            "components": self.config.repo_components,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "package_count": len(recipes),
            "packages": [r.name for r in recipes],
            "categories": sorted(set(r.category for r in recipes)),
            "toolchain": {
                "ndk": str(self.config.ndk_path) if self.config.ndk_path else "",
                "clang": str(self.config.clang_path) if self.config.clang_path else "",
                "target": self.config.target_triple,
            },
        }

        manifest_file.write_text(json.dumps(manifest, indent=2))
        logger.info(f"Manifest written: {manifest_file}")
        return manifest_file

    def _generate_metadata(self, recipes: List[Recipe]) -> Path:
        """Generate repository metadata file."""
        metadata_file = self.repository_dir / "metadata.json"

        total_size = 0
        for recipe in recipes:
            pkg_file = self._find_package_file(recipe)
            if pkg_file:
                total_size += pkg_file.stat().st_size

        metadata = RepositoryMetadata(
            name=self.config.repo_name,
            codename=self.config.repo_codename,
            description=self.config.repo_description,
            architecture=self.config.target_arch,
            api_level=self.config.min_api_level,
            components=self.config.repo_components,
            package_count=len(recipes),
            total_size=total_size,
        )

        metadata_file.write_text(metadata.to_json())
        logger.info(f"Metadata written: {metadata_file}")
        return metadata_file

    def _copy_packages_to_repo(self) -> None:
        """Copy or link packages into the repository."""
        pkgs_dir = self.repository_dir / "pkgs"
        pkgs_dir.mkdir(parents=True, exist_ok=True)

        for pkg_file in self.packages_dir.rglob("*.txpkg*"):
            dest = pkgs_dir / pkg_file.name
            if not dest.exists():
                shutil.copy2(pkg_file, dest)
                logger.debug(f"Copied package: {pkg_file.name}")

    def _find_package_file(self, recipe: Recipe) -> Optional[Path]:
        """Find the generated package file for a recipe."""
        # Check various possible locations
        search_dirs = [
            self.packages_dir / recipe.name,
            self.packages_dir,
            self.repository_dir / "pkgs",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for ext in ['.txpkg', '.txpkg.gz', '.txpkg.zst']:
                pattern = f"{recipe.name}-{recipe.full_version}{ext}"
                pkg_file = search_dir / pattern
                if pkg_file.exists():
                    return pkg_file

        return None

    def _file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def update(self, new_packages: List[Recipe]) -> Path:
        """Update the repository with new/updated packages."""
        return self.generate(new_packages)
