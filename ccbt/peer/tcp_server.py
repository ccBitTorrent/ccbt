"""TCP server for accepting incoming BitTorrent peer connections.

This module implements a TCP server that listens on the configured port
to accept incoming peer connections from other BitTorrent clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from ccbt.config.config import get_config
from ccbt.peer.inbound_protocol_classifier import (
    InboundProtocolKind,
    classify_prefix,
)
from ccbt.peer.peer import (
    Handshake,
    ParsedInboundPlainHandshake,
    parse_plaintext_bittorrent_handshake,
)
from ccbt.protocols.bittorrent_v2 import (
    PROTOCOL_STRING_LEN,
    RESERVED_BYTES_LEN,
    ProtocolVersionError,
    expected_plaintext_handshake_total_len,
)
from ccbt.security.mse_handshake import MSEHandshake
from ccbt.security.swarm_auth_policy import evaluate_inbound_admission
from ccbt.utils.exceptions import HandshakeError
from ccbt.utils.shutdown import is_shutting_down

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)


class _ReplayableStreamReader:
    """StreamReader wrapper that supports replaying buffered bytes.

    This is intentionally lightweight and only implements the subset of
    reader APIs used by inbound handshake/peer-acceptance paths.
    """

    def __init__(self, stream_reader: asyncio.StreamReader) -> None:
        self._stream_reader = stream_reader
        self._replay_buffer = bytearray()

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes, preferring buffered replay bytes first."""
        if n < 0:
            msg = "readexactly() argument must be non-negative"
            raise ValueError(msg)
        if n == 0:
            return b""
        if self._replay_buffer:
            if len(self._replay_buffer) >= n:
                data = self._replay_buffer[:n]
                del self._replay_buffer[:n]
                return bytes(data)

            buffered = bytes(self._replay_buffer)
            self._replay_buffer.clear()
            needed = n - len(buffered)
            extra = await self._stream_reader.readexactly(needed)
            return buffered + extra

        return await self._stream_reader.readexactly(n)

    async def read(self, n: int = -1) -> bytes:
        """Read up to n bytes, with buffered bytes drained first."""
        if n == 0:
            return b""
        if n < -1:
            msg = "read() argument must be >= -1"
            raise ValueError(msg)
        if n == -1:
            if self._replay_buffer:
                buffered = bytes(self._replay_buffer)
                self._replay_buffer.clear()
                return buffered + await self._stream_reader.read(-1)
            return await self._stream_reader.read(-1)

        if self._replay_buffer:
            if len(self._replay_buffer) >= n:
                data = self._replay_buffer[:n]
                del self._replay_buffer[:n]
                return bytes(data)

            buffered = bytes(self._replay_buffer)
            self._replay_buffer.clear()
            remaining = n - len(buffered)
            return buffered + await self._stream_reader.read(remaining)

        return await self._stream_reader.read(n)

    def unread(self, data: bytes) -> None:
        """Prepend bytes back into the replay buffer."""
        if not data:
            return
        self._replay_buffer = bytearray(data) + self._replay_buffer

    def at_eof(self) -> bool:
        """Return True when both buffered and underlying reader are exhausted."""
        return not self._replay_buffer and self._stream_reader.at_eof()

    async def wait(self) -> None:
        """Wait until data is available from either replay buffer or source."""
        if self._replay_buffer:
            return
        wait = getattr(self._stream_reader, "wait", None)
        if callable(wait):
            await cast(Any, wait)()


