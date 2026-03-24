"""Discovery defaults: tracker dedupe and UDP ingress-related fields."""

from __future__ import annotations

import pytest

from ccbt.models import DiscoveryConfig

pytestmark = pytest.mark.unit


def test_default_trackers_deduped_by_host_port() -> None:
    """Factory list collapses http+udp to the same host:port."""
    d = DiscoveryConfig()
    assert len(d.default_trackers) <= 6
    hosts_ports = set()
    for u in d.default_trackers:
        if "opentrackr.org:1337" in u:
            hosts_ports.add("ot1337")
        if "openbittorrent.com:80" in u:
            hosts_ports.add("ob80")
    assert "ot1337" in hosts_ports
    assert "ob80" in hosts_ports
    assert sum(1 for u in d.default_trackers if "opentrackr.org:1337" in u) == 1
    assert sum(1 for u in d.default_trackers if "openbittorrent.com:80" in u) == 1
