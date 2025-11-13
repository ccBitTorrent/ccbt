"""Tests for BEP 47 model additions.

Tests specifically for FileInfo BEP 47 fields, AttributeConfig, and FileCheckpoint.
"""

from __future__ import annotations

import hashlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]

from ccbt.models import AttributeConfig, DiskConfig, FileCheckpoint, FileInfo


class TestAttributeConfig:
    """Test AttributeConfig model."""

    def test_default_values(self):
        """Test default values for AttributeConfig."""
        config = AttributeConfig()

        assert config.preserve_attributes is True
        assert config.skip_padding_files is True
        assert config.verify_file_sha1 is False
        assert config.apply_symlinks is True
        assert config.apply_executable_bit is True
        assert config.apply_hidden_attr is True

    def test_custom_values(self):
        """Test setting custom values."""
        config = AttributeConfig(
            preserve_attributes=False,
            skip_padding_files=False,
            verify_file_sha1=True,
            apply_symlinks=False,
            apply_executable_bit=False,
            apply_hidden_attr=False,
        )

        assert config.preserve_attributes is False
        assert config.skip_padding_files is False
        assert config.verify_file_sha1 is True
        assert config.apply_symlinks is False
        assert config.apply_executable_bit is False
        assert config.apply_hidden_attr is False


class TestDiskConfigWithAttributes:
    """Test DiskConfig integration with AttributeConfig."""

    def test_disk_config_includes_attribute_config(self):
        """Test that DiskConfig includes AttributeConfig."""
        disk_config = DiskConfig()

        assert hasattr(disk_config, "attributes")
        assert isinstance(disk_config.attributes, AttributeConfig)

    def test_disk_config_custom_attributes(self):
        """Test setting custom attribute config in DiskConfig."""
        attr_config = AttributeConfig(verify_file_sha1=True)
        disk_config = DiskConfig(attributes=attr_config)

        assert disk_config.attributes.verify_file_sha1 is True


class TestFileCheckpointBEP47:
    """Test FileCheckpoint with BEP 47 fields."""

    def test_file_checkpoint_with_attributes(self):
        """Test FileCheckpoint with BEP 47 attributes."""
        checkpoint = FileCheckpoint(
            path="/path/to/file.txt",
            size=1000,
            exists=True,
            attributes="x",  # Executable
            symlink_path=None,
            file_sha1=None,
        )

        assert checkpoint.attributes == "x"
        assert checkpoint.symlink_path is None
        assert checkpoint.file_sha1 is None

    def test_file_checkpoint_with_symlink(self):
        """Test FileCheckpoint with symlink."""
        checkpoint = FileCheckpoint(
            path="/path/to/link.lnk",
            size=0,
            exists=True,
            attributes="l",
            symlink_path="/target/path",
            file_sha1=None,
        )

        assert checkpoint.attributes == "l"
        assert checkpoint.symlink_path == "/target/path"

    def test_file_checkpoint_with_sha1(self):
        """Test FileCheckpoint with file SHA-1."""
        sha1_hash = hashlib.sha1(b"test").digest()  # nosec B324

        checkpoint = FileCheckpoint(
            path="/path/to/file.txt",
            size=4,
            exists=True,
            attributes=None,
            symlink_path=None,
            file_sha1=sha1_hash,
        )

        assert checkpoint.file_sha1 == sha1_hash
        assert len(checkpoint.file_sha1) == 20

    def test_file_checkpoint_backward_compatible(self):
        """Test FileCheckpoint without BEP 47 fields is backward compatible."""
        checkpoint = FileCheckpoint(
            path="/path/to/file.txt",
            size=1000,
            exists=True,
        )

        assert checkpoint.attributes is None
        assert checkpoint.symlink_path is None
        assert checkpoint.file_sha1 is None


class TestFileInfoBEP47Properties:
    """Test FileInfo BEP 47 properties comprehensively."""

    def test_file_info_all_properties(self):
        """Test all BEP 47 properties."""
        file_info = FileInfo(
            name="test",
            length=100,
            attributes="plxh",  # All attributes
            symlink_path="/target",
            file_sha1=b"\x00" * 20,
        )

        assert file_info.is_padding is True
        assert file_info.is_symlink is True
        assert file_info.is_executable is True
        assert file_info.is_hidden is True

    def test_file_info_partial_properties(self):
        """Test FileInfo with partial attributes."""
        file_info = FileInfo(
            name="test",
            length=100,
            attributes="px",  # Padding + executable
        )

        assert file_info.is_padding is True
        assert file_info.is_executable is True
        assert file_info.is_symlink is False
        assert file_info.is_hidden is False

