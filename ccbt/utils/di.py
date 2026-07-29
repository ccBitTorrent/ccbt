"""Simple dependency injection container and factories for ccBitTorrent.

The DI container is optional and non-invasive. When not provided, the code
falls back to current direct constructions (get_config() and concrete classes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from ccbt.config.config import Config, get_config


class _Factory(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class DIContainer:
    """Holds factories/providers for constructing services.

    All attributes are optional; missing factories should be handled by callers
    with sensible defaults.
    """

    # Core providers
    config_provider: Optional[Callable[[], Config]] = None
    logger_factory: Optional[_Factory] = None
    metrics_factory: Optional[_Factory] = None

    # Networking / discovery
    tracker_client_factory: Optional[_Factory] = None
    udp_tracker_client_provider: Optional[_Factory] = None
    dht_client_factory: Optional[_Factory] = None
    nat_manager_factory: Optional[_Factory] = None
    tcp_server_factory: Optional[_Factory] = None

    # Security / protocol / peers
    security_manager_factory: Optional[_Factory] = None
    protocol_manager_factory: Optional[_Factory] = None
    peer_service_factory: Optional[_Factory] = None
    peer_connection_manager_factory: Optional[_Factory] = None
    piece_manager_factory: Optional[_Factory] = None
    metadata_exchange_factory: Optional[_Factory] = None

    # Infra
    task_scheduler: Optional[_Factory] = None
    time_provider: Optional[_Factory] = None
    backoff_policy: Optional[_Factory] = None


def default_udp_tracker_client_provider() -> Any:
    """Return the process-wide UDP tracker client singleton."""
    from ccbt.discovery.tracker_udp_client import get_udp_tracker_client

    return get_udp_tracker_client()


def default_container(config: Optional[Config] = None) -> DIContainer:
    """Build a container with minimal sensible defaults."""
    cfg = config or get_config()

    def _cfg() -> Config:
        return cfg

    return DIContainer(
        config_provider=_cfg,
        udp_tracker_client_provider=default_udp_tracker_client_provider,
        # Other factories intentionally left None; callers fall back to defaults.
    )
