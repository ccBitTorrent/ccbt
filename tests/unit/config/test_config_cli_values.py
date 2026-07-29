"""Tests for CLI config value parsing."""

from __future__ import annotations

from ccbt.config.config_cli_values import (
    get_nested_value,
    parse_cli_config_value,
    set_nested_dict,
)


def test_parse_json_array() -> None:
    """JSON array strings decode to Python lists."""
    v = parse_cli_config_value('["a","b"]', "discovery.dht_bootstrap_nodes")
    assert v == ["a", "b"]


def test_parse_comma_list_path() -> None:
    """Known list paths accept comma-separated tokens."""
    v = parse_cli_config_value("a, b", "discovery.dht_bootstrap_nodes")
    assert v == ["a", "b"]


def test_set_and_get_nested() -> None:
    """set_nested_dict and get_nested_value round-trip."""
    listen = 5000
    d: dict = {}
    set_nested_dict(d, "network.listen_port", listen)
    assert get_nested_value(d, "network.listen_port") == listen
