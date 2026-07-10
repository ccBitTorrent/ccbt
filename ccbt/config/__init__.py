"""Configuration management.

This module handles configuration loading, validation, templating, and migration.
"""

from __future__ import annotations

from ccbt.config.config import Config, ConfigManager, get_config, init_config
from ccbt.config.config_backup import ConfigBackup
from ccbt.config.config_capabilities import SystemCapabilities
from ccbt.config.config_conditional import ConditionalConfig
from ccbt.config.config_diff import ConfigDiff
from ccbt.config.config_migration import ConfigMigrator
from ccbt.config.config_schema import ConfigSchema
from ccbt.config.config_templates import ConfigProfiles, ConfigTemplates

__all__ = [
    "ConditionalConfig",
    "Config",
    "ConfigBackup",
    "ConfigDiff",
    "ConfigManager",
    "ConfigMigrator",
    "ConfigProfiles",
    "ConfigSchema",
    "ConfigTemplates",
    "SystemCapabilities",
    "get_config",
    "init_config",
]
