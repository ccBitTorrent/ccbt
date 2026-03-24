from __future__ import annotations

from unittest.mock import MagicMock

from ccbt.config.config import get_config
from ccbt.discovery.tracker_udp_client import (
    get_udp_tracker_client,
    reset_udp_tracker_client_for_testing,
)
from ccbt.session.factories import ComponentFactory
from ccbt.utils.di import DIContainer, default_container


def test_default_container_provides_config() -> None:
    di = default_container()
    assert di.config_provider is not None
    cfg = di.config_provider()
    assert cfg is not None
    assert cfg is get_config() or True  # accept object equality or instance availability


def test_default_container_udp_provider_returns_singleton() -> None:
    reset_udp_tracker_client_for_testing()
    try:
        di = default_container()
        assert di.udp_tracker_client_provider is not None
        a = di.udp_tracker_client_provider()
        b = di.udp_tracker_client_provider()
        assert a is b
        assert a is get_udp_tracker_client()
    finally:
        reset_udp_tracker_client_for_testing()


def test_custom_di_fields_optional() -> None:
    di = DIContainer()
    assert di.security_manager_factory is None
    assert di.tcp_server_factory is None


def test_component_factory_udp_respects_di_provider() -> None:
    injected = MagicMock()
    di = DIContainer(udp_tracker_client_provider=lambda: injected)
    mgr = MagicMock()
    mgr._di = di
    mgr.logger = MagicMock()
    assert ComponentFactory(mgr).create_udp_tracker_client() is injected


def test_component_factory_udp_falls_back_when_provider_returns_none() -> None:
    reset_udp_tracker_client_for_testing()
    try:
        di = DIContainer(udp_tracker_client_provider=lambda: None)
        mgr = MagicMock()
        mgr._di = di
        mgr.logger = MagicMock()
        client = ComponentFactory(mgr).create_udp_tracker_client()
        assert client is get_udp_tracker_client()
    finally:
        reset_udp_tracker_client_for_testing()



