"""TCP server for accepting incoming BitTorrent peer connections.

This module implements a TCP server that listens on the configured port
to accept incoming peer connections from other BitTorrent clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, cast

from ccbt.config.config import get_config
from ccbt.monitoring import get_metrics_collector
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


@dataclass
class _InboundProbationWaitEntry:
    """Pending inbound connection waiting for a per-hash probation slot."""

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    parsed_handshake: ParsedInboundPlainHandshake
    peer_ip: str
    peer_port: int
    start_time: float
    protocol_kind: InboundProtocolKind
    has_any_sessions: bool
    enqueued_at: float


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
            await cast("Any", wait)()


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
            info_hash: Optional[bytes] = None
            try:
                info_hash = session.info.info_hash
            except Exception as err:
                self_logger = getattr(session_manager, "logger", None)
                if isinstance(self_logger, logging.Logger):
                    self_logger.debug(
                        "Skipping session while resolving MSE inbound candidates: %s",
                        err,
                    )
            if info_hash is None or not isinstance(info_hash, (bytes, bytearray)):
                td = getattr(session, "torrent_data", None)
                if isinstance(td, dict):
                    raw_ih = td.get("info_hash")
                    if isinstance(raw_ih, (bytes, bytearray)) and len(raw_ih) == 20:
                        info_hash = bytes(raw_ih)
            if not isinstance(info_hash, (bytes, bytearray)) or len(info_hash) != 20:
                continue
            candidates.append((session, bytes(info_hash)))
        return candidates

    @staticmethod
    def resolve_single_session(
        session_manager: Optional[AsyncSessionManager],
        info_hash: Optional[bytes] = None,
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
    """TCP server for accepting incoming BitTorrent peer connections.

    Unknown-info-hash storms (wrong swarm, stale magnets, port scanners) are bounded via
    ``network.inbound_max_probation_inflight_per_hash``, ``inbound_probation_wait_queue_max_total``,
    ``inbound_probation_queued_max_wait_s``, and ``inbound_unknown_hash_storm_threshold``.
    Tune those on multi-torrent hosts when global probation depth grows without loaded torrents.
    """

    def __init__(
        self, session_manager: AsyncSessionManager, config: Optional[Any] = None
    ):
        """Initialize incoming peer server.

        Args:
            session_manager: AsyncSessionManager instance for routing connections
            config: Configuration object (defaults to get_config() if None)

        """
        self.session_manager = session_manager
        self.config = config or get_config()
        self.server: Optional[asyncio.Server] = None
        self._running = False
        self.logger = logging.getLogger(__name__)
        self._inbound_registration_probation: dict[str, int] = {}
        _net = getattr(self.config, "network", None)
        self._inbound_registration_probation_window = (
            float(getattr(_net, "inbound_probation_window_s", 8.0) or 8.0)
            if _net is not None
            else 8.0
        )
        self._inbound_registration_probation_retry_interval = (
            float(getattr(_net, "inbound_probation_retry_interval_s", 0.5) or 0.5)
            if _net is not None
            else 0.5
        )
        self._probation_tasks: set[asyncio.Task[None]] = set()
        # Unknown-info-hash observability and bounded probation fan-out (wrong swarm / scanners).
        self._inbound_unknown_hash_counts: defaultdict[str, int] = defaultdict(int)
        self._probation_inflight_by_hash: dict[str, int] = {}
        # Allow more concurrent registration waits per hash so magnet/slow-start
        # torrents do not discard viable inbound peers during session registration races.
        self._max_probation_inflight_per_hash = (
            int(getattr(_net, "inbound_max_probation_inflight_per_hash", 8) or 8)
            if _net is not None
            else 8
        )
        self._inbound_unknown_hash_storm_threshold = (
            int(getattr(_net, "inbound_unknown_hash_storm_threshold", 12) or 12)
            if _net is not None
            else 12
        )
        # WARNING log sampling when sessions exist but this info_hash is unknown (storm control).
        _warn_n = 32
        if _net is not None:
            raw_iv = getattr(_net, "inbound_unknown_hash_warning_sample_interval", 32)
            try:
                _warn_n = int(raw_iv)
            except (TypeError, ValueError):
                _warn_n = 32
        self._unknown_inbound_hash_warning_every_n = max(2, min(10_000, _warn_n))
        self._probation_wait_queues: dict[str, deque[_InboundProbationWaitEntry]] = (
            defaultdict(deque)
        )
        self._probation_queue_lock = asyncio.Lock()
        self._probation_wait_queue_max_total = (
            int(getattr(_net, "inbound_probation_wait_queue_max_total", 256) or 256)
            if _net is not None
            else 256
        )
        # Max time a peer may sit in the probation wait queue without a slot (0 = no limit).
        # Keep defensive fallback for legacy test stubs that inject partial network objects.
        self._probation_queued_max_wait_s = (
            float(getattr(_net, "inbound_probation_queued_max_wait_s", 120.0) or 120.0)
            if _net is not None
            else 120.0
        )
        _pmw = self._probation_queued_max_wait_s
        self._probation_wait_sweep_interval_s = (
            min(15.0, max(0.5, _pmw / 4.0)) if _pmw > 0 else 15.0
        )
        self._probation_wait_sweeper_task: Optional[asyncio.Task[None]] = None

    def _probation_wait_queue_total(self) -> int:
        return sum(len(dq) for dq in self._probation_wait_queues.values())

    async def _evict_oldest_probation_waiter_unlocked(self) -> None:
        """Drop the longest-waiting queued inbound peer (global LRU by enqueue time)."""
        best_hk: Optional[str] = None
        best_t = float("inf")
        for hk, dq in self._probation_wait_queues.items():
            if dq and dq[0].enqueued_at < best_t:
                best_t = dq[0].enqueued_at
                best_hk = hk
        if best_hk is None:
            return
        victim_dq = self._probation_wait_queues[best_hk]
        entry = victim_dq.popleft()
        if not victim_dq:
            self._probation_wait_queues.pop(best_hk, None)
        ih = self._extract_probation_info_hash(entry.parsed_handshake)
        await self._release_inbound_probation(ih, entry.peer_ip, entry.peer_port)
        await self._close_writer_safely(entry.writer)
        with contextlib.suppress(Exception):
            get_metrics_collector().increment_counter(
                "inbound_probation_wait_queue_evicted_total",
            )

    async def _expire_stale_probation_waiters_unlocked(
        self, now: float
    ) -> list[_InboundProbationWaitEntry]:
        """Remove waiters past queued max-wait; caller must hold _probation_queue_lock."""
        cap = float(self._probation_queued_max_wait_s)
        if cap <= 0:
            return []
        stale: list[_InboundProbationWaitEntry] = []
        for hk in list(self._probation_wait_queues.keys()):
            dq = self._probation_wait_queues.get(hk)
            if not dq:
                continue
            kept: deque[_InboundProbationWaitEntry] = deque()
            while dq:
                e = dq.popleft()
                if now - e.enqueued_at > cap:
                    stale.append(e)
                else:
                    kept.append(e)
            if kept:
                self._probation_wait_queues[hk] = kept
            else:
                self._probation_wait_queues.pop(hk, None)
        return stale

    async def _finalize_stale_probation_waiters(
        self, stale: list[_InboundProbationWaitEntry]
    ) -> None:
        for entry in stale:
            ih = self._extract_probation_info_hash(entry.parsed_handshake)
            await self._release_inbound_probation(ih, entry.peer_ip, entry.peer_port)
            await self._close_writer_safely(entry.writer)
            with contextlib.suppress(Exception):
                get_metrics_collector().increment_counter(
                    "inbound_probation_wait_queue_expired_total",
                )

    def _ensure_probation_wait_sweeper_started(self) -> None:
        """Background sweep so queued peers time out even without new arrivals or slot releases."""
        if (
            not self._running
            or self._probation_wait_queue_max_total <= 0
            or self._probation_queued_max_wait_s <= 0
        ):
            return
        if (
            self._probation_wait_sweeper_task
            and not self._probation_wait_sweeper_task.done()
        ):
            return
        self._probation_wait_sweeper_task = asyncio.create_task(
            self._probation_wait_sweeper_loop(),
            name="inbound-probation-wait-sweeper",
        )

    async def _probation_wait_sweeper_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(self._probation_wait_sweep_interval_s)
                if not self._running:
                    break
                loop = asyncio.get_event_loop()
                now = loop.time()
                stale: list[_InboundProbationWaitEntry] = []
                async with self._probation_queue_lock:
                    if self._probation_wait_queue_total() == 0:
                        break
                    stale = await self._expire_stale_probation_waiters_unlocked(now)
                if stale:
                    await self._finalize_stale_probation_waiters(stale)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger.debug("Probation wait sweeper error", exc_info=True)
        finally:
            self._probation_wait_sweeper_task = None

    async def _enqueue_inbound_probation_wait(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        parsed_handshake: ParsedInboundPlainHandshake,
        peer_ip: str,
        peer_port: int,
        start_time: float,
        protocol_kind: InboundProtocolKind,
        has_any_sessions: bool,
    ) -> bool:
        """Queue this peer until a probation slot frees. Returns False if queue disabled."""
        if self._probation_wait_queue_max_total <= 0:
            return False
        loop = asyncio.get_event_loop()
        enqueued_at = loop.time()
        ih = self._extract_probation_info_hash(parsed_handshake)
        hk = self._probation_hash_slot_key(ih)
        entry = _InboundProbationWaitEntry(
            reader=reader,
            writer=writer,
            parsed_handshake=parsed_handshake,
            peer_ip=peer_ip,
            peer_port=peer_port,
            start_time=start_time,
            protocol_kind=protocol_kind,
            has_any_sessions=has_any_sessions,
            enqueued_at=enqueued_at,
        )
        stale_pre: list[_InboundProbationWaitEntry] = []
        enqueue_rejected = False
        async with self._probation_queue_lock:
            stale_pre = await self._expire_stale_probation_waiters_unlocked(enqueued_at)
            while (
                self._probation_wait_queue_total()
                >= self._probation_wait_queue_max_total
            ):
                before = self._probation_wait_queue_total()
                await self._evict_oldest_probation_waiter_unlocked()
                after = self._probation_wait_queue_total()
                if after >= before:
                    self.logger.warning(
                        "Probation wait queue eviction did not shrink (before=%d after=%d); "
                        "dropping new inbound from %s:%d to protect bounds",
                        before,
                        after,
                        peer_ip,
                        peer_port,
                    )
                    with contextlib.suppress(Exception):
                        get_metrics_collector().increment_counter(
                            "inbound_probation_wait_queue_enqueue_reject_total",
                        )
                    enqueue_rejected = True
                    break
            if not enqueue_rejected:
                self._probation_wait_queues[hk].append(entry)
        await self._finalize_stale_probation_waiters(stale_pre)
        if enqueue_rejected:
            return False
        with contextlib.suppress(Exception):
            get_metrics_collector().increment_counter("inbound_probation_queued_total")
        self.logger.debug(
            "Queued inbound probation wait for info_hash=%s from %s:%d (global queue size ~%d)",
            self._format_handshake_info_hash(parsed_handshake),
            peer_ip,
            peer_port,
            self._probation_wait_queue_total(),
        )
        self._ensure_probation_wait_sweeper_started()
        return True

    async def _drain_next_probation_wait_after_release(self, info_hash: bytes) -> None:
        """Start the next queued probation for this hash after a slot was released."""
        if self._probation_wait_queue_max_total <= 0:
            return
        hk = self._probation_hash_slot_key(info_hash)
        loop = asyncio.get_event_loop()
        stale_on_drain: list[_InboundProbationWaitEntry] = []
        entry: Optional[_InboundProbationWaitEntry] = None
        async with self._probation_queue_lock:
            stale_on_drain = await self._expire_stale_probation_waiters_unlocked(
                loop.time()
            )
            wait_dq = self._probation_wait_queues.get(hk)
            if wait_dq and self._reserve_probation_slot_for_hash(info_hash):
                entry = wait_dq.popleft()
                if not wait_dq:
                    self._probation_wait_queues.pop(hk, None)
        if stale_on_drain:
            await self._finalize_stale_probation_waiters(stale_on_drain)
        if entry is None:
            return
        if self._should_abort_inbound_registration_wait():
            ih2 = self._extract_probation_info_hash(entry.parsed_handshake)
            await self._release_inbound_probation(
                ih2,
                entry.peer_ip,
                entry.peer_port,
            )
            self._release_probation_slot_for_hash(ih2)
            await self._close_writer_safely(entry.writer)
            await self._drain_next_probation_wait_after_release(ih2)
            return
        self._register_inbound_probation_task(
            entry.reader,
            entry.writer,
            entry.parsed_handshake,
            entry.peer_ip,
            entry.peer_port,
            entry.start_time,
            entry.protocol_kind,
            probation_window_s=self._probation_window_s_for_inbound(
                entry.parsed_handshake,
                entry.has_any_sessions,
            ),
        )

    def _register_inbound_probation_task(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        parsed_handshake: ParsedInboundPlainHandshake,
        peer_ip: str,
        peer_port: int,
        start_time: float,
        protocol_kind: InboundProtocolKind,
        *,
        probation_window_s: float,
    ) -> None:
        with contextlib.suppress(Exception):
            get_metrics_collector().increment_counter("inbound_probation_started_total")
        probation_task = asyncio.create_task(
            self._await_session_for_inbound_peer(
                reader,
                writer,
                parsed_handshake,
                peer_ip,
                peer_port,
                start_time,
                protocol_kind,
                probation_window_s=probation_window_s,
            ),
        )
        self._register_probation_task(probation_task)

    async def _close_all_probation_wait_queues(self) -> None:
        """Drain wait queues on shutdown (writers closed, probation keys released)."""
        async with self._probation_queue_lock:
            entries: list[_InboundProbationWaitEntry] = []
            for dq in self._probation_wait_queues.values():
                entries.extend(list(dq))
            self._probation_wait_queues.clear()
        for entry in entries:
            ih = self._extract_probation_info_hash(entry.parsed_handshake)
            with contextlib.suppress(Exception):
                await self._release_inbound_probation(
                    ih,
                    entry.peer_ip,
                    entry.peer_port,
                )
            await self._close_writer_safely(entry.writer)

    def _should_abort_inbound_registration_wait(self) -> bool:
        """True when inbound session lookup / probation should end immediately.

        Includes global process shutdown and AsyncSessionManager.stop() (TCP may still
        be accepting briefly while the manager is tearing down).
        """
        if not self._running or is_shutting_down():
            return True
        sm = self.session_manager
        if sm is not None:
            fn = getattr(sm, "is_shutting_down", None)
            if callable(fn):
                with contextlib.suppress(Exception):
                    raw = fn()
                    # Mocks may return non-bool truthy objects; only real True aborts
                    if raw is True:
                        return True
        return False

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
    async def _close_writer_safely(writer: asyncio.StreamWriter) -> None:
        """Close writer; ignore reset/broken-pipe errors common after remote hangup."""
        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    @staticmethod
    def _is_strict_mode(session: Any) -> bool:
        security = getattr(session, "config", None)
        if security is None:
            return False
        return (
            getattr(
                getattr(security, "authenticated_swarms", None),
                "mode",
                "off",
            )
            == "strict"
        )

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
            if self._probation_wait_sweeper_task:
                self._probation_wait_sweeper_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._probation_wait_sweeper_task
                self._probation_wait_sweeper_task = None
            if self._probation_tasks:
                probation_tasks = set(self._probation_tasks)
                self._probation_tasks.clear()
                for task in probation_tasks:
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(task, timeout=0.5)
            await self._close_all_probation_wait_queues()
            return

        self._running = False

        if self._probation_wait_sweeper_task:
            self._probation_wait_sweeper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._probation_wait_sweeper_task
            self._probation_wait_sweeper_task = None

        await self._close_all_probation_wait_queues()

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
        """Format v1 info hash prefix for structured logs (full hash is 40 hex chars)."""
        info_hash = self._extract_probation_info_hash(parsed_handshake)
        if not info_hash:
            return "unknown"
        return f"{info_hash.hex()[:16]}(prefix)"

    def _inbound_unknown_hash_metric_key(
        self, parsed_handshake: ParsedInboundPlainHandshake
    ) -> str:
        """Metric / sampling key (16-char hex prefix) for unknown inbound hashes."""
        raw = self._extract_probation_info_hash(parsed_handshake)
        return raw.hex()[:16] if raw else "unknown"

    def _record_inbound_unknown_info_hash(
        self, parsed_handshake: ParsedInboundPlainHandshake
    ) -> None:
        """Count inbound handshakes that did not map to an active session (by hash prefix)."""
        key = self._inbound_unknown_hash_metric_key(parsed_handshake)
        self._inbound_unknown_hash_counts[key] += 1

    def _should_emit_unknown_inbound_hash_warning(self, metric_key: str) -> bool:
        """First event and every Nth per hash prefix emit WARNING; others use DEBUG only."""
        n = self._inbound_unknown_hash_counts.get(metric_key, 0)
        interval = max(2, int(self._unknown_inbound_hash_warning_every_n))
        return n == 1 or (n > 0 and n % interval == 0)

    def _probation_hash_slot_key(self, info_hash: bytes) -> str:
        return info_hash.hex() if info_hash else ""

    def _reserve_probation_slot_for_hash(self, info_hash: bytes) -> bool:
        """Limit concurrent probation waits per info hash to reduce resource burn."""
        hk = self._probation_hash_slot_key(info_hash)
        n = self._probation_inflight_by_hash.get(hk, 0)
        if n >= self._max_probation_inflight_per_hash:
            return False
        self._probation_inflight_by_hash[hk] = n + 1
        return True

    def _release_probation_slot_for_hash(self, info_hash: bytes) -> None:
        hk = self._probation_hash_slot_key(info_hash)
        n = self._probation_inflight_by_hash.get(hk, 0)
        if n <= 1:
            self._probation_inflight_by_hash.pop(hk, None)
        else:
            self._probation_inflight_by_hash[hk] = n - 1

    def get_inbound_unknown_info_hash_metrics(self) -> dict[str, int]:
        """Snapshot of unknown inbound info-hash counts (16-char hex prefix keys)."""
        return dict(self._inbound_unknown_hash_counts)

    def _inbound_session_registration_wait_cap_s(
        self,
        parsed_handshake: ParsedInboundPlainHandshake,
        has_any_sessions: bool,
        *,
        metadata_pending: bool = False,
    ) -> float:
        """Max poll time for session lookup before probation / reject (wrong-swarm aware)."""
        net = getattr(self.config, "network", None)
        no_sess = (
            float(
                getattr(net, "inbound_registration_wait_cap_no_sessions_s", 60.0)
                or 60.0
            )
            if net is not None
            else 60.0
        )
        default_cap = (
            float(getattr(net, "inbound_registration_wait_cap_default_s", 15.0) or 15.0)
            if net is not None
            else 15.0
        )
        storm_cap = (
            float(getattr(net, "inbound_registration_wait_cap_storm_s", 8.0) or 8.0)
            if net is not None
            else 8.0
        )
        meta_cap = (
            float(
                getattr(
                    net,
                    "inbound_registration_wait_cap_metadata_pending_s",
                    60.0,
                )
                or 60.0
            )
            if net is not None
            else 60.0
        )
        if metadata_pending:
            return meta_cap
        if not has_any_sessions:
            return no_sess
        prefix = self._inbound_unknown_hash_metric_key(parsed_handshake)
        prior = self._inbound_unknown_hash_counts.get(prefix, 0)
        storm_th = max(1, int(self._inbound_unknown_hash_storm_threshold))
        if prior >= storm_th:
            return storm_cap
        return default_cap

    def _grace_poll_seconds_after_probation_cap(
        self,
        parsed_handshake: ParsedInboundPlainHandshake,
        has_any_sessions: bool,
    ) -> float:
        """Extra session poll when probation slots are saturated."""
        net = getattr(self.config, "network", None)
        no_sess = (
            float(getattr(net, "inbound_grace_poll_seconds_no_sessions_s", 8.0) or 8.0)
            if net is not None
            else 8.0
        )
        storm_gp = (
            float(getattr(net, "inbound_grace_poll_seconds_storm_s", 1.5) or 1.5)
            if net is not None
            else 1.5
        )
        default_gp = (
            float(getattr(net, "inbound_grace_poll_seconds_default_s", 2.5) or 2.5)
            if net is not None
            else 2.5
        )
        if not has_any_sessions:
            return no_sess
        prefix = self._inbound_unknown_hash_metric_key(parsed_handshake)
        storm_th = max(1, int(self._inbound_unknown_hash_storm_threshold))
        if self._inbound_unknown_hash_counts.get(prefix, 0) >= storm_th:
            return storm_gp
        return default_gp

    def _probation_window_s_for_inbound(
        self,
        parsed_handshake: ParsedInboundPlainHandshake,
        has_any_sessions: bool,
    ) -> float:
        """Bounded probation retry window; shorter under unknown-hash storms."""
        net = getattr(self.config, "network", None)
        storm_win = (
            float(getattr(net, "inbound_probation_window_storm_s", 4.0) or 4.0)
            if net is not None
            else 4.0
        )
        if not has_any_sessions:
            return float(self._inbound_registration_probation_window)
        prefix = self._inbound_unknown_hash_metric_key(parsed_handshake)
        storm_th = max(1, int(self._inbound_unknown_hash_storm_threshold))
        if self._inbound_unknown_hash_counts.get(prefix, 0) >= storm_th:
            return storm_win
        return float(self._inbound_registration_probation_window)

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

    async def _grace_poll_session_for_handshake(
        self,
        parsed_handshake: ParsedInboundPlainHandshake,
        *,
        seconds: float,
    ) -> Any:
        """Short extra poll when probation fan-out is saturated (registration race)."""
        if self.session_manager is None:
            return None
        loop = asyncio.get_event_loop()
        deadline = loop.time() + max(0.0, seconds)
        while (
            loop.time() < deadline
            and not self._should_abort_inbound_registration_wait()
        ):
            session = await self.session_manager.get_session_for_info_hash(
                parsed_handshake
            )
            if session is not None:
                return session
            await asyncio.sleep(0.15)
        return None

    async def _await_session_for_inbound_peer(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        parsed_handshake: ParsedInboundPlainHandshake,
        peer_ip: str,
        peer_port: int,
        start_time: float,
        protocol_classification: InboundProtocolKind,
        *,
        probation_window_s: Optional[float] = None,
    ) -> None:
        """Retry inbound session lookup briefly before closing stalled handshakes."""
        if self._should_abort_inbound_registration_wait():
            await self._close_writer_safely(writer)
            return

        try:
            session = None
            window = (
                float(probation_window_s)
                if probation_window_s is not None
                else float(self._inbound_registration_probation_window)
            )
            deadline = asyncio.get_event_loop().time() + max(0.5, window)
            while (
                session is None
                and asyncio.get_event_loop().time() < deadline
                and not self._should_abort_inbound_registration_wait()
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
                if self._should_abort_inbound_registration_wait():
                    await self._close_writer_safely(writer)
                    return
                elapsed = asyncio.get_event_loop().time() - start_time
                self.logger.debug(
                    "No active torrent for info_hash %s from %s:%d after probation wait %.1fs.",
                    self._format_handshake_info_hash(parsed_handshake),
                    peer_ip,
                    peer_port,
                    elapsed,
                )
                self._record_inbound_unknown_info_hash(parsed_handshake)
                await self._close_writer_safely(writer)
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
                await self._close_writer_safely(writer)
                return
            if self._should_abort_inbound_registration_wait():
                await self._close_writer_safely(writer)
                return

            if not self._allow_inbound_admission(
                writer,
                parsed_handshake,
                session,
                protocol_classification,
            ):
                await self._close_writer_safely(writer)
                return

            handshake_info_hash = self._extract_probation_info_hash(parsed_handshake)
            if not handshake_info_hash:
                await self._close_writer_safely(writer)
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
            with contextlib.suppress(Exception):
                get_metrics_collector().increment_counter(
                    "inbound_probation_resolved_total",
                )
        except Exception:
            self.logger.exception(
                "Error during inbound probation resolution for %s:%d",
                peer_ip,
                peer_port,
            )
            await self._close_writer_safely(writer)
        finally:
            ih = self._extract_probation_info_hash(parsed_handshake)
            await self._release_inbound_probation(ih, peer_ip, peer_port)
            self._release_probation_slot_for_hash(ih)
            await self._drain_next_probation_wait_after_release(ih)

    def _mse_inbound_pre_handshake_poll_cap_s(self, has_any_sessions: bool) -> float:
        """Upper bound to wait for routable sessions before MSE (no parsed handshake yet)."""
        net = getattr(self.config, "network", None)
        no_sess = (
            float(
                getattr(net, "inbound_registration_wait_cap_no_sessions_s", 60.0)
                or 60.0
            )
            if net is not None
            else 60.0
        )
        default_cap = (
            float(getattr(net, "inbound_registration_wait_cap_default_s", 15.0) or 15.0)
            if net is not None
            else 15.0
        )
        return no_sess if not has_any_sessions else default_cap

    async def _session_manager_torrent_count(self) -> int:
        """Active torrent count; uses manager lock when present (tests may omit lock)."""
        sm = self.session_manager
        if sm is None:
            return 0
        lock = getattr(sm, "lock", None)
        if lock is not None:
            async with lock:
                return len(getattr(sm, "torrents", {}) or {})
        return len(getattr(sm, "torrents", {}) or {})

    async def _poll_until_mse_session_candidates(
        self,
        *,
        peer_ip: str,
        peer_port: int,
    ) -> list[tuple[Any, bytes]]:
        """Wait briefly for torrents to become visible (startup / registration race)."""
        if self.session_manager is None:
            return []
        has_any_sessions = (await self._session_manager_torrent_count()) > 0
        cap = self._mse_inbound_pre_handshake_poll_cap_s(has_any_sessions)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + max(0.0, cap)
        interval = 0.2
        candidates: list[tuple[Any, bytes]] = []
        while (
            loop.time() < deadline
            and not self._should_abort_inbound_registration_wait()
        ):
            candidates = _MSEInboundSessionResolver.resolve_session_candidates(
                self.session_manager
            )
            if candidates:
                return candidates
            await asyncio.sleep(interval)
        if not candidates:
            self.logger.debug(
                "MSE/PE inbound %s:%d no routable session candidates after %.1fs poll "
                "(has_any_sessions=%s)",
                peer_ip,
                peer_port,
                cap,
                has_any_sessions,
            )
        return candidates

    @staticmethod
    def _filter_valid_mse_candidate_hashes(
        candidates: list[tuple[Any, bytes]],
    ) -> list[bytes]:
        """Only 20-byte info hashes are valid for MSE key derivation."""
        return [
            h
            for _, h in candidates
            if isinstance(h, (bytes, bytearray)) and len(h) == 20
        ]

    def _peer_manager_for_session(self, session: Any) -> Any:
        peer_manager = getattr(session, "download_manager", None)
        if peer_manager:
            peer_manager = getattr(peer_manager, "peer_manager", None)
        if not peer_manager:
            peer_manager = getattr(session, "peer_manager", None)
        return peer_manager

    async def _handle_inbound_mse_connection(
        self,
        reader: _ReplayableStreamReader,
        writer: asyncio.StreamWriter,
        peer_ip: str,
        peer_port: int,
    ) -> None:
        """Run inbound MSE/PE receiver handshake and hand off decrypted payload."""
        if self._should_abort_inbound_registration_wait():
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return
        try:
            candidates = await self._poll_until_mse_session_candidates(
                peer_ip=peer_ip, peer_port=peer_port
            )
            info_hash_candidates = self._filter_valid_mse_candidate_hashes(candidates)
            if not candidates or not info_hash_candidates:
                self.logger.debug(
                    "MSE/PE inbound %s:%d dropped because no active torrents are available",
                    peer_ip,
                    peer_port,
                )
                writer.close()
                await writer.wait_closed()
                return

            session, fallback_info_hash = candidates[0]
            peer_manager = self._peer_manager_for_session(session)

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

            timeout = float(self.config.network.handshake_timeout)
            # Bounded outer wait so a broken/stuck receiver cannot hang the handler indefinitely.
            outer_deadline = max(timeout + 2.0, timeout * 3.0 + 1.0)
            try:
                result = await asyncio.wait_for(
                    mse.respond_as_receiver_with_initial_data(
                        reader=cast("asyncio.StreamReader", reader),
                        writer=writer,
                        info_hash=fallback_info_hash,
                        initial_payload_size=0,
                        initial_payload_timeout=timeout,
                        info_hash_candidates=info_hash_candidates,
                    ),
                    timeout=outer_deadline,
                )
            except asyncio.CancelledError:
                await self._close_writer_safely(writer)
                raise
            except asyncio.TimeoutError:
                self.logger.debug(
                    "MSE/PE inbound %s:%d receiver handshake exceeded outer timeout %.1fs",
                    peer_ip,
                    peer_port,
                    outer_deadline,
                )
                await self._close_writer_safely(writer)
                return

            resolved_info_hash = getattr(result, "resolved_info_hash", None)
            if isinstance(resolved_info_hash, (bytes, bytearray)):
                resolved_info_hash = bytes(resolved_info_hash)
            else:
                resolved_info_hash = None
            if len(resolved_info_hash or b"") != 20:
                resolved_info_hash = None

            if result.success and resolved_info_hash is not None:
                resolved_session = _MSEInboundSessionResolver.resolve_single_session(
                    self.session_manager,
                    info_hash=resolved_info_hash,
                )
                if resolved_session is not None:
                    session, _ = resolved_session
                    peer_manager = self._peer_manager_for_session(session)
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
                await self._close_writer_safely(writer)
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
                await self._close_writer_safely(writer)
                return

            v1 = parsed_initial_handshake.info_hash_v1
            if v1 is None or not isinstance(v1, (bytes, bytearray)) or len(v1) != 20:
                self.logger.debug(
                    "MSE/PE inbound %s:%d decrypted handshake missing v1 info hash",
                    peer_ip,
                    peer_port,
                )
                await self._close_writer_safely(writer)
                return
            v1_bytes = bytes(v1)

            if resolved_info_hash is None:
                recovered = _MSEInboundSessionResolver.resolve_single_session(
                    self.session_manager,
                    info_hash=v1_bytes,
                )
                if recovered is not None:
                    session, _ = recovered
                    peer_manager = self._peer_manager_for_session(session)
                else:
                    # Do not route using the provisional first candidate when crypto hash was absent.
                    session = None
                    peer_manager = None
                resolved_info_hash = v1_bytes
            elif resolved_info_hash != v1_bytes:
                self.logger.debug(
                    "MSE/PE inbound %s:%d resolved crypto hash disagrees with plaintext handshake",
                    peer_ip,
                    peer_port,
                )
                await self._close_writer_safely(writer)
                return

            if not peer_manager:
                has_any_sessions = (await self._session_manager_torrent_count()) > 0
                polled_session = await self._grace_poll_session_for_handshake(
                    parsed_initial_handshake,
                    seconds=self._grace_poll_seconds_after_probation_cap(
                        parsed_initial_handshake,
                        has_any_sessions,
                    ),
                )
                if polled_session is not None:
                    session = polled_session
                    peer_manager = self._peer_manager_for_session(session)

            if not peer_manager:
                self.logger.debug(
                    "MSE/PE inbound %s:%d handshake failed: peer manager unavailable for resolved session",
                    peer_ip,
                    peer_port,
                )
                await self._close_writer_safely(writer)
                return

            if self._should_abort_inbound_registration_wait():
                await self._close_writer_safely(writer)
                return

            if not self._allow_inbound_admission(
                writer,
                parsed_initial_handshake,
                session,
                InboundProtocolKind.MSE_P2P,
            ):
                await self._close_writer_safely(writer)
                return

            await peer_manager.accept_incoming_encrypted(
                reader,
                writer,
                result.decrypted_initial_data,
                peer_ip,
                peer_port,
            )

        except asyncio.CancelledError:
            await self._close_writer_safely(writer)
            raise
        except Exception:
            self.logger.exception(
                "Error while handling inbound MSE/PE connection from %s:%d",
                peer_ip,
                peer_port,
            )
            await self._close_writer_safely(writer)

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

        if self._should_abort_inbound_registration_wait():
            await self._close_writer_safely(writer)
            return

        self.logger.debug("Incoming connection from %s:%d", peer_ip, peer_port)

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
            # Shorter wait when other torrents are already active (likely wrong-swarm inbound).
            session = None
            has_any_sessions = False
            if self.session_manager:
                async with self.session_manager.lock:
                    has_any_sessions = len(self.session_manager.torrents) > 0
            metadata_pending = False
            if self.session_manager is not None:
                with contextlib.suppress(Exception):
                    metadata_pending = (
                        await self.session_manager.metadata_pending_for_info_hash(
                            parsed_handshake
                        )
                    )
            # When other torrents are active, long waits mostly burn resources on wrong-swarm
            # inbound; use a shorter cap (further reduced if this prefix is already noisy).
            max_wait_time = self._inbound_session_registration_wait_cap_s(
                parsed_handshake,
                has_any_sessions,
                metadata_pending=metadata_pending,
            )
            check_interval = 0.2  # Check every 200ms
            start_time = asyncio.get_event_loop().time()

            while (
                session is None
                and (asyncio.get_event_loop().time() - start_time) < max_wait_time
                and not self._should_abort_inbound_registration_wait()
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
                if self._should_abort_inbound_registration_wait():
                    writer.close()
                    await writer.wait_closed()
                    return
                elapsed = asyncio.get_event_loop().time() - start_time
                probation_ih = self._extract_probation_info_hash(parsed_handshake)
                if self._should_probation_inbound(probation_ih, peer_ip, peer_port):
                    if self._reserve_probation_slot_for_hash(probation_ih):
                        self.logger.debug(
                            "No active torrent for info_hash %s from %s:%d after waiting %.1fs. "
                            "Entering bounded registration probation for this peer.",
                            self._format_handshake_info_hash(parsed_handshake),
                            peer_ip,
                            peer_port,
                            elapsed,
                        )
                        self._register_inbound_probation_task(
                            cast("asyncio.StreamReader", replayable_reader),
                            writer,
                            parsed_handshake,
                            peer_ip,
                            peer_port,
                            start_time,
                            protocol_kind,
                            probation_window_s=self._probation_window_s_for_inbound(
                                parsed_handshake,
                                has_any_sessions,
                            ),
                        )
                        return
                    queued = await self._enqueue_inbound_probation_wait(
                        cast("asyncio.StreamReader", replayable_reader),
                        writer,
                        parsed_handshake,
                        peer_ip,
                        peer_port,
                        start_time,
                        protocol_kind,
                        has_any_sessions,
                    )
                    if queued:
                        return
                    with contextlib.suppress(Exception):
                        get_metrics_collector().increment_counter(
                            "inbound_probation_cap_skipped_total",
                        )
                    self.logger.debug(
                        "No active torrent for info_hash %s from %s:%d — skipping probation "
                        "(max %d concurrent probation wait(s) for this hash already in flight); "
                        "grace-polling session registration briefly",
                        self._format_handshake_info_hash(parsed_handshake),
                        peer_ip,
                        peer_port,
                        self._max_probation_inflight_per_hash,
                    )
                    session = await self._grace_poll_session_for_handshake(
                        parsed_handshake,
                        seconds=self._grace_poll_seconds_after_probation_cap(
                            parsed_handshake,
                            has_any_sessions,
                        ),
                    )
                    if session is None:
                        with contextlib.suppress(Exception):
                            get_metrics_collector().increment_counter(
                                "inbound_grace_poll_miss_total",
                            )
                if session is None:
                    self._record_inbound_unknown_info_hash(parsed_handshake)
                    # Note: Check if any sessions exist at all
                    # If no sessions are registered, this is expected during startup - use DEBUG level
                    # If sessions exist but this one doesn't, it's a real issue - use WARNING level
                    if self.session_manager:
                        async with self.session_manager.lock:
                            has_any_sessions = len(self.session_manager.torrents) > 0
                    else:
                        has_any_sessions = False

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
                        # Sessions exist but this one wasn't found — sample WARNING to limit log storms.
                        unk_key = self._inbound_unknown_hash_metric_key(
                            parsed_handshake
                        )
                        total_for_prefix = self._inbound_unknown_hash_counts.get(
                            unk_key, 0
                        )
                        ih_fmt = self._format_handshake_info_hash(parsed_handshake)
                        if self._should_emit_unknown_inbound_hash_warning(unk_key):
                            self.logger.warning(
                                "No active torrent for info_hash %s from %s:%d after waiting %.1fs. "
                                "Session may not be registered yet or torrent not active. "
                                "This may indicate slow session initialization "
                                "(especially for magnet links) or session registration failure. "
                                "If this is a magnet link, metadata fetching may still be in progress. "
                                "(unknown-hash occurrence #%d for this prefix; see metrics)",
                                ih_fmt,
                                peer_ip,
                                peer_port,
                                elapsed,
                                total_for_prefix,
                            )
                        else:
                            self.logger.debug(
                                "No active torrent for info_hash %s from %s:%d after waiting %.1fs. "
                                "Session may not be registered yet or torrent not active. "
                                "This may indicate slow session initialization "
                                "(especially for magnet links) or session registration failure. "
                                "If this is a magnet link, metadata fetching may still be in progress. "
                                "[suppressed WARNING #%d for prefix %s; emit every %d]",
                                ih_fmt,
                                peer_ip,
                                peer_port,
                                elapsed,
                                total_for_prefix,
                                unk_key,
                                self._unknown_inbound_hash_warning_every_n,
                            )
                    writer.close()
                    await writer.wait_closed()
                    return

            if self._should_abort_inbound_registration_wait():
                writer.close()
                await writer.wait_closed()
                return

            if session is None:
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
                cast("asyncio.StreamReader", replayable_reader),
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
