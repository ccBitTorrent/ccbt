"""Tests for nested configuration discovery."""

from __future__ import annotations

from ccbt.config.config_schema import ConfigDiscovery


def test_list_all_options_nested_includes_deep_paths() -> None:
    """Nested discovery emits dotted paths under nested models."""
    rows = ConfigDiscovery.list_all_options_nested()
    paths = {r["path"] for r in rows}
    assert "network.utp.prefer_over_tcp" in paths
    assert "network.protocol_v2.enable_protocol_v2" in paths
    assert all("section" in r and "default_source" in r for r in rows)


def test_list_all_options_shallow_still_works() -> None:
    """Legacy list_all_options keeps one-level section.option paths."""
    shallow = ConfigDiscovery.list_all_options()
    assert shallow
    assert all(r["path"].count(".") == 1 for r in shallow)
