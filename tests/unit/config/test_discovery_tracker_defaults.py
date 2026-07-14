"""Discovery defaults: tracker dedupe and UDP ingress-related fields."""

from __future__ import annotations

import pytest

from ccbt.models import DiscoveryConfig

pytestmark = pytest.mark.unit


def test_default_trackers_deduped_by_host_port() -> None:
    """Factory list includes working HTTP fallbacks and dedupes host:port."""
    d = DiscoveryConfig()
    assert len(d.default_trackers) <= 6
    assert any("tracker.dler.org:6969" in u for u in d.default_trackers)
    assert any("tracker.renfei.net:8080" in u for u in d.default_trackers)
    assert any("tracker.nekomi.cn" in u for u in d.default_trackers)
    assert sum(1 for u in d.default_trackers if "opentrackr.org:1337" in u) == 1
