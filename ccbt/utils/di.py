"""Simple dependency injection container and factories for ccBitTorrent.

The DI container is optional and non-invasive. When not provided, the code
falls back to current direct constructions (get_config() and concrete classes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

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
    config_provider: Callable[[], Config] | None = None
    logger_factory: _Factory | None = None
    metrics_factory: _Factory | None = None

    # Networking / discovery
    tracker_client_factory: _Factory | None = None
    udp_tracker_client_provider: _Factory | None = None
    dht_client_factory: _Factory | None = None
    nat_manager_factory: _Factory | None = None
    tcp_server_factory: _Factory | None = None

    # Security / protocol / peers
    security_manager_factory: _Factory | None = None
    protocol_manager_factory: _Factory | None = None
    peer_service_factory: _Factory | None = None
    peer_connection_manager_factory: _Factory | None = None
    piece_manager_factory: _Factory | None = None
    metadata_exchange_factory: _Factory | None = None

    # Infra
    task_scheduler: _Factory | None = None
    time_provider: _Factory | None = None
    backoff_policy: _Factory | None = None


def default_container(config: Config | None = None) -> DIContainer:
    """Build a container with minimal sensible defaults."""
    cfg = config or get_config()

    def _cfg() -> Config:
        return cfg

    return DIContainer(
        config_provider=_cfg,
        # Other factories intentionally left None; callers fall back to defaults.
    )
