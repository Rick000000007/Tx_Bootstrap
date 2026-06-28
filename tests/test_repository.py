"""
Repository Generator Tests

Tests for repository metadata and index generation.
"""

import pytest
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.repository import RepositoryGenerator, RepositoryMetadata
from builders.config import BuildConfig
from builders.recipe import Recipe


class TestRepositoryMetadata:
    """Test repository metadata."""

    def test_metadata_creation(self):
        """Test creating repository metadata."""
        metadata = RepositoryMetadata(
            name="TX-Test",
            codename="tx-test",
            package_count=100,
            total_size=104857600,
        )
        assert metadata.name == "TX-Test"
        assert metadata.package_count == 100
        assert metadata.total_size == 104857600

    def test_metadata_serialization(self):
        """Test metadata JSON serialization."""
        metadata = RepositoryMetadata(name="TX-Test")
        data = json.loads(metadata.to_json())
        assert data["name"] == "TX-Test"
        assert data["architecture"] == "aarch64"
        assert data["api_level"] == 29


class TestPackageIndex:
    """Test package index generation."""

    def test_packages_index(self, tmp_path):
        """Test Packages index file generation."""
        config = BuildConfig()
        config.repository_dir = tmp_path / "repo"
        config.packages_dir = tmp_path / "pkgs"
        config.packages_dir.mkdir(parents=True)
        config.repository_dir.mkdir(parents=True)

        generator = RepositoryGenerator(config)

        recipes = [
            Recipe(name="pkg1", version="1.0.0", description="Package 1"),
            Recipe(name="pkg2", version="2.0.0", description="Package 2"),
        ]

        pkg_path = generator._generate_packages_index(recipes)
        assert pkg_path.exists()

        content = pkg_path.read_text()
        assert "Package: pkg1" in content
        assert "Package: pkg2" in content
        assert "Version: 1.0.0" in content
        assert "Version: 2.0.0" in content

    def test_json_index(self, tmp_path):
        """Test JSON package index generation."""
        config = BuildConfig()
        config.repository_dir = tmp_path / "repo"
        config.packages_dir = tmp_path / "pkgs"
        config.packages_dir.mkdir(parents=True)
        config.repository_dir.mkdir(parents=True)

        generator = RepositoryGenerator(config)

        recipes = [
            Recipe(name="pkg1", version="1.0.0", category="test", description="Package 1"),
        ]

        pkg_path = generator._generate_packages_json(recipes)
        assert pkg_path.exists()

        data = json.loads(pkg_path.read_text())
        assert data["repository"] == config.repo_name
        assert len(data["packages"]) == 1
        assert data["packages"][0]["name"] == "pkg1"


class TestManifestGeneration:
    """Test repository manifest generation."""

    def test_manifest(self, tmp_path):
        """Test manifest.json generation."""
        config = BuildConfig()
        config.repository_dir = tmp_path / "repo"
        config.packages_dir = tmp_path / "pkgs"
        config.packages_dir.mkdir(parents=True)
        config.repository_dir.mkdir(parents=True)

        generator = RepositoryGenerator(config)

        recipes = [
            Recipe(name="pkg1", version="1.0.0"),
            Recipe(name="pkg2", version="2.0.0"),
        ]

        manifest_path = generator._generate_manifest(recipes)
        assert manifest_path.exists()

        data = json.loads(manifest_path.read_text())
        assert data["package_count"] == 2
        assert "pkg1" in data["packages"]
        assert "pkg2" in data["packages"]


class TestSHA256SUMS:
    """Test SHA256SUMS generation."""

    def test_sha256sums(self, tmp_path):
        """Test SHA256SUMS file generation."""
        config = BuildConfig()
        config.repository_dir = tmp_path / "repo"
        config.repository_dir.mkdir(parents=True)

        # Create some files
        (config.repository_dir / "Packages").write_text("test content 1")
        (config.repository_dir / "Packages.json").write_text('{"test": true}')

        generator = RepositoryGenerator(config)
        sums_path = generator._generate_sha256sums()

        assert sums_path.exists()
        content = sums_path.read_text()
        assert "Packages" in content
        assert "Packages.json" in content

    def test_sha256sums_empty_repo(self, tmp_path):
        """Test SHA256SUMS with empty repository."""
        config = BuildConfig()
        config.repository_dir = tmp_path / "repo"
        config.repository_dir.mkdir(parents=True)

        generator = RepositoryGenerator(config)
        sums_path = generator._generate_sha256sums()

        assert sums_path.exists()
