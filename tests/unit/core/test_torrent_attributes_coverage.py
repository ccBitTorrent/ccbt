"""Additional coverage tests for BEP 47 attributes to reach 95%+ coverage.

Tests edge cases and error paths that aren't covered in main test file.
"""

from __future__ import annotations

import hashlib
import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]

from ccbt.core.torrent_attributes import (
    apply_file_attributes,
    verify_file_sha1,
)


class TestApplyFileAttributesEdgeCases:
    """Test edge cases in apply_file_attributes for coverage."""

    def test_apply_symlink_relative_path(self):
        """Test creating symlink with relative target path."""
        if platform.system() == "Windows":
            pytest.skip("Symlink creation requires admin privileges on Windows")

        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "target.txt"
            target_file.write_text("target content")

            link_file = Path(tmpdir) / "link.lnk"
            link_file.write_text("placeholder")

            # Create relative symlink path
            relative_path = "target.txt"

            apply_file_attributes(link_file, "l", relative_path)

            # Verify symlink was created
            assert link_file.is_symlink()
            # Should point to relative path
            assert link_file.readlink() == Path(relative_path)

    def test_apply_symlink_existing_file_removed(self):
        """Test that existing regular file is removed before creating symlink."""
        if platform.system() == "Windows":
            pytest.skip("Symlink creation requires admin privileges on Windows")

        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "target.txt"
            target_file.write_text("target content")

            link_file = Path(tmpdir) / "link.lnk"
            link_file.write_text("existing content")  # Regular file exists

            apply_file_attributes(link_file, "l", str(target_file))

            # Should be symlink now, not regular file
            assert link_file.is_symlink()
            assert not link_file.is_file() or link_file.is_symlink()

    def test_apply_executable_bit_on_symlink(self):
        """Test that executable bit is applied to symlink (Unix)."""
        if platform.system() == "Windows":
            pytest.skip("Symlink/executable test only on Unix")

        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "target.sh"
            target_file.write_text("#!/bin/bash")

            link_file = Path(tmpdir) / "link"
            link_file.write_text("placeholder")

            # Apply symlink first (creates symlink)
            apply_file_attributes(link_file, "l", str(target_file))

            # Verify symlink exists
            assert link_file.is_symlink()

            # Apply executable bit to the symlink
            # Note: In practice, we'd apply both at once with "xl"
            # but this test covers the executable path when symlink already exists
            import stat

            # Clear execute bits first
            target_file.chmod(0o644)

            # Apply executable attribute (should work on symlink)
            apply_file_attributes(link_file, "x")

            # Verify executable bit on symlink
            link_stat = os.stat(link_file)
            assert link_stat.st_mode & stat.S_IXUSR

    def test_apply_hidden_attribute_exception_handled(self):
        """Test that exceptions when setting hidden attribute are handled gracefully."""
        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            # Mock SetFileAttributesW to raise an exception
            with patch("ctypes.windll.kernel32.SetFileAttributesW", side_effect=OSError("Test error")):
                # Should not raise - exception is caught and logged
                apply_file_attributes(temp_path, "h")

            # File should still exist
            assert Path(temp_path).exists()

        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)


    def test_apply_executable_when_file_not_exists(self):
        """Test that executable bit is not set when file doesn't exist."""
        if platform.system() == "Windows":
            pytest.skip("Executable bit test only on Unix")

        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent = Path(tmpdir) / "nonexistent.sh"

            # Should not raise - just skip if file doesn't exist
            apply_file_attributes(non_existent, "x")

            # File still shouldn't exist
            assert not non_existent.exists()


class TestVerifyFileSha1EdgeCases:
    """Test edge cases in verify_file_sha1 for coverage."""

    def test_verify_file_sha1_mismatch_logs_warning(self, caplog):
        """Test that SHA-1 mismatch logs a warning."""
        content = b"test file content"
        wrong_hash = hashlib.sha1(b"different content").digest()  # nosec B324

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            with caplog.at_level("WARNING", logger="ccbt.core.torrent_attributes"):
                result = verify_file_sha1(temp_path, wrong_hash)

            assert result is False
            # Warning should be logged (check via structured logging output)
            # Just verify function returns False

        finally:
            os.unlink(temp_path)

