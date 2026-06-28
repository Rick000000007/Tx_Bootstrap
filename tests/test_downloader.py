"""
Source Downloader Tests

Tests for HTTP download, resume, retry, and checksum verification.
"""

import pytest
import hashlib
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "builders"))

from builders.downloader import SourceDownloader, DownloadResult
from builders.recipe import SourceDefinition


class TestDownloaderSetup:
    """Test downloader setup and configuration."""

    def test_default_retries(self, tmp_path):
        """Test default retry count."""
        dl = SourceDownloader(tmp_path)
        assert dl.retries == 3

    def test_custom_retries(self, tmp_path):
        """Test custom retry count."""
        dl = SourceDownloader(tmp_path, retries=5)
        assert dl.retries == 5

    def test_downloads_dir_created(self, tmp_path):
        """Test downloads directory is created."""
        dl_dir = tmp_path / "new_downloads"
        assert not dl_dir.exists()
        SourceDownloader(dl_dir)
        assert dl_dir.exists()


class TestChecksumVerification:
    """Test checksum verification."""

    def test_verify_valid_checksum(self, tmp_path):
        """Test valid checksum passes."""
        dl = SourceDownloader(tmp_path)
        test_file = tmp_path / "test.txt"
        test_content = b"test content for checksum"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        assert dl.verify_checksum(test_file, expected_hash)

    def test_verify_invalid_checksum(self, tmp_path):
        """Test invalid checksum fails."""
        dl = SourceDownloader(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        assert not dl.verify_checksum(test_file, "invalid_checksum")

    def test_calculate_checksum(self, tmp_path):
        """Test checksum calculation."""
        dl = SourceDownloader(tmp_path)
        test_file = tmp_path / "test.txt"
        test_content = b"test content"
        test_file.write_bytes(test_content)

        calculated = dl.calculate_checksum(test_file)
        expected = hashlib.sha256(test_content).hexdigest()
        assert calculated == expected

    def test_empty_file_checksum(self, tmp_path):
        """Test checksum of empty file."""
        dl = SourceDownloader(tmp_path)
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        calculated = dl.calculate_checksum(test_file)
        expected = hashlib.sha256(b"").hexdigest()
        assert calculated == expected


class TestSourceDefinition:
    """Test source definition handling."""

    def test_source_with_checksum(self):
        """Test source definition with checksum."""
        src = SourceDefinition(
            url="https://example.com/file.tar.gz",
            checksum="abc123def456",
        )
        assert src.url == "https://example.com/file.tar.gz"
        assert src.checksum == "abc123def456"

    def test_source_with_mirrors(self):
        """Test source definition with mirror URLs."""
        src = SourceDefinition(
            url="https://example.com/file.tar.gz",
            checksum="abc123",
            mirror_urls=["https://mirror1.example.com/file.tar.gz",
                        "https://mirror2.example.com/file.tar.gz"],
        )
        assert len(src.mirror_urls) == 2

    def test_source_without_checksum(self):
        """Test source with empty checksum (no verification)."""
        src = SourceDefinition(
            url="https://example.com/file.tar.gz",
            checksum="",
        )
        assert src.checksum == ""


class TestFilenameExtraction:
    """Test filename extraction from URLs."""

    def test_standard_url(self):
        """Extract filename from standard URL."""
        dl = SourceDownloader(Path("/tmp"))
        src = SourceDefinition(url="https://example.com/path/to/file.tar.gz", checksum="")
        assert dl._get_filename(src, "testpkg") == "file.tar.gz"

    def test_url_with_query(self):
        """Extract filename from URL with query string."""
        dl = SourceDownloader(Path("/tmp"))
        src = SourceDefinition(
            url="https://example.com/file.tar.gz?download=1",
            checksum="",
        )
        assert dl._get_filename(src, "testpkg") == "file.tar.gz"

    def test_explicit_filename(self):
        """Use explicitly provided filename."""
        dl = SourceDownloader(Path("/tmp"))
        src = SourceDefinition(
            url="https://example.com/download?id=123",
            checksum="",
            filename="package-1.0.0.tar.gz",
        )
        assert dl._get_filename(src, "testpkg") == "package-1.0.0.tar.gz"

    def test_url_without_path(self):
        """Handle URL without path."""
        dl = SourceDownloader(Path("/tmp"))
        src = SourceDefinition(url="https://example.com/", checksum="")
        assert dl._get_filename(src, "testpkg") == "testpkg-source"