class _MSEInboundSessionResolver:
    """Resolve inbound encrypted streams to a single active torrent session."""

    @staticmethod
    def resolve_session_candidates(
        session_manager: Optional[AsyncSessionManager],
    ) -> list[tuple[Any, bytes]]:
        if session_manager is None:
            return []
        try:
            sessions = list(session_manager.torrents.values())
        except Exception:
            session_manager_logger = getattr(session_manager, "logger", None)
            if isinstance(session_manager_logger, logging.Logger):
                session_manager_logger.debug(
                    "Skipping MSE inbound candidate resolution: torrents map unavailable"
                )
            return []
        candidates: list[tuple[Any, bytes]] = []
        for session in sessions:
            try:
                info_hash = session.info.info_hash
            except Exception as err:
                self_logger = getattr(session_manager, "logger", None)
                if isinstance(self_logger, logging.Logger):
                    self_logger.debug(
                        "Skipping session while resolving MSE inbound candidates: %s",
                        err,
                    )
                continue
            if not isinstance(info_hash, (bytes, bytearray)) or len(info_hash) != 20:
                continue
            candidates.append((session, bytes(info_hash)))
        return candidates

    @staticmethod
    def resolve_single_session(
        session_manager: Optional[AsyncSessionManager],
        info_hash: Optional[bytes]= None,
    ) -> Optional[tuple[Any, bytes]]:
        candidates = _MSEInboundSessionResolver.resolve_session_candidates(
            session_manager
        )
        if info_hash is not None:
            for session, candidate_hash in candidates:
                if candidate_hash == bytes(info_hash):
                    return session, candidate_hash
            return None
        if len(candidates) != 1:
            return None
        return candidates[0]

    @staticmethod
    def resolve_session_candidates_info_hashes(
        session_manager: Optional[AsyncSessionManager],
    ) -> list[bytes]:
        return [
            info_hash
            for _, info_hash in _MSEInboundSessionResolver.resolve_session_candidates(
                session_manager
            )
        ]

    @staticmethod
    def resolve_session_peer_manager(
        session_manager: Optional[AsyncSessionManager],
        info_hash: bytes,
    ) -> Optional[tuple[Any, Any]]:
        resolved = _MSEInboundSessionResolver.resolve_single_session(
            session_manager,
            info_hash=info_hash,
        )
        if resolved is None:
            return None
        session, resolved_info_hash = resolved
        peer_manager = getattr(session, "download_manager", None)
        if peer_manager:
            peer_manager = getattr(peer_manager, "peer_manager", None)
        if not peer_manager:
            peer_manager = getattr(session, "peer_manager", None)
        if not peer_manager or not hasattr(peer_manager, "accept_incoming_encrypted"):
            return None
        return peer_manager, resolved_info_hash


