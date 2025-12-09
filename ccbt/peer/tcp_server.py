"""TCP server for accepting incoming BitTorrent peer connections.

This module implements a TCP server that listens on the configured port
to accept incoming peer connections from other BitTorrent clients.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import TYPE_CHECKING, Any

from ccbt.config.config import get_config
from ccbt.utils.exceptions import HandshakeError

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)


class IncomingPeerServer:
    """TCP server for accepting incoming BitTorrent peer connections."""

    def __init__(self, session_manager: AsyncSessionManager, config: Any | None = None):
        """Initialize incoming peer server.

        Args:
            session_manager: AsyncSessionManager instance for routing connections
            config: Configuration object (defaults to get_config() if None)

        """
        self.session_manager = session_manager
        self.config = config or get_config()
        self.server: asyncio.Server | None = None
        self._running = False
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start the TCP server.

        Binds to the configured listen_interface and listen_port.
        Supports both IPv4 and IPv6 if enabled.
        """
        if self._running:
            self.logger.warning("TCP server already running")
            return

        if not self.config.network.enable_tcp:
            self.logger.info("TCP transport disabled, skipping TCP server startup")
            return

        listen_interface = self.config.network.listen_interface or "0.0.0.0"  # nosec B104 - Network service must bind to all interfaces to accept peer connections
        # Use listen_port_tcp if available, fallback to listen_port for backward compatibility
        listen_port = (
            self.config.network.listen_port_tcp or self.config.network.listen_port
        )

        try:
            # Start TCP server
            self.server = await asyncio.start_server(
                self._handle_connection,
                host=listen_interface,
                port=listen_port,
                family=socket.AF_UNSPEC,  # Support both IPv4 and IPv6
                reuse_address=True,
            )
        except OSError as e:
            # CRITICAL FIX: Enhanced port conflict error handling
            error_code = e.errno if hasattr(e, "errno") else None
            import sys

            if sys.platform == "win32":
                if error_code == 10048:  # WSAEADDRINUSE
                    from ccbt.utils.port_checker import get_port_conflict_resolution

                    resolution = get_port_conflict_resolution(listen_port, "tcp")
                    error_msg = (
                        f"TCP port {listen_port} is already in use.\n"
                        f"Error: {e}\n\n"
                        f"{resolution}"
                    )
                    self.logger.exception("TCP port %d is already in use", listen_port)
                    raise RuntimeError(error_msg) from e
                if error_code == 10013:  # WSAEACCES
                    error_msg = (
                        f"Permission denied binding to {listen_interface}:{listen_port}.\n"
                        f"Error: {e}\n\n"
                        f"Resolution: Run with administrator privileges or change the port."
                    )
                    self.logger.exception("Permission denied binding to %s:%d", listen_interface, listen_port)
                    raise RuntimeError(error_msg) from e
            elif error_code == 98:  # EADDRINUSE
                from ccbt.utils.port_checker import get_port_conflict_resolution

                resolution = get_port_conflict_resolution(listen_port, "tcp")
                error_msg = (
                    f"TCP port {listen_port} is already in use.\n"
                    f"Error: {e}\n\n"
                    f"{resolution}"
                )
                self.logger.exception("TCP port %d is already in use", listen_port)
                raise RuntimeError(error_msg) from e
            elif error_code == 13:  # EACCES
                error_msg = (
                    f"Permission denied binding to {listen_interface}:{listen_port}.\n"
                    f"Error: {e}\n\n"
                    f"Resolution: Run with root privileges or change the port to >= 1024."
                )
                self.logger.exception("Permission denied binding to %s:%d", listen_interface, listen_port)
                raise RuntimeError(error_msg) from e
            # Re-raise other OSErrors as-is
            raise

        # Get actual address(es) the server is bound to
        try:
            server_addresses = []
            if self.server.sockets:
                for sock in self.server.sockets:
                    sockname = sock.getsockname()
                    server_addresses.append(f"{sockname[0]}:{sockname[1]}")
                    # Verify socket is actually listening
                    if sock.fileno() != -1:
                        self.logger.debug(
                            "TCP server socket bound: %s:%d (fd=%d)",
                            sockname[0],
                            sockname[1],
                            sock.fileno(),
                        )
                    else:
                        self.logger.warning(
                            "TCP server socket has invalid file descriptor: %s:%d",
                            sockname[0],
                            sockname[1],
                        )
            else:
                self.logger.error("TCP server started but no sockets were created!")
                msg = "TCP server failed to bind to any sockets"
                raise RuntimeError(msg)

            self._running = True
            self.logger.info(
                "TCP server started on %s (interface=%s, port=%d, sockets=%d)",
                ", ".join(server_addresses) if server_addresses else "unknown",
                listen_interface,
                listen_port,
                len(self.server.sockets),
            )

            # Verify server is actually serving
            if not self.server.is_serving():
                self.logger.error(
                    "TCP server is not serving despite start() completing!"
                )
                msg = "TCP server failed to start serving"
                raise RuntimeError(msg)
        except Exception:
            # Handle any other exceptions
            self.logger.exception("Failed to start TCP server")
            raise

    async def stop(self) -> None:
        """Stop the TCP server gracefully.
        
        CRITICAL FIX: Add delays on Windows to prevent socket buffer exhaustion (WinError 10055).
        """
        if not self._running:
            return

        self._running = False

        if self.server:
            self.server.close()
            try:
                await asyncio.wait_for(self.server.wait_closed(), timeout=5.0)
                # CRITICAL FIX: Add delay on Windows after server close to prevent buffer exhaustion
                import sys
                if sys.platform == "win32":
                    await asyncio.sleep(0.1)  # 100ms delay on Windows
            except asyncio.TimeoutError:
                self.logger.warning("TCP server close timed out")
            except OSError as e:
                # CRITICAL FIX: Handle WinError 10055 gracefully
                error_code = getattr(e, "winerror", None) or getattr(e, "errno", None)
                if error_code == 10055:
                    self.logger.debug(
                        "WinError 10055 (socket buffer exhaustion) during TCP server close. "
                        "This is a transient Windows issue. Continuing..."
                    )
                else:
                    self.logger.debug("OSError waiting for server to close: %s", e)
            except Exception as e:
                self.logger.debug("Error waiting for server to close: %s", e)

            self.server = None
            self.logger.info("TCP server stopped")

    def is_serving(self) -> bool:
        """Check if the TCP server is currently serving.

        Returns:
            True if server is running and serving, False otherwise

        """
        return self._running and self.server is not None and self.server.is_serving()

    def get_server_addresses(self) -> list[str]:
        """Get list of addresses the server is bound to.

        Returns:
            List of "host:port" strings

        """
        if not self.server or not self.server.sockets:
            return []
        addresses = []
        for sock in self.server.sockets:
            sockname = sock.getsockname()
            addresses.append(f"{sockname[0]}:{sockname[1]}")
        return addresses

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming TCP connection.

        Reads the BitTorrent handshake, validates it, and routes to the
        appropriate torrent session.

        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for outgoing data

        """
        peer_addr = writer.get_extra_info("peername")
        if peer_addr:
            peer_ip, peer_port = peer_addr[0], peer_addr[1]
        else:
            peer_ip, peer_port = "unknown", 0

        self.logger.debug("Incoming connection from %s:%d", peer_ip, peer_port)

        try:
            # Read first byte to determine protocol length
            # This allows us to detect non-BitTorrent connections early
            protocol_len_byte = await asyncio.wait_for(
                reader.readexactly(1),
                timeout=self.config.network.handshake_timeout,
            )

            protocol_len = protocol_len_byte[0]

            # Validate protocol length early to reject non-BitTorrent connections
            if protocol_len != 19:
                self.logger.debug(
                    "Non-BitTorrent connection from %s:%d (protocol length: %d, expected 19). "
                    "This may be a port scanner, bot, or different protocol.",
                    peer_ip,
                    peer_port,
                    protocol_len,
                )
                writer.close()
                await writer.wait_closed()
                return

            # Read remaining 67 bytes of v1 handshake
            remaining_data = await asyncio.wait_for(
                reader.readexactly(67),
                timeout=self.config.network.handshake_timeout,
            )

            handshake_data = protocol_len_byte + remaining_data

            # Parse and validate handshake
            from ccbt.peer.peer import Handshake

            try:
                handshake = Handshake.decode(handshake_data)
            except HandshakeError as e:
                self.logger.warning(
                    "Invalid handshake from %s:%d: %s", peer_ip, peer_port, e
                )
                writer.close()
                await writer.wait_closed()
                return

            # CRITICAL FIX: Lookup torrent session by info_hash with retry logic
            # Session may not be registered yet if it's starting in background
            # Wait up to 60 seconds for session registration before rejecting connection
            # Increased to 60s to handle slow session initialization, especially for magnet links
            # Magnet links take longer to initialize (metadata fetching) than torrent files
            session = None
            max_wait_time = 60.0  # Maximum time to wait for session registration (increased to 60s for magnet links)
            check_interval = 0.2  # Check every 200ms
            start_time = asyncio.get_event_loop().time()

            while (
                session is None
                and (asyncio.get_event_loop().time() - start_time) < max_wait_time
            ):
                session = await self.session_manager.get_session_for_info_hash(
                    handshake.info_hash
                )
                if session is None:
                    await asyncio.sleep(check_interval)

            if session is None:
                elapsed = asyncio.get_event_loop().time() - start_time
                # CRITICAL FIX: Check if any sessions exist at all
                # If no sessions are registered, this is expected during startup - use DEBUG level
                # If sessions exist but this one doesn't, it's a real issue - use WARNING level
                has_any_sessions = False
                if self.session_manager:
                    async with self.session_manager.lock:
                        has_any_sessions = len(self.session_manager.torrents) > 0
                
                if not has_any_sessions:
                    # No sessions registered yet - expected during startup
                    self.logger.debug(
                        "No active torrent for info_hash %s from %s:%d after waiting %.1fs. "
                        "No sessions registered yet (this is normal during daemon startup).",
                        handshake.info_hash.hex()[:16],
                        peer_ip,
                        peer_port,
                        elapsed,
                    )
                else:
                    # Sessions exist but this one wasn't found - this is a real issue
                    self.logger.warning(
                        "No active torrent for info_hash %s from %s:%d after waiting %.1fs. "
                        "Session may not be registered yet or torrent not active. "
                        "This may indicate slow session initialization (especially for magnet links) or session registration failure. "
                        "If this is a magnet link, metadata fetching may still be in progress.",
                        handshake.info_hash.hex()[:16],
                        peer_ip,
                        peer_port,
                        elapsed,
                    )
                writer.close()
                await writer.wait_closed()
                return

            # CRITICAL FIX: Check session readiness before accepting connections
            # Reject connections if session is stopped (not ready to accept peers)
            if (
                hasattr(session, "info")
                and session.info
                and hasattr(session.info, "status")
                and session.info.status == "stopped"
            ):
                elapsed = asyncio.get_event_loop().time() - start_time
                self.logger.debug(
                    "Rejecting connection from %s:%d for info_hash %s: session is stopped (not ready). "
                    "Session status: %s (waited %.1fs for registration)",
                    peer_ip,
                    peer_port,
                    handshake.info_hash.hex()[:16],
                    session.info.status,
                    elapsed,
                )
                writer.close()
                await writer.wait_closed()
                return

            # Route to torrent session's peer connection manager
            await session.accept_incoming_peer(
                reader, writer, handshake, peer_ip, peer_port
            )

        except asyncio.TimeoutError:
            self.logger.warning(
                "Handshake timeout from %s:%d (timeout=%.1fs)",
                peer_ip,
                peer_port,
                self.config.network.handshake_timeout,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                # Remote host closed connection - this is normal
                pass
        except asyncio.IncompleteReadError:
            self.logger.debug(
                "Incomplete handshake from %s:%d (connection closed early)",
                peer_ip,
                peer_port,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                # Remote host closed connection - this is normal
                pass
        except (ConnectionResetError, OSError) as e:
            # CRITICAL FIX: Handle Windows ConnectionResetError (WinError 10054) gracefully
            # This occurs when remote host closes connection during handshake or processing
            import sys

            if sys.platform == "win32":
                winerror = getattr(e, "winerror", None)
                if winerror == 10054:  # WSAECONNRESET
                    self.logger.debug(
                        "Connection reset by peer %s:%d (WinError 10054) - this is normal",
                        peer_ip,
                        peer_port,
                    )
                else:
                    self.logger.debug(
                        "Connection error from %s:%d: %s (WinError %s)",
                        peer_ip,
                        peer_port,
                        type(e).__name__,
                        winerror,
                    )
            else:
                self.logger.debug(
                    "Connection reset by peer %s:%d - this is normal",
                    peer_ip,
                    peer_port,
                )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass  # Ignore errors during cleanup
        except Exception:
            self.logger.exception(
                "Error handling incoming connection from %s:%d",
                peer_ip,
                peer_port,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionResetError, OSError):
                # Remote host closed connection - this is normal
                pass
            except Exception:
                pass  # Ignore other errors during cleanup
