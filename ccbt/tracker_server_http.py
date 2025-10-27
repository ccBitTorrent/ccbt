"""Simple HTTP tracker server (BEP 3 style) for ccBitTorrent.

Provides /announce endpoint with compact peer lists and minimal state.
"""

import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Tuple
from urllib.parse import parse_qs, unquote_to_bytes, urlparse

from .bencode import encode


class InMemoryTrackerStore:
    def __init__(self):
        # info_hash -> {peer_key -> (ip, port, last_seen)}
        self.torrents: Dict[bytes, Dict[Tuple[str, int], float]] = {}
        self.interval = 1800  # 30 minutes

    def announce(self, info_hash: bytes, ip: str, port: int, event: str) -> bytes:
        now = time.time()
        peers = self.torrents.setdefault(info_hash, {})

        key = (ip, port)
        if event == "stopped":
            peers.pop(key, None)
        else:
            peers[key] = now

        # Cleanup stale peers (1 hour)
        cutoff = now - 3600
        stale = [k for k, ts in peers.items() if ts < cutoff]
        for k in stale:
            peers.pop(k, None)

        # Build compact peers
        compact = bytearray()
        for (peer_ip, peer_port) in peers.keys():
            try:
                compact.extend(socket.inet_aton(peer_ip))
                compact.extend(peer_port.to_bytes(2, "big"))
            except OSError:
                continue

        response = {
            b"interval": self.interval,
            b"peers": bytes(compact),
        }
        return encode(response)


class AnnounceHandler(BaseHTTPRequestHandler):
    store = InMemoryTrackerStore()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/announce":
            self.send_error(404)
            return

        params = parse_qs(parsed.query)
        try:
            info_hash_enc = params.get("info_hash", [None])[0]
            peer_id_enc = params.get("peer_id", [None])[0]
            port_str = params.get("port", ["0"])[0]
            event = params.get("event", [""])[0]

            if info_hash_enc is None or peer_id_enc is None:
                raise ValueError("missing info_hash or peer_id")

            # Decode binary params as raw percent-decoded bytes
            info_hash = unquote_to_bytes(info_hash_enc)
            # peer_id not used for store, but validate format
            _ = unquote_to_bytes(peer_id_enc)

            port = int(port_str)
            ip = self.client_address[0]

            body = self.store.announce(info_hash, ip, port, event)

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            failure = {b"failure reason": str(e).encode("utf-8")}
            body = encode(failure)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)


def run_http_tracker(host: str = "0.0.0.0", port: int = 6969):
    server = HTTPServer((host, port), AnnounceHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()

if __name__ == "__main__":
    run_http_tracker()


