from __future__ import annotations

import pytest

from ccbt.config.config_migration import ConfigMigrator
from ccbt.config.config_templates import ConfigTemplates


@pytest.mark.unit
def test_migrate_0_9_0_security_legacy_aliases() -> None:
    """Migration maps legacy security fields to canonical security config."""
    source_config = {
        "security": {"encryption_preference": "require_encrypted"},
        "network": {"enable_encryption": True},
    }

    migrated, _ = ConfigMigrator.migrate_config(
        source_config, target_version=ConfigMigrator.CURRENT_VERSION
    )

    security = migrated["security"]
    assert security["encryption_mode"] == "required"
    assert security["enable_encryption"] is True
    assert "encryption_preference" not in security


@pytest.mark.unit
def test_migrate_0_8_0_security_preference_falls_back_to_preferred() -> None:
    """Legacy encryption preference maps to preferred and explicit network toggle is preserved."""
    source_config = {
        "security": {"encryption_preference": "allow_plaintext"},
        "network": {"enable_encryption": False},
    }

    migrated = ConfigMigrator._migrate_0_8_0_to_1_0_0(source_config)

    security = migrated["security"]
    assert security["encryption_mode"] == "preferred"
    assert security["enable_encryption"] is False


@pytest.mark.unit
def test_templates_default_security_fields_are_canonical() -> None:
    """Template profiles should only use canonical SecurityConfig fields."""
    for profile_name, profile in ConfigTemplates.TEMPLATES.items():
        security = profile.get("config", {}).get("security", {})
        assert "encryption_preference" not in security, profile_name
        assert "encryption_mode" in security, profile_name
        assert "enable_encryption" in security, profile_name
