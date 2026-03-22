"""Parse CLI-provided configuration values for dotted config paths.

Shared with environment parsing semantics where list fields accept comma-separated
strings.
"""

from __future__ import annotations

import json
from typing import Any

# Paths where a comma-separated string should become list[str] (aligned with
# ``ConfigManager._get_env_config`` / ``_parse_env_value``).
COMMA_SEPARATED_LIST_PATHS: frozenset[str] = frozenset(
    {
        "security.encryption_allowed_ciphers",
        "security.ip_filter.filter_files",
        "security.ip_filter.filter_urls",
        "security.blacklist.auto_update_sources",
        "security.authenticated_swarms.trusted_swarm_ids",
        "discovery.dht_bootstrap_nodes",
        "discovery.dht_ipv6_bootstrap_nodes",
        "discovery.default_trackers",
        "proxy.proxy_bypass_list",
    }
)


def parse_cli_config_value(raw: str, dotted_path: str) -> Any:
    """Parse a CLI string into a Python value suitable for merging into config data.

    Order:

    1. ``json.loads`` when the string decodes as JSON (arrays, objects, numbers,
       booleans, null).
    2. Path-aware comma-separated list for :data:`COMMA_SEPARATED_LIST_PATHS`.
    3. Boolean tokens, then int/float, else raw string.

    Args:
        raw: Raw argument text (often from ``--value``).
        dotted_path: Full dotted config key (e.g. ``network.listen_port``).

    Returns:
        Parsed value.

    """
    stripped = raw.strip()
    if stripped:
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if dotted_path in COMMA_SEPARATED_LIST_PATHS:
        return [item.strip() for item in raw.split(",") if item.strip()]

    low = raw.lower()
    if low in {"true", "1", "yes", "on"}:
        return True
    if low in {"false", "0", "no", "off"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def get_nested_value(data: dict[str, Any], dotted_path: str) -> Any:
    """Return value at dotted path in a nested dict, or ``None`` if missing."""
    cur: Any = data
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_nested_dict(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    """Set ``target[a][b]... = value`` for a dotted path, creating dicts as needed."""
    parts = dotted_path.split(".")
    cur = target
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value
