from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import importlib.util
import json
import re
import sys
import types

import pytest
import toml

from ccbt.config.config_schema import ConfigDiscovery


REPO_ROOT = Path(__file__).resolve().parents[3]


def _extract_env_mappings() -> dict[str, str]:
    config_path = REPO_ROOT / "ccbt" / "config" / "config.py"
    text = config_path.read_text(encoding="utf-8")

    start = text.find("        env_mappings: dict[str, str] = {")
    if start < 0:
        msg = "Unable to locate env_mappings block in config.py"
        raise RuntimeError(msg)

    end = text.find("\n        }", start)
    if end < 0:
        msg = "Unable to locate env_mappings closing brace in config.py"
        raise RuntimeError(msg)

    block = text[start:end]
    out: dict[str, str] = {}
    # Single-line: "CCBT_X": "section.field"
    for env_name, path in re.findall(
        r"[\"\'](CCBT_[A-Z0-9_]+)[\"\']\s*:\s*[\"\']([a-z0-9_\\.]+)[\"\']",
        block,
    ):
        out[env_name] = path
    # Multi-line: "CCBT_X": (\n                "section.field"\n            ),
    for env_name, path in re.findall(
        r"[\"\'](CCBT_[A-Z0-9_]+)[\"\']\s*:\s*\(\s*\n\s*[\"\']([a-z0-9_\\.]+)[\"\']",
        block,
    ):
        out[env_name] = path
    return out


