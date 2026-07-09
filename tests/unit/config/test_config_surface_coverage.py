"""Drift checks: env mappings and CLI override paths vs nested config discovery."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ccbt.config.config_schema import ConfigDiscovery
from tests.unit.config.test_config_parity import (
    _extract_env_mappings,
    _load_parity_expectations,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
OVERRIDES_PATH = REPO_ROOT / "ccbt" / "cli" / "overrides.py"

# cfg.section.field... =  (at least one dot after cfg.)
_CFG_ASSIGN_PATH = re.compile(
    r"cfg\.([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)\s*=",
)


def _extract_cli_override_paths() -> set[str]:
    text = OVERRIDES_PATH.read_text(encoding="utf-8")
    return set(_CFG_ASSIGN_PATH.findall(text))


@pytest.mark.unit
def test_env_mapping_paths_exist_in_nested_discovery() -> None:
    """Every ``env_mappings`` destination must appear in ``list_all_options_nested``."""
    canonical = {r["path"] for r in ConfigDiscovery.list_all_options_nested()}
    env_map = _extract_env_mappings()
    fixture = _load_parity_expectations()
    allow = set(fixture.get("surface_env_path_allowlist", []))

    bad = sorted({p for p in env_map.values() if p not in canonical and p not in allow})
    assert not bad, f"env_mappings paths missing from discovery: {bad}"


@pytest.mark.unit
def test_cli_override_paths_exist_in_nested_discovery() -> None:
    """Dotted paths assigned via ``cfg.*`` in overrides should match discovery."""
    canonical = {r["path"] for r in ConfigDiscovery.list_all_options_nested()}
    override_paths = _extract_cli_override_paths()
    fixture = _load_parity_expectations()
    key = "surface_cli_override_path_allowlist"
    allow = set(fixture.get(key, []))

    bad = sorted(p for p in override_paths if p not in canonical and p not in allow)
    assert not bad, f"CLI override paths missing from discovery: {bad}"
