"""Minimal UDP tracker server (BEP 15) for ccBitTorrent.

from __future__ import annotations

Implements connection and announce actions with an in-memory peer store.
This is a simplified implementation for development/testing.
"""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import struct
import time

MAGIC_CONNECTION_ID = 0x41727101980  # initial magic

logger = logging.getLogger(__name__)


class InMemoryPeerStore:
    """In-memory peer store for UDP tracker server."""

    def __init__(self):
        """Initialize in-memory peer store."""
        # info_hash (bytes) -> { (ip, port) -> last_seen }
        self.torrents: dict[bytes, dict[tuple[str, int], float]] = {}
        self.interval = 1800

    def announce(self, info_hash: bytes, ip: str, port: int, event: int) -> bytes:
        """Handle peer announce request."""
        now = time.time()
        peers = self.torrents.setdefault(info_hash, {})

        key = (ip, port)
        # event codes: 0:none, 1:completed, 2:started, 3:stopped
        if event == 3:
            peers.pop(key, None)
        else:
            peers[key] = now

        # cleanup
        cutoff = now - 3600
        for k, ts in list(peers.items()):
            if ts < cutoff:
                peers.pop(k, None)

        # build compact peers
        compact = bytearray()
        for peer_ip, peer_port in peers:
            try:
                compact.extend(socket.inet_aton(peer_ip))
                compact.extend(peer_port.to_bytes(2, "big"))
            except OSError:
                continue

        return bytes(compact)


class UDPTracker:
    """UDP tracker server implementation."""

    def __init__(self, host: str = "0.0.0.0", port: int = 6969):  # nosec B104
        """Initialize UDP tracker server."""
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.store = InMemoryPeerStore()
        self._shutdown = False

    def serve_forever(self):
        """Start UDP tracker server loop."""
        while not self._shutdown:
            try:
                data, addr = self.sock.recvfrom(2048)
                if len(data) < 16:
                    continue
                with contextlib.suppress(Exception):
                    action, transaction_id = struct.unpack("!II", data[8:16])
                    if action == 0:
                        self._handle_connect(data, addr, transaction_id)
                    elif action == 1:
                        self._handle_announce(data, addr, transaction_id)
                    else:
                        # unsupported; send error
                        self._send_error(addr, transaction_id, b"Unsupported action")
            except OSError:
                # Socket closed or invalid, break the loop
                break
            except Exception as exc:  # S112: log and continue
                logger.debug("UDP tracker serve_forever loop error: %s", exc)
                continue

    def shutdown(self):
        """Shutdown the UDP tracker server."""
        self._shutdown = True
        with contextlib.suppress(OSError):  # SIM105
            self.sock.close()

    def _handle_connect(self, _data: bytes, addr, transaction_id: int):
        # response: action(0), transaction_id, connection_id (random 64-bit)
        connection_id = struct.unpack("!Q", os.urandom(8))[0]
        resp = struct.pack("!IIQ", 0, transaction_id, connection_id)
        self.sock.sendto(resp, addr)

    def _handle_announce(self, data: bytes, addr, transaction_id: int):
        # request: connection_id(8) action(4) transaction_id(4) info_hash(20) peer_id(20)
        # downloaded(8) left(8) uploaded(8) event(4) IP(4) key(4) num_want(4) port(2)
        if len(data) < 98:
            self._send_error(addr, transaction_id, b"Bad announce length")
            return
        info_hash = data[16:36]
        # peer_id = data[36:56]
        # downloaded, left, uploaded = struct.unpack('!QQQ', data[56:80])
        event = struct.unpack("!I", data[80:84])[0]
        # ip = data[84:88]  # 0 means use sender IP
        # key = data[88:92]
        # num_want = struct.unpack('!i', data[92:96])[0]
        port = struct.unpack("!H", data[96:98])[0]

        sender_ip = addr[0]
        peers_compact = self.store.announce(info_hash, sender_ip, port, event)

        # leechers/seeders unknown; set 0
        interval = self.store.interval
        header = struct.pack("!IIi", 1, transaction_id, interval)
        body = struct.pack("!II", 0, 0) + peers_compact
        self.sock.sendto(header + body, addr)

    def _send_error(self, addr, transaction_id: int, message: bytes):
        resp = struct.pack("!II", 3, transaction_id) + message
        self.sock.sendto(resp, addr)


def run_udp_tracker(host: str = "0.0.0.0", port: int = 6969):  # nosec B104
    """Run UDP tracker server."""
    srv = UDPTracker(host, port)
    srv.serve_forever()


if __name__ == "__main__":
    run_udp_tracker()
