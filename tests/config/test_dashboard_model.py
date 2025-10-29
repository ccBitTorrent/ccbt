from __future__ import annotations

from ccbt.models import Config


def test_dashboard_defaults_present() -> None:
    cfg = Config()
    assert cfg.dashboard.enable_dashboard is True
    assert isinstance(cfg.dashboard.host, str)
    assert cfg.dashboard.port >= 1024
    assert cfg.dashboard.refresh_interval > 0
    assert cfg.dashboard.default_view in {"overview", "performance", "network", "security", "alerts"}


