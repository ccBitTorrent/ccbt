"""Component factory methods for dependency injection."""

from __future__ import annotations

from typing import Any

from ccbt import session as _session_mod


class ComponentFactory:
    """Factory for creating session manager components with DI support."""

    def __init__(self, manager: Any) -> None:
        """Initialize component factory.

        Args:
            manager: AsyncSessionManager instance

        """
        self.manager = manager
        self._di = manager._di
        self.logger = manager.logger

    def create_security_manager(self) -> Any | None:
        """Create security manager with DI fallback.

        Returns:
            SecurityManager instance or None if creation fails

        """
        if self._di and self._di.security_manager_factory:
            try:
                return self._di.security_manager_factory()
            except Exception:
                self.logger.debug(
                    "DI security_manager_factory failed, falling back", exc_info=True
                )
        try:
            from ccbt.security.security_manager import SecurityManager

            return SecurityManager()
        except Exception:
            return None

    def create_dht_client(self, bind_ip: str, bind_port: int) -> Any | None:
        """Create DHT client with DI fallback.

        Args:
            bind_ip: IP address to bind to
            bind_port: Port to bind to

        Returns:
            AsyncDHTClient instance or None if creation fails

        """
        if self._di and self._di.dht_client_factory:
            try:
                return self._di.dht_client_factory(bind_ip=bind_ip, bind_port=bind_port)
            except Exception as e:
                self.logger.debug(
                    "DI dht_client_factory failed, falling back: %s", e, exc_info=True
                )
        try:
            dht_client = _session_mod.AsyncDHTClient(
                bind_ip=bind_ip,
                bind_port=bind_port,
            )
            # BEP 27: Set callback to check if torrent is private
            # This allows DHT client to skip operations for private torrents
            if hasattr(self.manager, "private_torrents"):
                dht_client.is_private_torrent = lambda info_hash: info_hash in self.manager.private_torrents
            return dht_client
        except Exception as e:
            self.logger.error(
                "Failed to create DHT client: %s", e, exc_info=True
            )
            return None

    def create_nat_manager(self) -> Any | None:
        """Create NAT manager with DI fallback.

        Returns:
            NATManager instance or None if creation fails

        """
        if self._di and self._di.nat_manager_factory:
            try:
                return self._di.nat_manager_factory(self.manager.config)
            except Exception:
                self.logger.debug(
                    "DI nat_manager_factory failed, falling back", exc_info=True
                )
        try:
            from ccbt.nat.manager import NATManager

            return NATManager(self.manager.config)
        except Exception:
            return None

    def create_tcp_server(self) -> Any | None:
        """Create TCP server with DI fallback.

        Returns:
            IncomingPeerServer instance or None if creation fails

        """
        if self._di and self._di.tcp_server_factory:
            try:
                return self._di.tcp_server_factory(self.manager, self.manager.config)
            except Exception as e:
                self.logger.debug(
                    "DI tcp_server_factory failed, falling back: %s", e, exc_info=True
                )
        try:
            from ccbt.peer.tcp_server import IncomingPeerServer

            return IncomingPeerServer(self.manager, self.manager.config)
        except Exception as e:
            self.logger.error(
                "Failed to create TCP server: %s", e, exc_info=True
            )
            return None