def _parse_env_example(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    comment_pattern = re.compile(r"^(CCBT_[A-Z0-9_]+)=(.*?)(?:\s+#\s*(.*))?$")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = comment_pattern.match(line)
        if not match:
            continue

        key, value, _ = match.groups()
        entries[key] = value.strip()

    return entries


def _load_env_example_comments(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    comment_pattern = re.compile(r"^(CCBT_[A-Z0-9_]+)=(.*?)(?:\s+#\s*(.*))?$")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = comment_pattern.match(line)
        if not match:
            continue

        key, _, comment = match.groups()
        entries[key] = (comment or "").strip()

    return entries


def _load_parity_expectations() -> dict[str, Any]:
    fixture_path = (
        Path(__file__).resolve().parent / "data" / "config_parity_expectations.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_config_modules() -> dict[str, Any]:
    # Load ccbt.models and config modules without triggering ccbt/__init__.py side effects.
    ccbt_root = REPO_ROOT / "ccbt"

    ccbt_pkg = types.ModuleType("ccbt")
    ccbt_pkg.__path__ = [str(ccbt_root)]
    sys.modules["ccbt"] = ccbt_pkg

    cfg_pkg = types.ModuleType("ccbt.config")
    cfg_pkg.__path__ = [str(ccbt_root / "config")]
    sys.modules["ccbt.config"] = cfg_pkg

    models_spec = importlib.util.spec_from_file_location(
        "ccbt.models", str(ccbt_root / "models.py")
    )
    models = importlib.util.module_from_spec(models_spec)
    models.__package__ = "ccbt"
    models.__file__ = str(ccbt_root / "models.py")
    sys.modules["ccbt.models"] = models
    models_spec.loader.exec_module(models)

    config_spec = importlib.util.spec_from_file_location(
        "ccbt.config.config", str(ccbt_root / "config" / "config.py")
    )
    config_module = importlib.util.module_from_spec(config_spec)
    config_module.__package__ = "ccbt.config"
    config_module.__file__ = str(ccbt_root / "config" / "config.py")
    sys.modules["ccbt.config.config"] = config_module
    config_spec.loader.exec_module(config_module)

    return {
        "config": config_module,
        "models": models,
    }


@pytest.mark.unit
def test_nested_discovery_path_floor_matches_expectations() -> None:
    """Guard against accidental shrinkage of the nested config option inventory."""
    fixture = _load_parity_expectations()
    floor = int(fixture.get("min_nested_discovery_paths", 400))
    assert len(ConfigDiscovery.list_all_options_nested()) >= floor


@pytest.mark.unit
def test_env_example_contains_all_mapped_variables() -> None:
    env_mappings = _extract_env_mappings()
    env_entries = _parse_env_example(REPO_ROOT / "env.example")

    expectations = _load_parity_expectations()
    allowed_missing = set(expectations.get("mapped_env_missing_tolerant_allowlist", []))
    missing = set(env_mappings) - set(env_entries) - allowed_missing

    assert not missing, f"Mapped env vars missing from env.example: {sorted(missing)}"

    legacy = set(env_entries) - set(env_mappings)
    expected_legacy = set(expectations["allowed_legacy_env_keys"])
    assert legacy == expected_legacy, (
        "Legacy/unmapped env var set changed\n"
        f"Missing from allowlist: {sorted(legacy - expected_legacy)}\n"
        f"New unknown keys: {sorted(expected_legacy - legacy)}"
    )

    legacy_comments = _load_env_example_comments(REPO_ROOT / "env.example")
    legacy_without_compat = [
        key
        for key in sorted(legacy)
        if key in legacy_comments
        and "legacy" not in legacy_comments[key].lower()
        and "unmapped" not in legacy_comments[key].lower()
    ]
    assert not legacy_without_compat


@pytest.mark.unit
def test_ccbt_toml_matches_model_section_inventory() -> None:
    modules = _load_config_modules()
    models = modules["models"]
    fixture = _load_parity_expectations()

    expected_sections = set(fixture["expected_model_sections"])
    toml_sections = set(toml.load(REPO_ROOT / "ccbt.toml").keys())

    assert toml_sections == expected_sections

    model_sections = set(models.Config.model_fields.keys())
    assert model_sections == expected_sections

    env_mappings = _extract_env_mappings()
    mapped_sections = {path.split(".", 1)[0] for path in env_mappings.values()}
    assert mapped_sections.issubset(expected_sections)

    assert fixture["mapped_env_count"] == len(env_mappings)
    assert fixture["env_example_count"] == len(
        _parse_env_example(REPO_ROOT / "env.example")
    )


@pytest.mark.unit
def test_config_manager_parses_env_types_and_paths() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    # Use a fresh instance that reads _get_env_config and validates types.
    with pytest.MonkeyPatch.context() as monkey:
        monkey.setenv("CCBT_ENABLE_DHT", "false")
        monkey.setenv("CCBT_MAX_PEERS", "321")
        monkey.setenv("CCBT_TRACKER_BASE_ANNOUNCE_INTERVAL", "88.5")
        monkey.setenv("CCBT_FILTER_FILES", "alpha.txt,beta.txt")
        monkey.setenv("CCBT_ENCRYPTION_ALLOWED_CIPHERS", "rc4,aes,chacha20")
        monkey.setenv("CCBT_LOG_CORRELATION_ID", "false")
        monkey.setenv("CCBT_STRUCTURED_LOGGING", "true")
        monkey.setenv("CCBT_LOG_FORMAT", "%(name)s - %(levelname)s - %(message)s")
        monkey.setenv("CCBT_TRACE_FILE", "/tmp/ccbt-trace.log")
        monkey.setenv("CCBT_METRICS_INTERVAL", "7.5")
        monkey.setenv("CCBT_LOG_LEVEL", "TRACE")

        config_manager = ConfigManager()
        env_values = config_manager._get_env_config()

    assert env_values["discovery"]["enable_dht"] is False
    assert env_values["network"]["max_global_peers"] == 321
    assert env_values["discovery"]["tracker_base_announce_interval"] == 88.5
    assert env_values["security"]["ip_filter"]["filter_files"] == [
        "alpha.txt",
        "beta.txt",
    ]
    assert env_values["security"]["encryption_allowed_ciphers"] == [
        "rc4",
        "aes",
        "chacha20",
    ]
    assert env_values["observability"]["log_level"] == "TRACE"
    assert env_values["observability"]["log_correlation_id"] is False
    assert env_values["observability"]["structured_logging"] is True
    assert (
        env_values["observability"]["log_format"]
        == "%(name)s - %(levelname)s - %(message)s"
    )
    assert env_values["observability"]["trace_file"] == "/tmp/ccbt-trace.log"
    assert env_values["observability"]["metrics_interval"] == 7.5

    # Optional alias mapping should resolve to the same destination path.
    with pytest.MonkeyPatch.context() as monkey:
        monkey.setenv("CCBT_LOCALE", "en")
        monkey.setenv("CCBT_UI_LOCALE", "es")

        alias_values = config_manager._get_env_config()

    assert alias_values["ui"]["locale"] == "es"


def test_env_observability_values_take_precedence_over_toml(tmp_path) -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager
    config_file = tmp_path / "ccbt.toml"
    config_file.write_text(
        """
[observability]
log_level = "ERROR"
log_correlation_id = false
structured_logging = false
log_format = "%(message)s"
metrics_interval = 15.0
trace_file = "old.trace"
"""
    )

    with pytest.MonkeyPatch.context() as monkey:
        monkey.setenv("CCBT_LOG_LEVEL", "TRACE")
        monkey.setenv("CCBT_LOG_CORRELATION_ID", "true")
        monkey.setenv("CCBT_STRUCTURED_LOGGING", "true")
        monkey.setenv("CCBT_LOG_FORMAT", "%(name)s")
        monkey.setenv("CCBT_METRICS_INTERVAL", "7.5")
        monkey.setenv("CCBT_TRACE_FILE", "from_env.trace")

        manager = ConfigManager(config_file=config_file)

    observability = manager.config.observability
    assert observability.log_level == modules["models"].LogLevel.TRACE
    assert observability.log_correlation_id is True
    assert observability.structured_logging is True
    assert observability.log_format == "%(name)s"
    assert observability.metrics_interval == 7.5
    assert observability.trace_file == "from_env.trace"


def test_config_env_mapping_supports_encryption_enable_flag() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    with pytest.MonkeyPatch.context() as monkey:
        monkey.setenv("CCBT_ENABLE_ENCRYPTION", "false")

        manager = ConfigManager()
        env_values = manager._get_env_config()

    assert env_values["security"]["enable_encryption"] is False


def test_config_env_network_enable_encryption_mirrors_toml_network_section() -> None:
    """CCBT_NETWORK_ENABLE_ENCRYPTION sets network.enable_encryption (TOML [network] parity)."""
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    with pytest.MonkeyPatch.context() as monkey:
        monkey.setenv("CCBT_NETWORK_ENABLE_ENCRYPTION", "true")

        manager = ConfigManager()
        env_values = manager._get_env_config()

    assert env_values["network"]["enable_encryption"] is True


def test_config_manager_normalizes_legacy_security_fields() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    manager = ConfigManager.__new__(ConfigManager)
    config_data: dict[str, dict[str, object]] = {
        "security": {"encryption_preference": "require_encrypted"},
        "network": {"enable_encryption": True},
    }

    manager._normalize_loaded_config_data(config_data)

    assert config_data["security"]["encryption_mode"] == "required"
    assert config_data["security"]["enable_encryption"] is True


def test_config_manager_normalizes_encryption_mode_aliases() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    manager = ConfigManager.__new__(ConfigManager)
    config_data = {"security": {"encryption_mode": "plaintext-only"}}

    manager._normalize_loaded_config_data(config_data)

    assert config_data["security"]["encryption_mode"] == "disabled"


def test_config_manager_normalizes_encryption_allowed_ciphers() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    manager = ConfigManager.__new__(ConfigManager)
    config_data = {"security": {"encryption_allowed_ciphers": " RC4, AES, ChAcHa20, "}}
    manager._normalize_loaded_config_data(config_data)
    assert config_data["security"]["encryption_allowed_ciphers"] == [
        "RC4",
        "AES",
        "ChAcHa20",
    ]

    config_data = {
        "security": {"encryption_allowed_ciphers": [" RC4", "AES, ChAcHa20", ""]},
    }
    manager._normalize_loaded_config_data(config_data)
    assert config_data["security"]["encryption_allowed_ciphers"] == [
        "RC4",
        "AES",
        "ChAcHa20",
    ]


def test_security_config_validates_encryption_fields() -> None:
    modules = _load_config_modules()
    SecurityConfig = modules["models"].SecurityConfig

    cfg = SecurityConfig(
        encryption_mode="REQUIRED",
        encryption_allowed_ciphers=[" RC4 ", "ChAcHa20"],
    )
    assert cfg.encryption_mode == "required"
    assert cfg.encryption_allowed_ciphers == ["rc4", "chacha20"]

    with pytest.raises(ValueError, match="encryption_mode"):
        SecurityConfig(encryption_mode="not-a-mode")

    with pytest.raises(ValueError, match="unknown token"):
        SecurityConfig(encryption_allowed_ciphers=["not-a-cipher"])


def test_full_config_network_env_enables_security_encryption() -> None:
    """network.enable_encryption from env must enable MSE via model sync."""
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    with pytest.MonkeyPatch.context() as monkey:
        monkey.delenv("CCBT_ENABLE_ENCRYPTION", raising=False)
        monkey.setenv("CCBT_NETWORK_ENABLE_ENCRYPTION", "true")

        manager = ConfigManager()

    assert manager.config.security.enable_encryption is True
    assert manager.config.network.enable_encryption is True


def test_config_encryption_mirror_prefers_canonical_security_field() -> None:
    modules = _load_config_modules()
    Config = modules["models"].Config

    cfg = Config(network={"enable_encryption": True})
    assert cfg.security.enable_encryption is True
    assert cfg.network.enable_encryption is True

    cfg = Config(
        network={"enable_encryption": False},
        security={"enable_encryption": True},
    )
    assert cfg.security.enable_encryption is True
    assert cfg.network.enable_encryption is True


def test_env_mapping_includes_dht_bootstrap_nodes() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    with pytest.MonkeyPatch.context() as monkey:
        monkey.setenv(
            "CCBT_DHT_BOOTSTRAP_NODES",
            "router.bittorrent.com:6881,dht.transmissionbt.com:6881",
        )
        manager = ConfigManager()
        env_values = manager._get_env_config()

    assert env_values["discovery"]["dht_bootstrap_nodes"] == [
        "router.bittorrent.com:6881",
        "dht.transmissionbt.com:6881",
    ]


def test_apply_profile_sets_max_peers_per_torrent_key() -> None:
    modules = _load_config_modules()
    ConfigManager = modules["config"].ConfigManager

    manager = ConfigManager()
    manager.config.network.max_peers_per_torrent = 999
    manager.apply_profile("low_resource")

    assert manager.config.network.max_peers_per_torrent == 10
