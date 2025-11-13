"""Tests for configuration migration, backup, and diff functionality."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from ccbt.config.config_migration import ConfigMigrator
from ccbt.config.config_backup import ConfigBackup
from ccbt.config.config_diff import ConfigDiff
from ccbt.models import Config


class TestConfigMigrator:
    """Test configuration migration functionality."""

    def test_detect_version_current(self):
        """Test version detection for current version."""
        config_data = {
            "limits": {"global_down_kib": 0},
            "_version": "1.0.0"
        }
        
        version = ConfigMigrator.detect_version(config_data)
        assert version == "1.0.0"

    def test_detect_version_metadata(self):
        """Test version detection from metadata (line 47)."""
        config_data = {
            "metadata": {"version": "1.0.0"},
            "network": {"listen_port": 6881}
        }
        
        version = ConfigMigrator.detect_version(config_data)
        assert version == "1.0.0"

    def test_detect_version_from_limits(self):
        """Test version detection from limits structure (line 51)."""
        config_data = {
            "limits": {"global_down_kib": 0}
        }
        
        version = ConfigMigrator.detect_version(config_data)
        assert version == "1.0.0"

    def test_detect_version_legacy(self):
        """Test version detection for legacy version."""
        config_data = {
            "network": {"global_down_kib": 0}
        }
        
        version = ConfigMigrator.detect_version(config_data)
        assert version == "0.9.0"

    def test_detect_version_old(self):
        """Test version detection for old version."""
        config_data = {
            "network": {"listen_port": 6881}
        }
        
        version = ConfigMigrator.detect_version(config_data)
        assert version == "0.8.0"

    def test_migrate_config_same_version(self):
        """Test migration when already at target version."""
        config_data = {
            "limits": {"global_down_kib": 0},
            "_version": "1.0.0"
        }
        
        migrated, log = ConfigMigrator.migrate_config(config_data, "1.0.0")
        
        assert migrated == config_data
        assert "already at version" in log[0]

    def test_migrate_config_0_8_0_to_1_0_0(self):
        """Test migration from 0.8.0 to 1.0.0."""
        config_data = {
            "network": {"listen_port": 6881},
            "disk": {"hash_workers": 4}
        }
        
        migrated, log = ConfigMigrator.migrate_config(config_data, "1.0.0")
        
        # Should have added missing sections
        assert "limits" in migrated
        assert "security" in migrated
        assert "ml" in migrated
        
        # Should preserve existing data
        assert migrated["network"]["listen_port"] == 6881
        assert migrated["disk"]["hash_workers"] == 4
        
        # Should have version metadata
        assert migrated["_version"] == "1.0.0"
        assert "_migration_log" in migrated

    def test_migrate_config_0_9_0_to_1_0_0(self):
        """Test migration from 0.9.0 to 1.0.0."""
        config_data = {
            "network": {
                "listen_port": 6881,
                "global_down_kib": 1000,
                "global_up_kib": 500,
            },
            "disk": {"hash_workers": 4}
        }
        
        migrated, log = ConfigMigrator.migrate_config(config_data, "1.0.0")
        
        # Should move limits from network to limits section
        assert "limits" in migrated
        assert migrated["limits"]["global_down_kib"] == 1000
        assert migrated["limits"]["global_up_kib"] == 500
        
        # Should remove limits from network
        assert "global_down_kib" not in migrated["network"]
        assert "global_up_kib" not in migrated["network"]
        
        # Should preserve other network settings
        assert migrated["network"]["listen_port"] == 6881

    def test_get_migration_path_0_9_to_1_0(self):
        """Test getting migration path for 0.9.0 -> 1.0.0 (line 121)."""
        path = ConfigMigrator._get_migration_path("0.9.0", "1.0.0")
        assert path == ["0.9.0"]

    def test_get_migration_path_unknown(self):
        """Test getting migration path for unknown version pair (line 122)."""
        # Test a version pair that doesn't have a defined path
        path = ConfigMigrator._get_migration_path("1.0.0", "2.0.0")
        assert path == []  # Should return empty list for unknown paths

    def test_migrate_0_8_0_to_1_0_0_direct(self):
        """Test direct migration from 0.8.0 to 1.0.0 (lines 134-167)."""
        config_data = {
            "network": {"listen_port": 6881},
            "disk": {"hash_workers": 4}
        }
        
        migrated = ConfigMigrator._migrate_0_8_0_to_1_0_0(config_data)
        
        # Should have added missing sections
        assert "limits" in migrated
        assert "security" in migrated
        assert "ml" in migrated
        
        # Should preserve existing data
        assert migrated["network"]["listen_port"] == 6881
        assert migrated["disk"]["hash_workers"] == 4
        
        # Check defaults
        assert migrated["limits"]["global_down_kib"] == 0
        assert migrated["security"]["enable_encryption"] is False
        assert migrated["ml"]["peer_selection_enabled"] is False

    def test_migrate_file_success(self, tmp_path):
        """Test successful file migration."""
        config_file = tmp_path / "test_config.toml"
        
        # Create test config
        config_data = {
            "network": {"listen_port": 6881},
            "disk": {"hash_workers": 4}
        }
        
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Migrate
        success, log = ConfigMigrator.migrate_file(config_file, backup=True)
        
        assert success
        assert "migrated successfully" in log[-1]
        
        # Check backup was created
        backup_file = config_file.with_suffix(".toml.backup")
        assert backup_file.exists()

    def test_migrate_file_json(self, tmp_path):
        """Test migrating JSON config file (lines 241, 252, 264)."""
        config_file = tmp_path / "test_config.json"
        
        # Create test config
        config_data = {
            "network": {"listen_port": 6881},
            "disk": {"hash_workers": 4}
        }
        
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        
        # Migrate with backup
        success, log = ConfigMigrator.migrate_file(config_file, backup=True)
        
        assert success
        assert "migrated successfully" in log[-1]
        
        # Check backup was created
        backup_file = config_file.with_suffix(".json.backup")
        assert backup_file.exists()
        
        # Check migrated file is valid JSON
        with open(config_file, encoding="utf-8") as f:
            migrated_data = json.load(f)
        assert "_version" in migrated_data

    def test_migrate_file_exception(self, tmp_path):
        """Test migrate_file with exception handling (lines 273-276)."""
        config_file = tmp_path / "test_config.toml"
        
        # Create test config
        config_data = {"network": {"listen_port": 6881}}
        
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Mock open to raise exception
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            success, log = ConfigMigrator.migrate_file(config_file)
            
            assert not success
            assert "Migration failed" in log[0]

    def test_rollback_migration_backup_path(self, tmp_path):
        """Test rollback with default backup path (line 316)."""
        config_file = tmp_path / "test_config.toml"
        backup_file = config_file.with_suffix(".toml.backup")
        
        # Create backup file
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(backup_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Create current config (different)
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump({"network": {"listen_port": 6882}}, f)
        
        # Rollback with default backup path
        success, log = ConfigMigrator.rollback_migration(config_file)
        
        assert success
        assert "rolled back" in log[0]
        
        # Verify config was restored
        with open(config_file, encoding="utf-8") as f:
            restored_data = toml.load(f)
        assert restored_data["network"]["listen_port"] == 6881

    def test_rollback_migration_backup_not_found(self, tmp_path):
        """Test rollback with backup file not found (line 321)."""
        config_file = tmp_path / "test_config.toml"
        
        # Create config file but no backup
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Try to rollback without backup
        success, log = ConfigMigrator.rollback_migration(config_file)
        
        assert not success
        assert "Backup file not found" in log[0]

    def test_rollback_migration_exception(self, tmp_path):
        """Test rollback with exception handling (lines 332-335)."""
        config_file = tmp_path / "test_config.toml"
        backup_file = config_file.with_suffix(".toml.backup")
        
        # Create backup file
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(backup_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Mock shutil.copy2 to raise exception
        with patch("shutil.copy2", side_effect=PermissionError("Access denied")):
            success, log = ConfigMigrator.rollback_migration(config_file)
            
            assert not success
            assert "Rollback failed" in log[0]

    def test_migrate_file_nonexistent(self, tmp_path):
        """Test migration of non-existent file."""
        config_file = tmp_path / "nonexistent.toml"
        
        success, log = ConfigMigrator.migrate_file(config_file)
        
        assert not success
        assert "not found" in log[0]

    def test_validate_migrated_config_valid(self):
        """Test validation of valid migrated config."""
        config_data = {
            "network": {"listen_port": 6881},
            "disk": {"hash_workers": 4},
            "limits": {"global_down_kib": 0},
            "_version": "1.0.0"
        }
        
        is_valid, errors = ConfigMigrator.validate_migrated_config(config_data)
        
        assert is_valid
        assert errors == []

    def test_validate_migrated_config_invalid(self):
        """Test validation of invalid migrated config."""
        config_data = {
            "network": {"listen_port": "invalid"},
            "_version": "1.0.0"
        }
        
        is_valid, errors = ConfigMigrator.validate_migrated_config(config_data)
        
        assert not is_valid
        assert len(errors) > 0

    def test_rollback_migration(self, tmp_path):
        """Test migration rollback."""
        config_file = tmp_path / "test_config.toml"
        backup_file = tmp_path / "test_config.toml.backup"
        
        # Create test files
        config_data = {"network": {"listen_port": 6881}}
        backup_data = {"network": {"listen_port": 6882}}
        
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        with open(backup_file, "w", encoding="utf-8") as f:
            toml.dump(backup_data, f)
        
        # Rollback
        success, log = ConfigMigrator.rollback_migration(config_file, backup_file)
        
        assert success
        assert "rolled back" in log[0]
        
        # Check config was restored
        with open(config_file, "r", encoding="utf-8") as f:
            restored_data = toml.load(f)
        
        assert restored_data["network"]["listen_port"] == 6882

    def test_get_migration_history(self):
        """Test getting migration history."""
        config_data = {
            "network": {"listen_port": 6881},
            "_migration_log": ["Migrated from 0.8.0 to 1.0.0"]
        }
        
        history = ConfigMigrator.get_migration_history(config_data)
        
        assert len(history) == 1
        assert "Migrated from 0.8.0 to 1.0.0" in history[0]

    def test_clean_migration_metadata(self):
        """Test cleaning migration metadata."""
        config_data = {
            "network": {"listen_port": 6881},
            "_version": "1.0.0",
            "_migration_log": ["Migration log"]
        }
        
        cleaned = ConfigMigrator.clean_migration_metadata(config_data)
        
        assert "network" in cleaned
        assert "_version" not in cleaned
        assert "_migration_log" not in cleaned


class TestConfigBackup:
    """Test configuration backup functionality."""

    def test_create_backup_success(self, tmp_path):
        """Test successful backup creation."""
        config_file = tmp_path / "test_config.toml"
        backup_dir = tmp_path / "backups"
        
        # Create test config
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Create backup
        backup_system = ConfigBackup(backup_dir)
        success, backup_path, log = backup_system.create_backup(
            config_file, 
            description="Test backup"
        )
        
        assert success
        assert backup_path is not None
        assert backup_path.exists()
        assert "Test backup" in log[1]  # Description is in the second log message

    def test_create_backup_nonexistent_file(self, tmp_path):
        """Test backup creation for non-existent file."""
        config_file = tmp_path / "nonexistent.toml"
        backup_dir = tmp_path / "backups"
        
        backup_system = ConfigBackup(backup_dir)
        success, backup_path, log = backup_system.create_backup(config_file)
        
        assert not success
        assert backup_path is None
        assert "not found" in log[0]

    def test_restore_backup_success(self, tmp_path):
        """Test successful backup restoration."""
        config_file = tmp_path / "test_config.toml"
        backup_dir = tmp_path / "backups"
        
        # Create backup
        backup_system = ConfigBackup(backup_dir)
        
        # Create test config
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Create backup
        success, backup_path, _ = backup_system.create_backup(config_file)
        assert success
        
        # Modify original config
        modified_data = {"network": {"listen_port": 6882}}
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(modified_data, f)
        
        # Restore backup
        success, log = backup_system.restore_backup(backup_path)
        
        assert success
        assert "restored" in log[0]
        
        # Check config was restored
        with open(config_file, "r", encoding="utf-8") as f:
            restored_data = toml.load(f)
        
        assert restored_data["network"]["listen_port"] == 6881

    def test_restore_backup_nonexistent(self, tmp_path):
        """Test restoration of non-existent backup."""
        backup_file = tmp_path / "nonexistent.json"
        backup_dir = tmp_path / "backups"
        
        backup_system = ConfigBackup(backup_dir)
        success, log = backup_system.restore_backup(backup_file)
        
        assert not success
        assert "not found" in log[0]

    def test_list_backups(self, tmp_path):
        """Test listing backups."""
        backup_dir = tmp_path / "backups"
        backup_system = ConfigBackup(backup_dir)
        
        # Create test config
        config_file = tmp_path / "test_config.toml"
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Create multiple backups with a longer delay
        backup_system.create_backup(config_file, description="Backup 1")
        import time
        time.sleep(1.0)  # Longer delay to ensure different timestamps
        backup_system.create_backup(config_file, description="Backup 2")
        
        # List backups
        backups = backup_system.list_backups()
        
        assert len(backups) == 2
        assert all("Backup" in backup["description"] for backup in backups)

    def test_auto_backup(self, tmp_path):
        """Test automatic backup creation."""
        config_file = tmp_path / "test_config.toml"
        backup_dir = tmp_path / "backups"
        
        # Create test config
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Create auto backup
        backup_system = ConfigBackup(backup_dir)
        success, backup_path, log = backup_system.auto_backup(config_file)
        
        assert success
        assert backup_path is not None
        assert "Automatic backup" in log[1]  # Description is in the second log message

    def test_validate_backup_valid(self, tmp_path):
        """Test validation of valid backup."""
        backup_dir = tmp_path / "backups"
        backup_system = ConfigBackup(backup_dir)
        
        # Create test config and backup
        config_file = tmp_path / "test_config.toml"
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        success, backup_path, _ = backup_system.create_backup(config_file)
        assert success
        
        # Validate backup
        is_valid, errors = backup_system.validate_backup(backup_path)
        
        assert is_valid
        assert errors == []

    def test_validate_backup_invalid(self, tmp_path):
        """Test validation of invalid backup."""
        backup_file = tmp_path / "invalid_backup.json"
        backup_dir = tmp_path / "backups"
        
        # Create invalid backup file
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write("invalid json")
        
        backup_system = ConfigBackup(backup_dir)
        is_valid, errors = backup_system.validate_backup(backup_file)
        
        assert not is_valid
        assert len(errors) > 0

    def test_cleanup_old_backups(self, tmp_path):
        """Test cleanup of old backups."""
        backup_dir = tmp_path / "backups"
        backup_system = ConfigBackup(backup_dir)
        
        # Create test config
        config_file = tmp_path / "test_config.toml"
        config_data = {"network": {"listen_port": 6881}}
        import toml
        with open(config_file, "w", encoding="utf-8") as f:
            toml.dump(config_data, f)
        
        # Create backup
        backup_system.create_backup(config_file)
        
        # Cleanup (should not remove recent backups)
        removed_count, log = backup_system.cleanup_old_backups(days=0)
        
        # Should not remove anything since backup is recent
        assert removed_count == 0


class TestConfigDiff:
    """Test configuration diff functionality."""

    def test_compare_configs_identical(self):
        """Test comparison of identical configs."""
        config1 = {"network": {"listen_port": 6881}}
        config2 = {"network": {"listen_port": 6881}}
        
        diff = ConfigDiff.compare_configs(config1, config2)
        
        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0
        assert len(diff["modified"]) == 0
        assert len(diff["unchanged"]) == 1

    def test_compare_configs_different(self):
        """Test comparison of different configs."""
        config1 = {"network": {"listen_port": 6881}}
        config2 = {"network": {"listen_port": 6882}}
        
        diff = ConfigDiff.compare_configs(config1, config2)
        
        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0
        assert len(diff["modified"]) == 1
        assert "network.listen_port" in diff["modified"]

    def test_compare_configs_added_removed(self):
        """Test comparison with added and removed fields."""
        config1 = {"network": {"listen_port": 6881}}
        config2 = {"disk": {"hash_workers": 4}}
        
        diff = ConfigDiff.compare_configs(config1, config2)
        
        assert len(diff["added"]) == 1
        assert len(diff["removed"]) == 1
        assert "disk.hash_workers" in diff["added"]
        assert "network.listen_port" in diff["removed"]

    def test_merge_configs_no_conflicts(self):
        """Test merging configs with no conflicts."""
        base = {"network": {"listen_port": 6881}}
        override = {"disk": {"hash_workers": 4}}
        
        merged, conflicts = ConfigDiff.merge_configs(base, override)
        
        assert len(conflicts) == 0
        assert merged["network"]["listen_port"] == 6881
        assert merged["disk"]["hash_workers"] == 4

    def test_merge_configs_with_conflicts(self):
        """Test merging configs with conflicts."""
        base = {"network": {"listen_port": 6881}}
        override = {"network": {"listen_port": 6882}}
        
        merged, conflicts = ConfigDiff.merge_configs(base, override, conflict_resolution="last_wins")
        
        assert len(conflicts) == 1
        assert merged["network"]["listen_port"] == 6882

    def test_merge_configs_first_wins(self):
        """Test merging with first_wins conflict resolution."""
        base = {"network": {"listen_port": 6881}}
        override = {"network": {"listen_port": 6882}}
        
        merged, conflicts = ConfigDiff.merge_configs(base, override, conflict_resolution="first_wins")
        
        assert len(conflicts) == 1
        assert merged["network"]["listen_port"] == 6881

    def test_apply_changes(self):
        """Test applying specific changes."""
        base = {"network": {"listen_port": 6881}}
        changes = {"network.listen_port": 6882}
        
        result = ConfigDiff.apply_changes(base, changes)
        
        assert result["network"]["listen_port"] == 6882

    def test_apply_changes_add_remove(self):
        """Test applying add and remove changes."""
        base = {"network": {"listen_port": 6881}}
        changes = {"disk.hash_workers": 4}
        change_types = {"disk.hash_workers": "add"}
        
        result = ConfigDiff.apply_changes(base, changes, change_types)
        
        assert result["network"]["listen_port"] == 6881
        assert result["disk"]["hash_workers"] == 4

    def test_generate_diff_report_text(self):
        """Test generating text diff report."""
        diff = {
            "added": {"disk.hash_workers": 4},
            "removed": {"network.listen_port": 6881},
            "modified": {"network.max_peers": {"old": 100, "new": 200}},
            "unchanged": {},
        }
        
        report = ConfigDiff.generate_diff_report(diff, "text")
        
        assert "ADDED" in report
        assert "REMOVED" in report
        assert "MODIFIED" in report
        assert "Summary:" in report

    def test_generate_diff_report_json(self):
        """Test generating JSON diff report."""
        diff = {"added": {}, "removed": {}, "modified": {}, "unchanged": {}}
        
        report = ConfigDiff.generate_diff_report(diff, "json")
        
        parsed = json.loads(report)
        assert "added" in parsed
        assert "removed" in parsed

    def test_generate_diff_report_yaml(self):
        """Test generating YAML diff report."""
        diff = {"added": {}, "removed": {}, "modified": {}, "unchanged": {}}
        
        try:
            report = ConfigDiff.generate_diff_report(diff, "yaml")
            assert "added:" in report
        except ImportError:
            pytest.skip("PyYAML not available")

    def test_generate_diff_report_invalid_format(self):
        """Test generating diff report with invalid format."""
        diff = {"added": {}, "removed": {}, "modified": {}, "unchanged": {}}
        
        with pytest.raises(ValueError, match="Unsupported format"):
            ConfigDiff.generate_diff_report(diff, "invalid")

    def test_compare_files(self, tmp_path):
        """Test comparing configuration files."""
        file1 = tmp_path / "config1.toml"
        file2 = tmp_path / "config2.toml"
        
        config1 = {"network": {"listen_port": 6881}}
        config2 = {"network": {"listen_port": 6882}}
        
        import toml
        with open(file1, "w", encoding="utf-8") as f:
            toml.dump(config1, f)
        
        with open(file2, "w", encoding="utf-8") as f:
            toml.dump(config2, f)
        
        diff = ConfigDiff.compare_files(file1, file2)
        
        assert len(diff["modified"]) == 1
        assert "network.listen_port" in diff["modified"]

    def test_deep_merge_nested_conflicts(self):
        """Test deep merge with nested conflicts."""
        base = {
            "network": {
                "listen_port": 6881,
                "settings": {"timeout": 30}
            }
        }
        override = {
            "network": {
                "listen_port": 6882,
                "settings": {"timeout": 60, "retries": 3}
            }
        }
        
        merged, conflicts = ConfigDiff.merge_configs(base, override, strategy="deep")
        
        # Should have conflicts for both listen_port and timeout
        assert len(conflicts) == 2
        assert any("listen_port" in conflict for conflict in conflicts)
        assert any("timeout" in conflict for conflict in conflicts)
        
        # Should merge nested settings
        assert merged["network"]["settings"]["timeout"] == 60
        assert merged["network"]["settings"]["retries"] == 3

    def test_ignore_metadata(self):
        """Test ignoring metadata in comparison."""
        config1 = {
            "network": {"listen_port": 6881},
            "_version": "1.0.0"
        }
        config2 = {
            "network": {"listen_port": 6881},
            "_version": "1.1.0"
        }
        
        diff = ConfigDiff.compare_configs(config1, config2, ignore_metadata=True)
        
        # Should not detect version as different
        assert len(diff["modified"]) == 0
        assert len(diff["unchanged"]) == 1

    def test_merge_configs_shallow_strategy(self):
        """Test merging with shallow strategy (line 101)."""
        base = {"network": {"listen_port": 6881}}
        override = {"network": {"listen_port": 6882}}
        
        merged, conflicts = ConfigDiff.merge_configs(base, override, strategy="shallow")
        
        # Should use shallow merge
        assert len(conflicts) == 1
        assert merged["network"]["listen_port"] == 6882

    def test_apply_changes_remove(self):
        """Test applying remove change (line 139)."""
        base = {"network": {"listen_port": 6881, "max_peers": 100}}
        changes = {"network.max_peers": None}
        change_types = {"network.max_peers": "remove"}
        
        result = ConfigDiff.apply_changes(base, changes, change_types)
        
        assert "listen_port" in result["network"]
        assert "max_peers" not in result["network"]

    def test_generate_diff_report_yaml_import_error(self):
        """Test YAML report generation with ImportError (lines 168-170)."""
        diff = {"added": {}, "removed": {}, "modified": {}, "unchanged": {}}
        
        # Mock yaml import to fail
        import sys
        original_yaml = sys.modules.get("yaml")
        try:
            if "yaml" in sys.modules:
                del sys.modules["yaml"]
            
            with patch("builtins.__import__", side_effect=ImportError("No module named 'yaml'")):
                with pytest.raises(ImportError, match="PyYAML is required"):
                    ConfigDiff.generate_diff_report(diff, "yaml")
        finally:
            if original_yaml:
                sys.modules["yaml"] = original_yaml

    def test_remove_nested_value_success(self):
        """Test removing nested value successfully (lines 262-272)."""
        config = {
            "network": {
                "listen_port": 6881,
                "settings": {
                    "timeout": 30,
                    "retries": 3
                }
            }
        }
        
        ConfigDiff._remove_nested_value(config, "network.settings.timeout")
        
        assert "timeout" not in config["network"]["settings"]
        assert "retries" in config["network"]["settings"]

    def test_remove_nested_value_missing_path(self):
        """Test removing nested value with missing path (line 269)."""
        config = {"network": {"listen_port": 6881}}
        
        # Should return early without error
        ConfigDiff._remove_nested_value(config, "network.missing.key")
        
        # Original config should be unchanged
        assert config["network"]["listen_port"] == 6881

    def test_deep_merge_manual_resolution(self):
        """Test deep merge with manual resolution strategy (line 316)."""
        base = {"network": {"listen_port": 6881}}
        override = {"network": {"listen_port": 6882}}
        
        merged, conflicts = ConfigDiff.merge_configs(base, override, conflict_resolution="manual")
        
        # Manual resolution should keep base value
        assert len(conflicts) == 1
        assert merged["network"]["listen_port"] == 6881

    def test_shallow_merge_with_conflicts(self):
        """Test shallow merge with conflicts (lines 339-359)."""
        base = {"key1": "value1", "key2": "value2"}
        override = {"key2": "value2_override", "key3": "value3"}
        
        result, conflicts = ConfigDiff._shallow_merge_with_conflicts(base, override, "last_wins")
        
        assert len(conflicts) == 1
        assert "key2" in [c.split("'")[1] for c in conflicts]
        assert result["key1"] == "value1"
        assert result["key2"] == "value2_override"  # last_wins
        assert result["key3"] == "value3"

    def test_shallow_merge_first_wins(self):
        """Test shallow merge with first_wins strategy (lines 351)."""
        base = {"key1": "value1"}
        override = {"key1": "value2"}
        
        result, conflicts = ConfigDiff._shallow_merge_with_conflicts(base, override, "first_wins")
        
        assert len(conflicts) == 1
        assert result["key1"] == "value1"  # first_wins keeps base

    def test_shallow_merge_no_conflict(self):
        """Test shallow merge with no conflicts (lines 355-357)."""
        base = {"key1": "value1"}
        override = {"key2": "value2"}
        
        result, conflicts = ConfigDiff._shallow_merge_with_conflicts(base, override, "last_wins")
        
        assert len(conflicts) == 0
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"

    def test_load_config_file_json(self):
        """Test loading JSON config file (line 439)."""
        import json
        import tempfile
        
        config_data = {"network": {"listen_port": 6881}}
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(config_data, f)
            json_path = Path(f.name)
        
        try:
            result = ConfigDiff._load_config_file(json_path)
            assert result["network"]["listen_port"] == 6881
        finally:
            json_path.unlink()