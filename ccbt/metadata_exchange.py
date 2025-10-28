"""Metadata exchange (BEP 10 + ut_metadata) for magnet downloads.

from __future__ import annotations

Connects to peers, negotiates the extension protocol, and downloads
the torrent metadata (info dictionary) in pieces.
"""

from __future__ import annotations

import hashlib
import logging
import math
import socket
import struct
from typing import Any

from ccbt.bencode import BencodeDecoder, BencodeEncoder

logger = logging.getLogger(__name__)

EXT_PROTOCOL_FLAG_BYTE = 5  # reserved[5] |= 0x10
EXT_PROTOCOL_FLAG_MASK = 0x10
METADATA_PIECE_SIZE = 16384


def _handshake(info_hash: bytes, peer_id: bytes) -> bytes:
    pstr = b"BitTorrent protocol"
    reserved = bytearray(8)
    reserved[EXT_PROTOCOL_FLAG_BYTE] |= EXT_PROTOCOL_FLAG_MASK
    return struct.pack("B", len(pstr)) + pstr + bytes(reserved) + info_hash + peer_id


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            msg = "Connection closed"
            raise ConnectionError(msg)
        buf += chunk
    return buf


def _send_extended_handshake(sock: socket.socket) -> None:
    payload = BencodeEncoder().encode({b"m": {b"ut_metadata": 1}})
    msg = struct.pack("!IBB", 2 + len(payload), 20, 0) + payload
    sock.sendall(msg)


def _recv_message(sock: socket.socket) -> tuple[int, bytes]:
    header = _read_exact(sock, 4)
    length = struct.unpack("!I", header)[0]
    if length == 0:
        return (0, b"")
    payload = _read_exact(sock, length)
    return (length, payload)


def fetch_metadata_from_peers(
    info_hash: bytes,
    peers: list[dict[str, Any]],
    timeout: float = 5.0,
    peer_id: bytes | None = None,
) -> dict[bytes, Any] | None:
    """Fetch torrent metadata from a list of peers."""
    if peer_id is None:
        peer_id = b"-CC0101-" + b"x" * 12

    for peer in peers[:10]:  # limit attempts
        ip = peer.get("ip")
        port = peer.get("port")
        if not ip or not port:
            continue
        try:
            with socket.create_connection((ip, port), timeout=timeout) as sock:
                sock.settimeout(timeout)

                # Handshake
                sock.sendall(_handshake(info_hash, peer_id))
                hs = _read_exact(sock, 68)
                if (
                    len(hs) != 68
                    or hs[1:20] != b"BitTorrent protocol"
                    or hs[28:48] != info_hash
                ):
                    continue

                # Extended handshake
                _send_extended_handshake(sock)

                ut_metadata_id = None
                metadata_size = None

                # Read messages until we get extended handshake
                for _ in range(10):
                    length, payload = _recv_message(sock)
                    if length <= 0:
                        continue
                    msg_id = payload[0]
                    if msg_id != 20:
                        continue
                    ext_id = payload[1]
                    if ext_id == 0:
                        # extended handshake response
                        decoder = BencodeDecoder(payload[2:])
                        data = decoder.decode()
                        # keys may be bytes
                        m = data.get(b"m") or {}
                        ut_metadata_id = m.get(b"ut_metadata")
                        metadata_size = data.get(b"metadata_size")
                        break

                if not ut_metadata_id or not metadata_size:
                    continue

                num_pieces = math.ceil(int(metadata_size) / METADATA_PIECE_SIZE)
                pieces = [None] * num_pieces  # type: ignore[list-item]

                # Request each piece
                for idx in range(num_pieces):
                    req_dict = {b"msg_type": 0, b"piece": idx}
                    req_payload = BencodeEncoder().encode(req_dict)
                    req_msg = (
                        struct.pack(
                            "!IBB",
                            2 + len(req_payload),
                            20,
                            int(ut_metadata_id),
                        )
                        + req_payload
                    )
                    sock.sendall(req_msg)

                    # Await piece
                    for _ in range(20):
                        length, payload = _recv_message(sock)
                        if length <= 0 or payload[0] != 20:
                            continue
                        if payload[1] != int(ut_metadata_id):
                            continue
                        # Parse header dict
                        decoder = BencodeDecoder(payload[2:])
                        header = decoder.decode()
                        msg_type = header.get(b"msg_type")
                        piece_index = header.get(b"piece")
                        if msg_type == 1 and piece_index == idx:
                            header_len = decoder.pos
                            piece_data = payload[2 + header_len :]
                            pieces[idx] = piece_data
                            break

                if any(p is None for p in pieces):
                    continue

                metadata = b"".join(pieces)  # type: ignore[arg-type]
                # Decode to dict
                info = BencodeDecoder(metadata).decode()
                # Validate hash
                info_encoded = BencodeEncoder().encode(info)
                if hashlib.sha1(info_encoded).digest() != info_hash:  # nosec B324 - SHA-1 required by BitTorrent protocol (BEP 3)
                    continue
                return info
        except Exception as e:
            logger.debug("Failed to fetch metadata from peer: %s", e)
            continue

    return None
