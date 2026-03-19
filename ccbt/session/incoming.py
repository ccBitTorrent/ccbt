"""Incoming connection handling.

This module handles incoming peer connections, including connection acceptance,
handshake processing, and initial peer setup.
"""

from __future__ import annotations

import asyncio
from typing import Any


class IncomingPeerHandler:
    """Handle incoming peer acceptance and queued processing for a session."""

    def __init__(self, session: Any) -> None:
        """Initialize the incoming peer handler with an AsyncTorrentSession instance."""
        self.s = session  # AsyncTorrentSession instance

    async def accept_incoming_peer(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        handshake: Any,
        peer_ip: str,
        peer_port: int,
    ) -> None:
        """Accept an incoming peer connection.

        Args:
            reader: Stream reader for the connection
            writer: Stream writer for the connection
            handshake: Handshake data
            peer_ip: Peer IP address
            peer_port: Peer port number

        """
        # Note: Access peer_manager via download_manager (it's stored there)
        # Fallback to direct peer_manager attribute if it exists (set by some setup code)
        peer_manager = getattr(self.s, "download_manager", None)
        if peer_manager:
            peer_manager = getattr(peer_manager, "peer_manager", None)
        if not peer_manager:
            peer_manager = getattr(self.s, "peer_manager", None)

        if not peer_manager:
            self.s.logger.info(
                "Peer manager not ready yet, queueing incoming peer %s:%d for later processing",
                peer_ip,
                peer_port,
            )
            try:
                queue = self.s.get_incoming_peer_queue()
                await queue.put((reader, writer, handshake, peer_ip, peer_port))
                self.s.logger.debug(
                    "Queued incoming peer %s:%d (queue size: %d)",
                    peer_ip,
                    peer_port,
                    queue.qsize(),
                )
            except Exception as e:
                self.s.logger.warning(
                    "Failed to queue incoming peer %s:%d: %s. Closing connection.",
                    peer_ip,
                    peer_port,
                    e,
                )
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            return

        # Check connection limits
        if hasattr(peer_manager, "connections"):
            current_connections = len(peer_manager.connections)
            max_peers = self.s.config.network.max_peers_per_torrent
            if current_connections >= max_peers:
                self.s.logger.debug(
                    "Rejecting incoming connection from %s:%d: max peers per torrent reached (%d/%d)",
                    peer_ip,
                    peer_port,
                    current_connections,
                    max_peers,
                )
                writer.close()
                await writer.wait_closed()
                return

        # Route to peer manager's accept_incoming method
        if hasattr(peer_manager, "accept_incoming"):
            try:
                await peer_manager.accept_incoming(
                    reader, writer, handshake, peer_ip, peer_port
                )
            except Exception:
                self.s.logger.exception(
                    "Error accepting incoming peer from %s:%d", peer_ip, peer_port
                )
                try:
                    writer.close()
                    await writer.wait_closed()
                except (ConnectionResetError, OSError):
                    # Note: Handle Windows ConnectionResetError (WinError 10054) gracefully
                    # Remote host closed connection - this is normal
                    pass
                except Exception:
                    pass
        else:
            self.s.logger.warning(
                "peer_manager does not support accept_incoming method"
            )
            writer.close()
            await writer.wait_closed()

    async def run_queue_processor(self) -> None:
        """Process queued incoming peer connections.

        This method continuously processes peers that were queued when
        the peer manager was not yet ready.
        """
        self.s.logger.debug(
            "Starting incoming peer queue processor for %s", self.s.info.name
        )
        while not self.s.stopped:
            try:
                try:
                    (
                        reader,
                        writer,
                        handshake,
                        peer_ip,
                        peer_port,
                    ) = await asyncio.wait_for(
                        self.s.get_incoming_peer_queue().get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                max_wait = 30.0
                wait_interval = 0.5
                waited = 0.0
                # Note: Check peer_manager via download_manager
                peer_manager = None
                while waited < max_wait and not self.s.stopped:
                    # Try to get peer_manager from download_manager
                    if hasattr(self.s, "download_manager") and self.s.download_manager:
                        peer_manager = getattr(
                            self.s.download_manager, "peer_manager", None
                        )
                    if not peer_manager:
                        peer_manager = getattr(self.s, "peer_manager", None)
                    if peer_manager:
                        break
                    await asyncio.sleep(wait_interval)
                    waited += wait_interval

                if self.s.stopped:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    continue

                if not peer_manager:
                    self.s.logger.warning(
                        "Peer manager not ready after %d seconds, closing queued peer %s:%d",
                        max_wait,
                        peer_ip,
                        peer_port,
                    )
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    continue

                if hasattr(peer_manager, "accept_incoming"):
                    try:
                        await peer_manager.accept_incoming(
                            reader, writer, handshake, peer_ip, peer_port
                        )
                    except Exception:
                        self.s.logger.exception(
                            "Error accepting queued peer %s:%d (processed after delay)",
                            peer_ip,
                            peer_port,
                        )
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                else:
                    self.s.logger.warning(
                        "peer_manager does not support accept_incoming for queued peer"
                    )
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception:
                self.s.logger.exception("Error in incoming peer queue processor")
                await asyncio.sleep(0.5)
