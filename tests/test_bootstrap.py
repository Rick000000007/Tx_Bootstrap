"""
Bootstrap Generator Tests

Tests for bootstrap image generation and validation.
"""

import pytest
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.bootstrap import BootstrapGenerator, BootstrapManifest, BootstrapError
from builders.config import BuildConfig
from builders.recipe import Recipe


class TestBootstrapManifest:
    """Test bootstrap manifest."""

    def test_manifest_creation(self):
        """Test creating a bootstrap manifest."""
        manifest = BootstrapManifest(
            name="tx-bootstrap",
            version="1.0.0",
            architecture="aarch64",
            api_level=29,
            packages=["coreutils", "bash", "openssl"],
        )
        assert manifest.name == "tx-bootstrap"
        assert manifest.architecture == "aarch64"
        assert len(manifest.packages) == 3

    def test_manifest_serialization(self):
        """Test manifest serialization."""
        manifest = BootstrapManifest(
            packages=["pkg1"],
            package_versions={"pkg1": "1.0.0-1"},
            total_size=1048576,
            checksum="abc123",
        )
        data = json.loads(manifest.to_json())
        assert data["packages"] == ["pkg1"]
        assert data["total_size"] == 1048576
        assert data["checksum"] == "abc123"


class TestBootstrapValidation:
    """Test bootstrap validation."""

    def test_valid_userspace(self, tmp_path):
        """Test validation of valid userspace."""
        config = BuildConfig()
        config.bootstrap_dir = tmp_path / "bootstrap"
        config.artifacts_dir = tmp_path / "artifacts"
        generator = BootstrapGenerator(config)

        prefix = tmp_path / "prefix"
        (prefix / "bin").mkdir(parents=True)
        (prefix / "lib").mkdir(parents=True)
        (prefix / "bin" / "bash").write_bytes(b"#!/bin/sh\necho hello")
        (prefix / "bin" / "ls").write_bytes(b"#!/bin/sh\necho listing")

        # Should not raise
        generator._validate_userspace(prefix, ["bash", "coreutils"])

    def test_missing_directories(self, tmp_path, caplog):
        """Test warning for missing directories."""
        config = BuildConfig()
        generator = BootstrapGenerator(config)

        prefix = tmp_path / "prefix"
        prefix.mkdir()
        # Create only some essential dirs
        (prefix / "bin").mkdir()

        with caplog.at_level("WARNING"):
            generator._validate_userspace(prefix, [])

        assert any("essential directory" in rec.message for rec in caplog.records)


class TestConfigGeneration:
    """Test configuration file generation."""

    def test_passwd_generation(self, tmp_path):
        """Test passwd file generation."""
        config = BuildConfig()
        generator = BootstrapGenerator(config)

        prefix = tmp_path / "prefix"
        generator._generate_config_files(prefix)

        passwd = prefix / "etc" / "passwd"
        assert passwd.exists()
        content = passwd.read_text()
        assert "root:" in content
        assert "system:" in content

    def test_hosts_generation(self, tmp_path):
        """Test hosts file generation."""
        config = BuildConfig()
        generator = BootstrapGenerator(config)

        prefix = tmp_path / "prefix"
        generator._generate_config_files(prefix)

        hosts = prefix / "etc" / "hosts"
        assert hosts.exists()
        content = hosts.read_text()
        assert "127.0.0.1" in content
        assert "localhost" in content

    def test_resolv_conf(self, tmp_path):
        """Test resolv.conf generation."""
        config = BuildConfig()
        generator = BootstrapGenerator(config)

        prefix = tmp_path / "prefix"
        generator._generate_config_files(prefix)

        resolv = prefix / "etc" / "resolv.conf"
        assert resolv.exists()
        content = resolv.read_text()
        assert "nameserver" in content
