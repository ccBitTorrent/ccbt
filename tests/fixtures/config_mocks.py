"""Shared configuration mocking helpers for tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest


def patch_get_config(monkeypatch, mock_config: Mock) -> None:
    """Patch get_config where production code imports it."""
    monkeypatch.setattr("ccbt.config.config.get_config", lambda: mock_config)


@pytest.fixture(scope="function")
def mock_config_enabled(monkeypatch):
    """Mock config with metrics enabled."""
    import ccbt.monitoring as monitoring_module

    monitoring_module._GLOBAL_METRICS_COLLECTOR = None

    mock_config = Mock()
    mock_observability = Mock()
    mock_observability.enable_metrics = True
    mock_observability.metrics_interval = 5.0
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability

    patch_get_config(monkeypatch, mock_config)
    return mock_config


@pytest.fixture(scope="function")
def mock_config_disabled(monkeypatch):
    """Mock config with metrics disabled."""
    import ccbt.monitoring as monitoring_module

    monitoring_module._GLOBAL_METRICS_COLLECTOR = None

    mock_config = Mock()
    mock_observability = Mock()
    mock_observability.enable_metrics = False
    mock_observability.metrics_interval = 5.0
    mock_observability.metrics_port = 9090
    mock_config.observability = mock_observability

    patch_get_config(monkeypatch, mock_config)
    return mock_config
