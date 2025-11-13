"""BitTorrent protocol wrapper.

from __future__ import annotations

Provides a protocol abstraction for the existing BitTorrent implementation.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from ccbt.protocols.base import (
    Protocol,
    ProtocolCapabilities,
    ProtocolState,
    ProtocolType,
)
from ccbt.utils.events import Event, EventType, emit_event

if TYPE_CHECKING:  # pragma: no cover - Only executed during static type checking
    from ccbt.models import PeerInfo, TorrentInfo


class BitTorrentProtocol(Protocol):
    """BitTorrent protocol wrapper."""

    def __init__(self, session_manager=None):
        """Initialize BitTorrent protocol."""
        super().__init__(ProtocolType.BITTORRENT)
        self.session_manager = session_manager
        self.peer_manager = None
        self.tracker_manager = None

        # BitTorrent-specific capabilities
        # Check if Xet is enabled in config
        from ccbt.config.config import get_config

        config = get_config()
        supports_xet = getattr(config.disk, "xet_enabled", False)

        self.capabilities = ProtocolCapabilities(
            supports_encryption=True,
            supports_metadata=True,
            supports_pex=True,
            supports_dht=True,
            supports_webrtc=False,
            supports_ipfs=False,
            supports_xet=supports_xet,
            max_connections=200,
            supports_ipv6=True,
        )

        # BitTorrent components (would be injected in real implementation)
        self.peer_manager = None
        self.tracker_manager = None
        self.dht_manager = None

        # Logger
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        """Start BitTorrent protocol."""
        try:
            # Initialize BitTorrent components
            if self.session_manager:
                await self.session_manager.start()

            # Initialize peer manager if available
            if hasattr(self.session_manager, "peer_manager"):
                self.peer_manager = self.session_manager.peer_manager

            # Initialize tracker manager if available
            if hasattr(self.session_manager, "tracker_manager"):
                self.tracker_manager = self.session_manager.tracker_manager

            # Set state to connected
            self.set_state(ProtocolState.CONNECTED)

            # Emit protocol started event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STARTED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def stop(self) -> None:
        """Stop BitTorrent protocol."""
        try:
            # Stop BitTorrent components
            if self.session_manager:
                await self.session_manager.stop()

            # Set state to disconnected
            self.set_state(ProtocolState.DISCONNECTED)

            # Emit protocol stopped event
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_STOPPED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "timestamp": time.time(),
                    },
                ),
            )

        except Exception:
            self.set_state(ProtocolState.ERROR)
            raise

    async def connect_peer(self, peer_info: PeerInfo) -> bool:
        """Connect to a BitTorrent peer."""
        try:
            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "connect_peer"):
                success = await self.peer_manager.connect_peer(peer_info)
                if success:
                    self.stats.connections_established += 1
                    self.update_stats()
                    return True

            # Fallback to session manager
            if self.session_manager and hasattr(self.session_manager, "connect_peer"):
                success = await self.session_manager.connect_peer(peer_info)
                if success:
                    self.stats.connections_established += 1
                    self.update_stats()
                    return True

            return False

        except Exception as e:
            self.stats.connections_failed += 1
            self.update_stats(errors=1)

            # Emit connection error event
            await emit_event(
                Event(
                    event_type=EventType.PEER_CONNECTION_FAILED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "peer_id": peer_info.peer_id.hex()
                        if peer_info.peer_id
                        else None,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return False

    async def disconnect_peer(self, peer_id: str) -> None:
        """Disconnect from a BitTorrent peer."""
        try:
            # Extract IP from peer_id if it's in "IP:port" format
            # Peers are stored by IP in self.peers (from base Protocol class)
            peer_ip = peer_id.split(":")[0] if ":" in peer_id else peer_id

            # Check if peer exists in our tracking (by IP or full peer_id)
            if (
                peer_ip not in self.peers
                and peer_id not in self.peers
                and peer_ip not in self.active_connections
                and peer_id not in self.active_connections
            ):
                self.logger.debug("Peer %s not found, skipping disconnection", peer_id)
                return

            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "disconnect_peer"):
                await self.peer_manager.disconnect_peer(peer_id)

            # Fallback to session manager
            elif self.session_manager and hasattr(
                self.session_manager, "disconnect_peer"
            ):
                await self.session_manager.disconnect_peer(peer_id)

            # Emit peer disconnected event
            await emit_event(
                Event(
                    event_type=EventType.PEER_DISCONNECTED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "peer_id": peer_id,
                        "timestamp": time.time(),
                    },
                ),
            )

            # Update protocol statistics
            self.update_stats()

            # Remove peer from protocol tracking (try both IP and full peer_id)
            if peer_ip in self.peers:
                self.remove_peer(peer_ip)
            elif peer_id in self.peers:
                self.remove_peer(peer_id)
            else:
                # If not in peers dict, still remove from active_connections
                self.active_connections.discard(peer_ip)
                self.active_connections.discard(peer_id)

        except Exception as e:
            self.update_stats(errors=1)
            self.logger.exception("Error disconnecting peer %s", peer_id)

            # Still emit disconnect event even on error
            await emit_event(
                Event(
                    event_type=EventType.PEER_DISCONNECTED.value,
                    data={
                        "protocol_type": "bittorrent",
                        "peer_id": peer_id,
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            # Still remove peer from tracking
            peer_ip = peer_id.split(":")[0] if ":" in peer_id else peer_id
            if peer_ip in self.peers:
                self.remove_peer(peer_ip)
            elif peer_id in self.peers:
                self.remove_peer(peer_id)
            else:
                self.active_connections.discard(peer_ip)
                self.active_connections.discard(peer_id)

    async def send_message(self, peer_id: str, message: bytes) -> bool:
        """Send message to BitTorrent peer."""
        try:
            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "send_message"):
                success = await self.peer_manager.send_message(peer_id, message)
                if success:
                    self.update_stats(bytes_sent=len(message), messages_sent=1)
                    return True

            # Fallback to session manager
            if self.session_manager and hasattr(self.session_manager, "send_message"):
                success = await self.session_manager.send_message(peer_id, message)
                if success:
                    self.update_stats(bytes_sent=len(message), messages_sent=1)
                    return True

            return False

        except Exception:
            self.update_stats(errors=1)
            return False

    async def receive_message(self, peer_id: str) -> bytes | None:
        """Receive message from BitTorrent peer."""
        try:
            # Use peer manager if available
            if self.peer_manager and hasattr(self.peer_manager, "receive_message"):
                message = await self.peer_manager.receive_message(peer_id)
                if message:
                    self.update_stats(bytes_received=len(message), messages_received=1)
                    return message

            # Fallback to session manager
            if self.session_manager and hasattr(
                self.session_manager, "receive_message"
            ):
                message = await self.session_manager.receive_message(peer_id)
                if message:
                    self.update_stats(bytes_received=len(message), messages_received=1)
                    return message

            return None

        except Exception:
            self.update_stats(errors=1)
            return None

    async def announce_torrent(self, torrent_info: TorrentInfo) -> list[PeerInfo]:
        """Announce torrent to BitTorrent trackers."""
        peers = []

        try:
            # Use tracker manager if available
            if self.tracker_manager and hasattr(self.tracker_manager, "announce"):
                peers = await self.tracker_manager.announce(torrent_info)

            # Fallback to session manager
            elif self.session_manager and hasattr(
                self.session_manager, "announce_torrent"
            ):
                peers = await self.session_manager.announce_torrent(torrent_info)

            return peers

        except Exception as e:
            # Emit tracker error event
            await emit_event(
                Event(
                    event_type=EventType.TRACKER_ERROR.value,
                    data={
                        "protocol_type": "bittorrent",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return peers

    async def scrape_torrent(self, torrent_info: TorrentInfo) -> dict[str, int]:
        """Scrape torrent statistics from BitTorrent trackers.

        Args:
            torrent_info: Torrent information model

        Returns:
            Dictionary with keys: seeders, leechers, completed
            Returns zeros if scraping fails

        """
        stats = {
            "seeders": 0,
            "leechers": 0,
            "completed": 0,
        }

        try:
            # Convert TorrentInfo to torrent_data dict format
            torrent_data = self._torrent_info_to_dict(torrent_info)

            # Get all tracker URLs
            tracker_urls = self._get_tracker_urls(torrent_info)

            if not tracker_urls:
                self.logger.debug("No tracker URLs found for scraping")
                return stats

            # Try scraping from each tracker until we get a successful result
            for tracker_url in tracker_urls:
                try:
                    # Determine tracker type
                    is_udp = tracker_url.startswith("udp://")
                    is_http = tracker_url.startswith(("http://", "https://"))

                    if not is_udp and not is_http:
                        self.logger.debug(
                            "Unsupported tracker URL scheme: %s", tracker_url
                        )
                        continue

                    # Create tracker data dict for this tracker
                    tracker_data = torrent_data.copy()
                    tracker_data["announce"] = tracker_url

                    # Scrape using appropriate client
                    if is_udp:
                        from ccbt.discovery.tracker_udp_client import (
                            AsyncUDPTrackerClient,
                        )

                        udp_client = AsyncUDPTrackerClient()
                        await udp_client.start()

                        try:
                            scrape_result = await udp_client.scrape(tracker_data)
                            if scrape_result:
                                # Map to standardized format
                                stats["seeders"] = scrape_result.get("seeders", 0)
                                stats["leechers"] = scrape_result.get("leechers", 0)
                                stats["completed"] = scrape_result.get("completed", 0)

                                # Success! Return first successful result
                                if stats["seeders"] > 0 or stats["leechers"] > 0:
                                    self.logger.info(
                                        "Successfully scraped from UDP tracker: %s (seeders: %d, leechers: %d)",
                                        tracker_url,
                                        stats["seeders"],
                                        stats["leechers"],
                                    )
                                    return stats
                        finally:
                            await udp_client.stop()

                    else:  # HTTP/HTTPS
                        from ccbt.discovery.tracker import AsyncTrackerClient

                        http_client = AsyncTrackerClient()
                        await http_client.start()

                        try:
                            scrape_result = await http_client.scrape(tracker_data)
                            if scrape_result:
                                # Map to standardized format
                                stats["seeders"] = scrape_result.get("seeders", 0)
                                stats["leechers"] = scrape_result.get("leechers", 0)
                                stats["completed"] = scrape_result.get("completed", 0)

                                # Success! Return first successful result
                                if stats["seeders"] > 0 or stats["leechers"] > 0:
                                    self.logger.info(
                                        "Successfully scraped from HTTP tracker: %s (seeders: %d, leechers: %d)",
                                        tracker_url,
                                        stats["seeders"],
                                        stats["leechers"],
                                    )
                                    return stats
                        finally:
                            await http_client.stop()

                except Exception as e:
                    # Log error but continue to next tracker
                    self.logger.debug(
                        "Failed to scrape from tracker %s: %s", tracker_url, e
                    )
                    continue

            # If we get here, no tracker returned successful results
            self.logger.debug("No trackers returned scrape results")
            return stats

        except Exception as e:
            # Emit error event
            self.logger.exception("Error during tracker scraping")
            await emit_event(
                Event(
                    event_type=EventType.PROTOCOL_ERROR.value,
                    data={
                        "protocol_type": "bittorrent",
                        "error": str(e),
                        "timestamp": time.time(),
                    },
                ),
            )

            return stats

    def _torrent_info_to_dict(self, torrent_info: TorrentInfo) -> dict[str, Any]:
        """Convert TorrentInfo model to torrent_data dict format.

        Args:
            torrent_info: TorrentInfo model

        Returns:
            Dictionary in format expected by tracker clients

        """
        # Build announce_list (flattened list)
        announce_list = []
        if torrent_info.announce_list:
            for tier in torrent_info.announce_list:
                announce_list.extend(tier)

        # Build file_info dict
        file_info = {
            "type": "multi" if len(torrent_info.files) > 1 else "single",
            "total_length": torrent_info.total_length,
            "name": torrent_info.name,
        }

        if torrent_info.files:
            if len(torrent_info.files) == 1:
                file_info["length"] = torrent_info.files[0].length
            else:
                file_info["files"] = [
                    {
                        "length": f.length,
                        "path": f.path or [],
                        "full_path": f.full_path or "",
                    }
                    for f in torrent_info.files
                ]

        return {
            "announce": torrent_info.announce,
            "announce_list": announce_list,
            "info_hash": torrent_info.info_hash,
            "name": torrent_info.name,
            "file_info": file_info,
            "total_length": torrent_info.total_length,
        }

    def _get_tracker_urls(self, torrent_info: TorrentInfo) -> list[str]:
        """Extract all tracker URLs from TorrentInfo.

        Args:
            torrent_info: TorrentInfo model

        Returns:
            List of tracker URLs (announce + all from announce_list)

        """
        urls = []

        # Add primary announce URL
        if torrent_info.announce:
            urls.append(torrent_info.announce)

        # Add URLs from announce_list
        if torrent_info.announce_list:
            for tier in torrent_info.announce_list:
                urls.extend(tier)

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def get_bittorrent_stats(self) -> dict[str, Any]:
        """Get BitTorrent-specific statistics."""
        return {
            "protocol_type": "bittorrent",
            "state": self.state.value,
            "peers_count": len(self.peers),
            "active_connections": len(self.active_connections),
            "stats": {
                "bytes_sent": self.stats.bytes_sent,
                "bytes_received": self.stats.bytes_received,
                "connections_established": self.stats.connections_established,
                "connections_failed": self.stats.connections_failed,
                "messages_sent": self.stats.messages_sent,
                "messages_received": self.stats.messages_received,
                "errors": self.stats.errors,
                "last_activity": self.stats.last_activity,
            },
        }
