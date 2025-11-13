"""Expanded tests for ccbt.config.config_backup to achieve 95%+ coverage.

Covers missing lines:
- Uncompressed backup creation (91-92)
- Exception handling (104-107, 167-170, 198-200)
- Error paths (140, 150)
- List backups error handling (198-200)
- Other missing methods
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import toml

from ccbt.config.config_backup import ConfigBackup

pytestmark = [pytest.mark.unit]


class TestConfigBackupExpanded:
    """Expanded tests for ConfigBackup class."""

    def test_create_backup_uncompressed(self, tmp_path):
        """Test create_backup without compression (lines 91-92)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        backup = ConfigBackup(backup_dir)
        success, backup_path, messages = backup.create_backup(config_file, compress=False)
        
        assert success is True
        assert backup_path is not None
        assert backup_path.exists()
        assert not backup_path.suffix.endswith(".gz")  # Not compressed
        assert "Backup created" in messages[0]
        
        # Verify backup content
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        assert "metadata" in backup_data
        assert "config" in backup_data

    def test_create_backup_exception(self, tmp_path):
        """Test create_backup exception handling (lines 104-107)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        backup = ConfigBackup(backup_dir)
        
        # Mock _load_config_file to raise exception
        with patch.object(backup, "_load_config_file", side_effect=Exception("Load error")):
            success, backup_path, messages = backup.create_backup(config_file)
            
            assert success is False
            assert backup_path is None
            assert len(messages) > 0
            assert "Backup creation failed" in messages[0]

    def test_restore_backup_no_target_file(self, tmp_path):
        """Test restore_backup when target file cannot be determined (line 140)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create a backup file with missing metadata
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        backup_data = {
            "metadata": {},  # Missing config_file
            "config": {"network": {"listen_port": 6881}},
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        success, messages = backup.restore_backup(backup_file)
        
        assert success is False
        assert "Cannot determine target file" in messages[0]

    def test_restore_backup_pre_restore_backup_fails(self, tmp_path):
        """Test restore_backup when pre-restore backup fails (line 150)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create backup file
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        target_file = tmp_path / "ccbt.toml"
        target_file.write_text("[network]\nlisten_port = 6881\n")
        
        backup_data = {
            "metadata": {"config_file": str(target_file)},
            "config": {"network": {"listen_port": 6882}},
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        
        # Mock create_backup to fail
        with patch.object(backup, "create_backup", return_value=(False, None, ["Backup failed"])):
            success, messages = backup.restore_backup(backup_file, create_backup=True)
            
            assert success is False
            assert "Failed to create pre-restore backup" in messages[0]

    def test_restore_backup_exception(self, tmp_path):
        """Test restore_backup exception handling (lines 167-170)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        # Create invalid backup file
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            f.write("invalid json")
        
        backup = ConfigBackup(backup_dir)
        success, messages = backup.restore_backup(backup_file)
        
        assert success is False
        assert "Restore failed" in messages[0]

    def test_list_backups_exception(self, tmp_path):
        """Test list_backups exception handling (lines 198-200)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create a backup file that will cause error when loading
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            f.write("invalid json")
        
        backup = ConfigBackup(backup_dir)
        
        # Should handle exception and continue
        backups = backup.list_backups()
        
        # Invalid backup should be skipped
        assert isinstance(backups, list)

    def test_auto_backup_metadata_update_exception(self, tmp_path):
        """Test auto_backup exception when updating metadata (lines 233-234)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[network]\nlisten_port = 6881\n")
        
        backup = ConfigBackup(backup_dir)
        
        # Mock _load_backup_file to raise exception after backup created
        with patch.object(backup, "_load_backup_file", side_effect=[{"metadata": {}, "config": {}}, Exception("Load error")]):
            success, backup_path, messages = backup.auto_backup(config_file)
            
            # Should still succeed even if metadata update fails
            assert success is True
            assert backup_path is not None

    def test_cleanup_auto_backups_exception(self, tmp_path):
        """Test _cleanup_auto_backups exception handling (lines 258-269)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        
        # Mock list_backups to raise exception
        with patch.object(backup, "list_backups", side_effect=Exception("List error")):
            # Should handle exception gracefully
            backup._cleanup_auto_backups(5)

    def test_cleanup_auto_backups_unlink_exception(self, tmp_path):
        """Test _cleanup_auto_backups exception when unlink fails."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create backup files
        for i in range(5):
            backup_file = backup_dir / f"ccbt_config_2024010{i}_000000.json.gz"
            backup_data = {
                "metadata": {
                    "timestamp": f"2024-01-0{i}T00:00:00+00:00",
                    "description": "Automatic backup before configuration change",
                },
                "config": {},
            }
            with gzip.open(backup_file, "wt", encoding="utf-8") as f:
                json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        
        # Mock unlink to raise exception for some files
        original_unlink = Path.unlink
        call_count = [0]
        
        def failing_unlink(self):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise PermissionError("Permission denied")
            return original_unlink(self)
        
        with patch.object(Path, "unlink", failing_unlink):
            # Should handle unlink exceptions gracefully
            backup._cleanup_auto_backups(max_backups=2)

    def test_validate_backup_missing_metadata(self, tmp_path):
        """Test validate_backup with missing metadata (line 291)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        backup_data = {
            "config": {"network": {"listen_port": 6881}},  # Missing metadata
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        is_valid, errors = backup.validate_backup(backup_file)
        
        assert is_valid is False
        assert "missing metadata section" in errors[0].lower()

    def test_validate_backup_missing_config(self, tmp_path):
        """Test validate_backup with missing config (line 294)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        backup_data = {
            "metadata": {"timestamp": "2024-01-01T00:00:00+00:00"},  # Missing config
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        is_valid, errors = backup.validate_backup(backup_file)
        
        assert is_valid is False
        assert "missing config section" in errors[0].lower()

    def test_validate_backup_missing_required_field(self, tmp_path):
        """Test validate_backup with missing required metadata field (line 303)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        backup_data = {
            "metadata": {
                "timestamp": "2024-01-01T00:00:00+00:00",
                # Missing version and config_file
            },
            "config": {},
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        is_valid, errors = backup.validate_backup(backup_file)
        
        assert is_valid is False
        assert any("missing required field" in err for err in errors)

    def test_validate_backup_config_validation_fails(self, tmp_path):
        """Test validate_backup when config validation fails (line 308)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        backup_data = {
            "metadata": {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "version": "1.0",
                "config_file": "/path/to/config.toml",
            },
            "config": {"invalid": "config"},
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        
        # Mock validate_migrated_config to fail
        with patch("ccbt.config.config_backup.ConfigMigrator.validate_migrated_config", return_value=(False, ["Validation failed"])):
            is_valid, errors = backup.validate_backup(backup_file)
            
            assert is_valid is False
            assert "validation failed" in errors[0].lower()

    def test_validate_backup_not_found(self, tmp_path):
        """Test validate_backup with non-existent file (line 283)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        is_valid, errors = backup.validate_backup(backup_dir / "nonexistent.json.gz")
        
        assert is_valid is False
        assert "not found" in errors[0].lower()

    def test_save_backup_file_uncompressed(self, tmp_path):
        """Test _save_backup_file without compression (lines 373-374)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json"  # No .gz
        backup_data = {
            "metadata": {"timestamp": "2024-01-01T00:00:00+00:00"},
            "config": {},
        }
        
        backup = ConfigBackup(backup_dir)
        backup._save_backup_file(backup_file, backup_data)
        
        # Verify file was saved
        assert backup_file.exists()
        with open(backup_file, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == backup_data

    def test_get_hostname_exception(self, tmp_path):
        """Test _get_hostname exception handling (lines 386-387)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        
        # Mock socket.gethostname to raise exception
        with patch("socket.gethostname", side_effect=Exception("Hostname error")):
            hostname = backup._get_hostname()
            
            assert hostname == "unknown"

    def test_cleanup_old_backups_days_zero(self, tmp_path):
        """Test cleanup_old_backups with days <= 0 (lines 400-401)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        removed_count, messages = backup.cleanup_old_backups(days=0)
        
        assert removed_count == 0
        assert len(messages) == 0

    def test_cleanup_old_backups_exception(self, tmp_path):
        """Test cleanup_old_backups exception handling (lines 417-418)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        
        # Mock glob to raise exception
        with patch.object(Path, "glob", side_effect=Exception("Glob error")):
            removed_count, messages = backup.cleanup_old_backups(days=30)
            
            assert removed_count == 0
            assert len(messages) > 0
            assert "Cleanup failed" in messages[0]

    def test_cleanup_old_backups_unlink_exception(self, tmp_path):
        """Test cleanup_old_backups exception when unlink fails (lines 414-415)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create old backup file
        backup_file = backup_dir / "ccbt_config_20200101_000000.json.gz"
        backup_data = {"metadata": {}, "config": {}}
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        # Make file appear old
        import time
        old_time = time.time() - (31 * 24 * 60 * 60)  # 31 days ago
        os.utime(backup_file, (old_time, old_time))
        
        backup = ConfigBackup(backup_dir)
        
        # Mock unlink to raise exception
        with patch.object(Path, "unlink", side_effect=PermissionError("Permission denied")):
            removed_count, messages = backup.cleanup_old_backups(days=30)
            
            assert removed_count == 0
            assert len(messages) > 0
            assert any("Failed to remove" in msg for msg in messages)

    def test_init_default_backup_dir(self, tmp_path, monkeypatch):
        """Test __init__ with default backup_dir (line 31)."""
        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        backup = ConfigBackup()
        
        # Should use default ~/.config/ccbt/backups
        expected_dir = tmp_path / ".config" / "ccbt" / "backups"
        assert backup.backup_dir == expected_dir
        assert expected_dir.exists()

    def test_create_backup_file_not_found(self, tmp_path):
        """Test create_backup with non-existent file (line 55)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        non_existent = tmp_path / "nonexistent.toml"
        
        success, backup_path, messages = backup.create_backup(non_existent)
        
        assert success is False
        assert backup_path is None
        assert "not found" in messages[0].lower()

    def test_restore_backup_file_not_found(self, tmp_path):
        """Test restore_backup with non-existent backup file (line 128)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup = ConfigBackup(backup_dir)
        non_existent = backup_dir / "nonexistent.json.gz"
        
        success, messages = backup.restore_backup(non_existent)
        
        assert success is False
        assert "not found" in messages[0].lower()

    def test_restore_backup_success(self, tmp_path):
        """Test restore_backup success path (lines 153-165)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create backup file
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        target_file = tmp_path / "ccbt.toml"
        target_file.write_text("[network]\nlisten_port = 6881\n")  # Existing file
        
        backup_data = {
            "metadata": {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "version": "1.0",
                "config_file": str(target_file),
            },
            "config": {"network": {"listen_port": 6882}},
        }
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        success, messages = backup.restore_backup(backup_file, create_backup=False)
        
        assert success is True
        assert len(messages) > 0
        assert "restored" in messages[0].lower()
        
        # Verify config was restored
        with open(target_file, "r", encoding="utf-8") as f:
            restored_data = toml.load(f)
        assert restored_data["network"]["listen_port"] == 6882

    def test_validate_backup_exception(self, tmp_path):
        """Test validate_backup exception handling (lines 310-313)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json.gz"
        # Create corrupted backup
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            f.write("invalid json {[")
        
        backup = ConfigBackup(backup_dir)
        is_valid, errors = backup.validate_backup(backup_file)
        
        assert is_valid is False
        assert "validation failed" in errors[0].lower()

    def test_load_config_file_json(self, tmp_path):
        """Test _load_config_file with JSON file (line 326)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        config_file = tmp_path / "config.json"
        config_data = {"network": {"listen_port": 6881}}
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)
        
        backup = ConfigBackup(backup_dir)
        loaded_data = backup._load_config_file(config_file)
        
        assert loaded_data == config_data

    def test_save_config_file_json(self, tmp_path):
        """Test _save_config_file with JSON file (lines 338-340)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        config_file = tmp_path / "config.json"
        config_data = {"network": {"listen_port": 6881}}
        
        backup = ConfigBackup(backup_dir)
        backup._save_config_file(config_file, config_data)
        
        # Verify file was saved as JSON
        with open(config_file, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == config_data

    def test_save_config_file_toml(self, tmp_path):
        """Test _save_config_file with TOML file (lines 342-344)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        config_file = tmp_path / "config.toml"
        config_data = {"network": {"listen_port": 6881}}
        
        backup = ConfigBackup(backup_dir)
        backup._save_config_file(config_file, config_data)
        
        # Verify file was saved as TOML
        with open(config_file, "r", encoding="utf-8") as f:
            loaded_data = toml.load(f)
        assert loaded_data == config_data

    def test_load_backup_file_uncompressed(self, tmp_path):
        """Test _load_backup_file without compression (lines 359-360)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        backup_file = backup_dir / "ccbt_config_20240101_000000.json"  # No .gz
        backup_data = {
            "metadata": {"timestamp": "2024-01-01T00:00:00+00:00"},
            "config": {},
        }
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        backup = ConfigBackup(backup_dir)
        loaded_data = backup._load_backup_file(backup_file)
        
        assert loaded_data == backup_data

    def test_cleanup_old_backups_success(self, tmp_path):
        """Test cleanup_old_backups success path (lines 412-413)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create old backup file
        backup_file = backup_dir / "ccbt_config_20200101_000000.json.gz"
        backup_data = {"metadata": {}, "config": {}}
        with gzip.open(backup_file, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)
        
        # Make file appear old (31 days ago)
        import time
        old_time = time.time() - (31 * 24 * 60 * 60)
        os.utime(backup_file, (old_time, old_time))
        
        backup = ConfigBackup(backup_dir)
        removed_count, messages = backup.cleanup_old_backups(days=30)
        
        assert removed_count == 1
        assert len(messages) > 0
        assert not backup_file.exists()