class IncomingPeerServer:
    """TCP server for accepting incoming BitTorrent peer connections."""

    def __init__(
        self, session_manager: AsyncSessionManager, config: Optional[Any]= None
    ):
        """Initialize incoming peer server.

        Args:
            session_manager: AsyncSessionManager instance for routing connections
            config: Configuration object (defaults to get_config() if None)

        """
        self.session_manager = session_manager
        self.config = config or get_config()
        self.server: Optional[asyncio.Server]= None
        self._running = False
        self.logger = logging.getLogger(__name__)
        self._inbound_registration_probation: dict[str, int] = {}
        self._inbound_registration_probation_window = 8.0
        self._inbound_registration_probation_retry_interval = 0.5
        self._probation_tasks: set[asyncio.Task[None]] = set()

    def _register_probation_task(self, task: asyncio.Task[None]) -> None:
        """Track background probation task for shutdown cleanup."""
        self._probation_tasks.add(task)

        def _on_task_done(done_task: asyncio.Task[None]) -> None:
            self._probation_tasks.discard(done_task)

        task.add_done_callback(_on_task_done)

    @staticmethod
    def _transport_hint(protocol_kind: InboundProtocolKind) -> str:
        if protocol_kind == InboundProtocolKind.MSE_P2P:
            return "mse"
        return "plain"

    @staticmethod
    def _supports_ltep(parsed_handshake: ParsedInboundPlainHandshake) -> bool:
        reserved_bytes = getattr(parsed_handshake, "reserved_bytes", None)
        return bool(
            isinstance(reserved_bytes, (bytes, bytearray))
            and len(reserved_bytes) >= 6
            and bool(reserved_bytes[5] & 0x10)
        )

    @staticmethod
    def _is_strict_mode(session: Any) -> bool:
        security = getattr(session, "config", None)
        if security is None:
            return False
        return getattr(
            getattr(security, "authenticated_swarms", None),
            "mode",
            "off",
        ) == "strict"

    def _allow_inbound_admission(
        self,
        peer_socket: object,
        parsed_handshake: ParsedInboundPlainHandshake,
        session: Any,
        protocol_kind: InboundProtocolKind,
    ) -> bool:
        """Evaluate admission and return True when the connection may proceed."""
        if self._is_strict_mode(session) and not self._supports_ltep(parsed_handshake):
            self.logger.debug(
                "Rejecting strict authenticated-swarm inbound peer %s until extension handshake: no LTEP reserved bit",
                peer_socket,
            )
            return False
        decision = evaluate_inbound_admission(
            peer_socket=peer_socket,
            parsed_handshake=parsed_handshake,
            session=session,
            transport_hint=self._transport_hint(protocol_kind),
        )

        if not decision.allowed:
            # Defer strict-mode schema misses to the extension-stage validator.
            if decision.mode == "strict" and decision.reason_code == "missing_schema":
                self.logger.debug(
                    "Deferring strict swarm-auth admission for %s until extension handshake (reason=%s)",
                    peer_socket,
                    decision.reason_code,
                )
                return True

            self.logger.warning(
                "Inbound swarm-auth admission denied for %s (mode=%s reason=%s)",
                peer_socket,
                decision.mode,
                decision.reason_code,
            )
            return False

        return True

    async def start(self) -> None:
        """Start the TCP server.

        Binds to the configured listen_interface and listen_port.
        Supports both IPv4 and IPv6 if enabled.
        """
        if self._running:
            self.logger.warning("TCP server already running")
            return

        if not self.config.network.enable_tcp:
            self.logger.debug("TCP transport disabled, skipping TCP server startup")
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
            # Note: Enhanced port conflict error handling
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
                    self.logger.exception(
                        "Permission denied binding to %s:%d",
                        listen_interface,
                        listen_port,
                    )
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
                self.logger.exception(
                    "Permission denied binding to %s:%d", listen_interface, listen_port
                )
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
            self.logger.debug(
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

        Note: Add delays on Windows to prevent socket buffer exhaustion (WinError 10055).
        ENHANCEMENT: Explicitly close all sockets to ensure immediate port release.
        """
        if not self._running:
            if self._probation_tasks:
                probation_tasks = set(self._probation_tasks)
                self._probation_tasks.clear()
                for task in probation_tasks:
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(task, timeout=0.5)
            return

        self._running = False

        probation_tasks = set(self._probation_tasks)
        self._probation_tasks.clear()
        for task in probation_tasks:
            task.cancel()

        for task in probation_tasks:
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            except Exception as exc:
                self.logger.debug("Error while stopping probation task: %s", exc)

        if self.server:
            # CRITICAL: Explicitly close all sockets before closing server to ensure immediate port release
            if self.server.sockets:
                for sock in self.server.sockets:
                    try:
                        # Close socket explicitly to release port immediately
                        if hasattr(sock, "_closed") and not getattr(
                            sock, "_closed", True
                        ):
                            sock.close()
                    except Exception as e:
                        self.logger.debug("Error closing socket: %s", e)

            self.server.close()
            try:
                await asyncio.wait_for(self.server.wait_closed(), timeout=5.0)
                # Note: Add delay on Windows after server close to prevent buffer exhaustion
                import sys

                if sys.platform == "win32":
                    await asyncio.sleep(0.1)  # 100ms delay on Windows
            except asyncio.TimeoutError:
                self.logger.warning("TCP server close timed out")
            except OSError as e:
                # Note: Handle WinError 10055 gracefully
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
            self.logger.debug("TCP server stopped")

    def is_serving(self) -> bool:
        """Check if the TCP server is currently serving.

        Returns:
            True if server is running and serving, False otherwise

        """
        return self._running and self.server is not None and self.server.is_serving()

    @property
    def port(self) -> Optional[int]:
        """Get the port the server is bound to.

        Returns:
            Port number if server is running, None otherwise

        """
        if not self.server or not self.server.sockets:
            return None
        try:
            # Return the port from the first socket
            sock = self.server.sockets[0]
            sockname = sock.getsockname()
            return sockname[1]
        except (IndexError, OSError):
            return None

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

    def _get_inbound_probation_key(
        self, info_hash: bytes, peer_ip: str, peer_port: int
    ) -> str:
        """Build deterministic key for inbound registration probation."""
        return f"{info_hash.hex()}|{peer_ip}:{peer_port}"

    @staticmethod
    def _extract_probation_info_hash(
        parsed_handshake: ParsedInboundPlainHandshake,
    ) -> bytes:
        """Return the primary v1 hash used for probation tracking."""
        info_hash_v1 = getattr(parsed_handshake, "info_hash_v1", None)
        if isinstance(info_hash_v1, (bytes, bytearray)):
            return bytes(info_hash_v1)
        return b""

    def _format_handshake_info_hash(
        self, parsed_handshake: ParsedInboundPlainHandshake
    ) -> str:
        """Format v1 info hash for structured logs."""
        info_hash = self._extract_probation_info_hash(parsed_handshake)
        if not info_hash:
            return "unknown"
        return info_hash.hex()[:16]

    def _should_probation_inbound(
        self, info_hash: bytes, peer_ip: str, peer_port: int
    ) -> bool:
        """Allow one bounded probation attempt for each peer/info_hash pair."""
        key = self._get_inbound_probation_key(info_hash, peer_ip, peer_port)
        attempts = self._inbound_registration_probation.get(key, 0)
        if attempts >= 1:
            return False
        self._inbound_registration_probation[key] = attempts + 1
        return True

    async def _release_inbound_probation(
        self, info_hash: bytes, peer_ip: str, peer_port: int
    ) -> None:
        """Release probation marker after resolution."""
        self._inbound_registration_probation.pop(
            self._get_inbound_probation_key(info_hash, peer_ip, peer_port), None
        )

    async def _await_session_for_inbound_peer(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        parsed_handshake: ParsedInboundPlainHandshake,
        peer_ip: str,
        peer_port: int,
        start_time: float,
        protocol_classification: InboundProtocolKind,
    ) -> None:
        """Retry inbound session lookup briefly before closing stalled handshakes."""
        if is_shutting_down() or not self._running:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        try:
            session = None
            deadline = (
                asyncio.get_event_loop().time()
                + self._inbound_registration_probation_window
            )
            while (
                session is None
                and asyncio.get_event_loop().time() < deadline
                and self._running
                and not is_shutting_down()
            ):
                if self.session_manager is not None:
                    session = await self.session_manager.get_session_for_info_hash(
                        parsed_handshake
                    )
                if session is None:
                    await asyncio.sleep(
                        self._inbound_registration_probation_retry_interval
                    )

            if session is None:
                if not self._running or is_shutting_down():
                    writer.close()
                    await writer.wait_closed()
                    return
                elapsed = asyncio.get_event_loop().time() - start_time
                self.logger.debug(
                    "No active torrent for info_hash %s from %s:%d after probation wait %.1fs.",
                    self._format_handshake_info_hash(parsed_handshake),
                    peer_ip,
                    peer_port,
                    elapsed,
                )
                writer.close()
                await writer.wait_closed()
                return

            if (
                hasattr(session, "info")
                and session.info
                and hasattr(session.info, "status")
                and session.info.status == "stopped"
            ):
                self.logger.debug(
                    "Probation resolution found stopped session for %s:%d (info_hash=%s)",
                    peer_ip,
                    peer_port,
                    self._format_handshake_info_hash(parsed_handshake),
                )
                writer.close()
                await writer.wait_closed()
                return
            if is_shutting_down() or not self._running:
                writer.close()
                await writer.wait_closed()
                return

            if not self._allow_inbound_admission(
                writer,
                parsed_handshake,
                session,
                protocol_classification,
            ):
                writer.close()
                await writer.wait_closed()
                return

            handshake_info_hash = self._extract_probation_info_hash(parsed_handshake)
            if not handshake_info_hash:
                writer.close()
                await writer.wait_closed()
                return
            handshake = Handshake(
                handshake_info_hash,
                parsed_handshake.peer_id,
                reserved_bytes=parsed_handshake.reserved_bytes,
            )
            await session.accept_incoming_peer(
                reader,
                writer,
                handshake,
                peer_ip,
                peer_port,
                protocol_classification=protocol_classification,
            )
        except Exception:
            self.logger.exception(
                "Error during inbound probation resolution for %s:%d",
                peer_ip,
                peer_port,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        finally:
            await self._release_inbound_probation(
                self._extract_probation_info_hash(parsed_handshake), peer_ip, peer_port
            )

    async def _handle_inbound_mse_connection(
        self,
        reader: _ReplayableStreamReader,
        writer: asyncio.StreamWriter,
        peer_ip: str,
        peer_port: int,
    ) -> None:
        """Run inbound MSE/PE receiver handshake and hand off decrypted payload."""
        try:
            candidates = _MSEInboundSessionResolver.resolve_session_candidates(
                self.session_manager
            )
            info_hash_candidates = [info_hash for _, info_hash in candidates]
            if not candidates:
                self.logger.debug(
                    "MSE/PE inbound %s:%d dropped because no active torrents are available",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

            session, fallback_info_hash = candidates[0]
            peer_manager = getattr(session, "download_manager", None)
            if peer_manager:
                peer_manager = getattr(peer_manager, "peer_manager", None)
            if not peer_manager:
                peer_manager = getattr(session, "peer_manager", None)

            if not peer_manager or not hasattr(
                peer_manager, "accept_incoming_encrypted"
            ):
                self.logger.debug(
                    "MSE/PE inbound %s:%d dropped because peer manager cannot accept encrypted payload",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

            create_mse = getattr(peer_manager, "_create_mse_handshake", None)
            mse = create_mse() if callable(create_mse) else MSEHandshake()  # type: ignore[misc]

            timeout = self.config.network.handshake_timeout
            result = await mse.respond_as_receiver_with_initial_data(
                reader=cast(asyncio.StreamReader, reader),
                writer=writer,
                info_hash=fallback_info_hash,
                initial_payload_size=0,
                initial_payload_timeout=timeout,
                info_hash_candidates=info_hash_candidates,
            )
            resolved_info_hash = getattr(result, "resolved_info_hash", None)
            if result.success and resolved_info_hash is not None:
                resolved_session = _MSEInboundSessionResolver.resolve_single_session(
                    self.session_manager,
                    info_hash=resolved_info_hash,
                )
                if resolved_session is not None:
                    session, _ = resolved_session
                    peer_manager = getattr(session, "download_manager", None)
                    if peer_manager:
                        peer_manager = getattr(peer_manager, "peer_manager", None)
                    if not peer_manager:
                        peer_manager = getattr(session, "peer_manager", None)
                    if not peer_manager or not hasattr(
                        peer_manager, "accept_incoming_encrypted"
                    ):
                        peer_manager = None

            if not result.success or not result.decrypted_initial_data:
                self.logger.debug(
                    "MSE/PE inbound %s:%d handshake failed: success=%s, decrypted_initial_data=%s",
                    peer_ip,
                    peer_port,
                    result.success,
                    result.decrypted_initial_data is not None,
                )
                writer.close()
                await writer.wait_closed()
                return

            try:
                parsed_initial_handshake = parse_plaintext_bittorrent_handshake(
                    bytes(result.decrypted_initial_data)
                )
            except HandshakeError as exc:
                self.logger.debug(
                    "Invalid decrypted MSE/PE handshake from %s:%d: %s",
                    peer_ip,
                    peer_port,
                    exc,
                )
                writer.close()
                await writer.wait_closed()
                return

            if not peer_manager:
                self.logger.debug(
                    "MSE/PE inbound %s:%d handshake failed: peer manager unavailable for resolved session",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

            if not self._allow_inbound_admission(
                writer,
                parsed_initial_handshake,
                session,
                InboundProtocolKind.MSE_P2P,
            ):
                writer.close()
                await writer.wait_closed()
                return

            await peer_manager.accept_incoming_encrypted(
                reader,
                writer,
                result.decrypted_initial_data,
                peer_ip,
                peer_port,
            )

        except Exception:
            self.logger.exception(
                "Error while handling inbound MSE/PE connection from %s:%d",
                peer_ip,
                peer_port,
            )
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

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

        if is_shutting_down() or not self._running:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        try:
            replayable_reader = _ReplayableStreamReader(reader)

            # Stage 1: consume a 28-byte plaintext prefix candidate for classification.
            # This also covers MSE/PE's 4-byte length field + message type checks because we
            # retain all bytes in the replayable reader for downstream fallback paths.
            prefix = await asyncio.wait_for(
                replayable_reader.readexactly(
                    1 + PROTOCOL_STRING_LEN + RESERVED_BYTES_LEN
                ),
                timeout=self.config.network.handshake_timeout,
            )

            protocol_kind = classify_prefix(prefix)
            replayable_reader.unread(prefix)
            if protocol_kind == InboundProtocolKind.UNKNOWN:
                self.logger.debug(
                    "Non-BitTorrent connection from %s:%d (unrecognized protocol lead). "
                    "This may be a port scanner, bot, or unsupported envelope.",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

            if protocol_kind == InboundProtocolKind.MSE_P2P:
                self.logger.debug(
                    "MSE/PE inbound connection from %s:%d entering encrypted receiver path",
                    peer_ip,
                    peer_port,
                )
                await self._handle_inbound_mse_connection(
                    replayable_reader,
                    writer,
                    peer_ip,
                    peer_port,
                )
                return

            # Stage 2: grow the replayable buffer to an allowed plaintext handshake size.
            try:
                valid_total_lengths = expected_plaintext_handshake_total_len(prefix)
            except ProtocolVersionError as exc:
                self.logger.warning(
                    "Invalid handshake prefix from %s:%d while computing plaintext lengths: %s",
                    peer_ip,
                    peer_port,
                    exc,
                )
                writer.close()
                await writer.wait_closed()
                return

            handshake_data = prefix
            parsed_handshake = None
            for expected_len in sorted(set(valid_total_lengths)):
                if len(handshake_data) < expected_len:
                    handshake_data += await asyncio.wait_for(
                        replayable_reader.readexactly(
                            expected_len - len(handshake_data)
                        ),
                        timeout=self.config.network.handshake_timeout,
                    )

                try:
                    parsed_handshake = parse_plaintext_bittorrent_handshake(
                        handshake_data
                    )
                    break
                except HandshakeError:
                    parsed_handshake = None
                    continue

            if parsed_handshake is None:
                self.logger.warning(
                    "Invalid plaintext handshake from %s:%d", peer_ip, peer_port
                )
                writer.close()
                await writer.wait_closed()
                return

            # Compatibility with existing inbound acceptance contract until ord-030 migration:
            # prefer v1 info hash for session lookup.
            if parsed_handshake.info_hash_v1 is None:
                self.logger.warning(
                    "Unsupported parsed handshake variant from %s:%d without v1 info hash.",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

            handshake = Handshake(
                parsed_handshake.info_hash_v1,
                parsed_handshake.peer_id,
                reserved_bytes=parsed_handshake.reserved_bytes,
            )

            # Note: Lookup torrent session by info_hash with retry logic
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
                and self._running
                and not is_shutting_down()
            ):
                if self.session_manager is not None:
                    session = await self.session_manager.get_session_for_info_hash(
                        parsed_handshake
                    )
                else:
                    session = None
                if session is None:
                    await asyncio.sleep(check_interval)

            if session is None:
                if is_shutting_down() or not self._running:
                    writer.close()
                    await writer.wait_closed()
                    return
                elapsed = asyncio.get_event_loop().time() - start_time
                if self._should_probation_inbound(
                    self._extract_probation_info_hash(parsed_handshake),
                    peer_ip,
                    peer_port,
                ):
                    self.logger.debug(
                        "No active torrent for info_hash %s from %s:%d after waiting %.1fs. "
                        "Entering bounded registration probation for this peer.",
                        self._format_handshake_info_hash(parsed_handshake),
                        peer_ip,
                        peer_port,
                        elapsed,
                    )
                    probation_task = asyncio.create_task(
                        self._await_session_for_inbound_peer(
                    cast(asyncio.StreamReader, replayable_reader),
                            writer,
                            parsed_handshake,
                            peer_ip,
                            peer_port,
                            start_time,
                            protocol_kind,
                        )
                    )
                    self._register_probation_task(probation_task)
                    return
                # Note: Check if any sessions exist at all
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
                        self._format_handshake_info_hash(parsed_handshake),
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
                        self._format_handshake_info_hash(parsed_handshake),
                        peer_ip,
                        peer_port,
                        elapsed,
                    )
                writer.close()
                await writer.wait_closed()
                return

            if is_shutting_down() or not self._running:
                writer.close()
                await writer.wait_closed()
                return

            # Note: Check session readiness before accepting connections
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
                    self._format_handshake_info_hash(parsed_handshake),
                    session.info.status,
                    elapsed,
                )
                writer.close()
                await writer.wait_closed()
                return

            # Route to torrent session's peer connection manager
            if not self._allow_inbound_admission(
                writer,
                parsed_handshake,
                session,
                protocol_kind,
            ):
                writer.close()
                await writer.wait_closed()
                return

            await session.accept_incoming_peer(
                cast(asyncio.StreamReader, replayable_reader),
                writer,
                handshake,
                peer_ip,
                peer_port,
                protocol_classification=protocol_kind,
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
            # Note: Handle Windows ConnectionResetError (WinError 10054) gracefully
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


