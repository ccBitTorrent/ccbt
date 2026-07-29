#!/usr/bin/env python3
"""Return pytest path arguments for a CI test shard name."""

from __future__ import annotations

import sys
from pathlib import Path

SHARDS: dict[str, list[str]] = {
    "daemon-integration": [
        "tests/daemon",
        "tests/integration",
        "tests/extensions",
    ],
    "unit-peer-transport": [
        "tests/unit/peer",
        "tests/unit/transport",
        "tests/unit/piece",
        "tests/unit/tracker",
        "tests/unit/network",
        "tests/unit/metadata",
    ],
    "unit-session-storage": [
        "tests/unit/session",
        "tests/unit/discovery",
        "tests/unit/storage",
        "tests/unit/checkpoint",
        "tests/unit/file",
        "tests/unit/disk",
        "tests/unit/resilience",
    ],
    "unit-rest": [
        "tests/unit/cli",
        "tests/unit/config",
        "tests/unit/consensus",
        "tests/unit/core",
        "tests/unit/daemon",
        "tests/unit/executor",
        "tests/unit/extensions",
        "tests/unit/i18n",
        "tests/unit/interface",
        "tests/unit/ml",
        "tests/unit/models",
        "tests/unit/monitoring",
        "tests/unit/nat",
        "tests/unit/plugins",
        "tests/unit/protocols",
        "tests/unit/property",
        "tests/unit/proxy",
        "tests/unit/queue_mgmt",
        "tests/unit/security",
        "tests/unit/services",
        "tests/unit/utils",
        "tests/test_new_fixtures.py",
    ],
}


def main() -> int:
    if len(sys.argv) != 2:
        names = ", ".join(sorted(SHARDS))
        print(f"usage: {sys.argv[0]} <shard-name>", file=sys.stderr)
        print(f"shards: {names}", file=sys.stderr)
        return 2
    shard = sys.argv[1]
    paths = SHARDS.get(shard)
    if paths is None:
        print(f"unknown shard: {shard}", file=sys.stderr)
        return 1
    existing = [path for path in paths if Path(path).exists()]
    missing = [path for path in paths if not Path(path).exists()]
    if missing:
        print(
            f"warning: skipping missing shard paths: {' '.join(missing)}",
            file=sys.stderr,
        )
    if not existing:
        print(f"no existing paths for shard: {shard}", file=sys.stderr)
        return 1
    print(" ".join(existing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
