"""
Source Downloader Module

Handles downloading upstream source tarballs with resume support,
mirror fallback, retry logic, and SHA-256 verification.
"""

import os
import re
import hashlib
import logging
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass
from urllib.parse import urlparse

from .recipe import SourceDefinition

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    file_path: Optional[Path] = None
    checksum_valid: bool = False
    bytes_downloaded: int = 0
    error: Optional[str] = None
    source_url: str = ""


class SourceDownloader:
    """Downloads upstream sources with resume, retry, and verification."""

    DEFAULT_RETRIES = 3
    DEFAULT_TIMEOUT = 300  # 5 minutes
    CHUNK_SIZE = 8192  # 8KB chunks
    USER_AGENT = "curl/8.7.1"

    def __init__(self, downloads_dir: Path, retries: int = DEFAULT_RETRIES):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.retries = retries
        self._progress_callbacks: List[Callable[[str, int, int], None]] = []

    def register_progress_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """Register a callback for download progress.

        Args:
            callback: Function(name, downloaded, total) -> None
        """
        self._progress_callbacks.append(callback)

    def download_source(self, source: SourceDefinition, pkg_name: str) -> DownloadResult:
        """Download a single source with retry and verification."""
        urls = self._get_urls(source)
        filename = self._get_filename(source, pkg_name)
        dest_path = self.downloads_dir / filename

        logger.info(f"Downloading {pkg_name}: {filename}")

        # Check if already downloaded and valid
        if dest_path.exists() and self._verify_checksum(dest_path, source.checksum):
            logger.info(f"Source already downloaded and verified: {filename}")
            return DownloadResult(
                success=True,
                file_path=dest_path,
                checksum_valid=True,
                bytes_downloaded=dest_path.stat().st_size,
                source_url="cached"
            )

        # Try each URL
        last_error = None
        for url in urls:
            for attempt in range(1, self.retries + 1):
                try:
                    result = self._download_file(url, dest_path, filename, source.checksum)
                    if result.success and result.checksum_valid:
                        return result
                    elif result.success and not result.checksum_valid:
                        logger.warning(f"Checksum invalid after download, deleting corrupted file: {dest_path}")
                        if dest_path.exists():
                            dest_path.unlink()
                        # Treat as failure to trigger retry
                        last_error = "Checksum mismatch"
                except urllib.error.HTTPError as e:
                    if e.code == 416 and dest_path.exists():
                        logger.warning("416 Range Not Satisfiable, deleting file and restarting download")
                        dest_path.unlink()
                        # Don't sleep, retry immediately
                        continue
                    last_error = str(e)
                    logger.warning(f"Download attempt {attempt}/{self.retries} failed for {url}: {e}")
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Download attempt {attempt}/{self.retries} failed for {url}: {e}")
                
                if attempt < self.retries:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff

        # All attempts failed
        error_msg = f"Failed to download {filename} from all mirrors"
        if last_error:
            error_msg += f": {last_error}"
        logger.error(error_msg)
        return DownloadResult(success=False, error=error_msg)

    def download_all(self, sources: List[SourceDefinition], pkg_name: str) -> List[DownloadResult]:
        """Download all sources for a package."""
        results = []
        for source in sources:
            result = self.download_source(source, pkg_name)
            results.append(result)
            if not result.success:
                logger.error(f"Failed to download source for {pkg_name}")
                break
        return results

    def _get_urls(self, source: SourceDefinition) -> List[str]:
        """Get all URLs to try (primary + mirrors)."""
        urls = [source.url]
        urls.extend(source.mirror_urls)
        return [u for u in urls if u]

    def _get_filename(self, source: SourceDefinition, pkg_name: str) -> str:
        """Determine the filename for a source."""
        if source.filename:
            return source.filename

        # Extract from URL
        parsed = urlparse(source.url)
        filename = os.path.basename(parsed.path)
        if filename:
            return filename

        # Fallback
        return f"{pkg_name}-source"

    def _download_file(self, url: str, dest_path: Path, display_name: str,
                       expected_checksum: str) -> DownloadResult:
        """Download a single file with resume support."""
        headers = {
            'User-Agent': self.USER_AGENT,
        }

        # Check for partial download
        resume_byte_pos = 0
        if dest_path.exists():
            resume_byte_pos = dest_path.stat().st_size
            headers['Range'] = f'bytes={resume_byte_pos}-'
            logger.debug(f"Resuming download from byte {resume_byte_pos}")

        request = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(request, timeout=self.DEFAULT_TIMEOUT) as response:
            # Check response
            if response.status not in (200, 206):
                return DownloadResult(
                    success=False,
                    error=f"HTTP {response.status}",
                    source_url=url
                )

            # Get total size
            total_size = None
            if 'Content-Length' in response.headers:
                content_length = int(response.headers['Content-Length'])
                if response.status == 206 and 'Content-Range' in response.headers:
                    # Parse total from Content-Range
                    range_header = response.headers['Content-Range']
                    match = re.match(r'bytes \d+-\d+/(\d+)', range_header)
                    if match:
                        total_size = int(match.group(1))
                else:
                    total_size = content_length

            # Determine file mode
            if response.status == 206:
                mode = 'ab'
                downloaded = resume_byte_pos
            else:
                mode = 'wb'
                downloaded = 0
                resume_byte_pos = 0

            # Download
            with open(dest_path, mode) as f:
                while True:
                    chunk = response.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Progress callbacks
                    for callback in self._progress_callbacks:
                        try:
                            callback(display_name, downloaded, total_size or 0)
                        except Exception:
                            pass

        # Verify checksum
        checksum_valid = self._verify_checksum(dest_path, expected_checksum)
        if not checksum_valid and expected_checksum:
            logger.warning(f"Checksum mismatch for {display_name}")
            # Don't delete - user may want to inspect

        return DownloadResult(
            success=True,
            file_path=dest_path,
            checksum_valid=checksum_valid,
            bytes_downloaded=downloaded,
            source_url=url
        )

    def _verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Verify file SHA-256 checksum."""
        if not expected_checksum:
            logger.warning("No checksum provided, skipping verification")
            return True

        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)

        actual_checksum = sha256.hexdigest()
        is_valid = actual_checksum.lower() == expected_checksum.lower()

        if not is_valid:
            logger.error(f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}")

        return is_valid

    def verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Public method to verify a file's checksum."""
        return self._verify_checksum(file_path, expected_checksum)

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def cleanup_old_downloads(self, keep_checksums: Dict[str, str], max_age_days: int = 30) -> int:
        """Remove old downloads not in the keep list."""
        removed = 0
        import time

        current_time = time.time()
        max_age_seconds = max_age_days * 86400

        for file_path in self.downloads_dir.iterdir():
            if not file_path.is_file():
                continue

            # Check if in keep list
            file_checksum = self.calculate_checksum(file_path)
            if file_checksum in keep_checksums.values():
                continue

            # Check age
            file_age = current_time - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                logger.info(f"Removing old download: {file_path.name}")
                file_path.unlink()
                removed += 1

        return removed
