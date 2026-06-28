"""
TX Package Format Tests

Tests for .txpkg generation, verification, and manifest handling.
"""

import pytest
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.packager import PackageGenerator, PackageManifest
from builders.config import BuildConfig
from builders.recipe import Recipe


class TestPackageManifest:
    """Test package manifest structure."""

    def test_manifest_creation(self):
        """Test creating a basic manifest."""
        manifest = PackageManifest(
            name="testpkg",
            version="1.0.0",
            architecture="aarch64",
            description="Test package",
        )
        assert manifest.name == "testpkg"
        assert manifest.version == "1.0.0"
        assert manifest.architecture == "aarch64"

    def test_manifest_serialization(self):
        """Test manifest serialization to dict."""
        manifest = PackageManifest(
            name="testpkg",
            version="1.0.0",
            depends=["liba", "libb"],
        )
        data = manifest.to_dict()
        assert data["name"] == "testpkg"
        assert data["depends"] == ["liba", "libb"]

    def test_manifest_json(self):
        """Test manifest JSON serialization."""
        manifest = PackageManifest(name="testpkg", version="1.0.0")
        json_str = manifest.to_json()
        data = json.loads(json_str)
        assert data["name"] == "testpkg"
        assert "build_date" in data


class TestPackageGenerator:
    """Test package generation."""

    def test_generator_setup(self, tmp_path):
        """Test generator initialization."""
        config = BuildConfig()
        config.packages_dir = tmp_path / "packages"
        generator = PackageGenerator(config)
        assert generator.packages_dir.exists()

    def test_manifest_from_recipe(self, tmp_path):
        """Test creating manifest from recipe."""
        config = BuildConfig()
        config.packages_dir = tmp_path / "packages"
        generator = PackageGenerator(config)

        recipe = Recipe(
            name="testpkg",
            version="1.0.0",
            depends=["libdep"],
            conflicts=["oldpkg"],
        )

        install_prefix = tmp_path / "install"
        install_prefix.mkdir()
        (install_prefix / "bin").mkdir()
        (install_prefix / "bin" / "testtool").write_bytes(b"#!/bin/sh\necho hello")

        manifest = generator._create_manifest(recipe, install_prefix)

        assert manifest.name == "testpkg"
        assert "libdep" in manifest.depends
        assert "oldpkg" in manifest.conflicts
        assert len(manifest.files) > 0


class TestControlFile:
    """Test control file generation."""

    def test_control_format(self):
        """Test control file format."""
        config = BuildConfig()
        generator = PackageGenerator(config)

        manifest = PackageManifest(
            name="testpkg",
            version="1.0.0",
            release=1,
            architecture="aarch64",
            description="Test package",
            homepage="https://example.com",
            license="MIT",
            maintainer="Test <test@example.com>",
            total_size=10240,
            depends=["liba"],
            conflicts=["oldpkg"],
            provides=["testpkg-dev"],
        )

        control = generator._generate_control(manifest)

        assert "Package: testpkg" in control
        assert "Architecture: aarch64" in control
        assert "Depends: liba" in control
        assert "Conflicts: oldpkg" in control
        assert "Provides: testpkg-dev" in control


class TestTXPKGMagic:
    """Test .txpkg file format magic bytes."""

    def test_magic_constant(self):
        """Test magic bytes constant."""
        from builders.packager import TXPKG_MAGIC, TXPKG_VERSION
        assert TXPKG_MAGIC == b"TXPKG\x00"
        assert TXPKG_VERSION == 1
