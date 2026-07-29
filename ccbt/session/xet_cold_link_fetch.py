"""Fetch XET folder metadata from peers for cold tonic link resolution.

When the session has no cached metadata and no connected peers for a workspace,
this module discovers peers (via discovery module) and fetches .tonic metadata
from them using the XET extension (FOLDER_METADATA_REQUEST/RESPONSE).
"""

from __future__ import annotations

import asyncio
import logging
import struct
from contextlib import suppress
from typing import Any, Optional

from ccbt.core.tonic import TonicFile
from ccbt.extensions.xet import XetExtension
from ccbt.extensions.xet_metadata import XetMetadataExchange
from ccbt.protocols.bittorrent_v2 import (
    HANDSHAKE_V2_SIZE,
    ProtocolVersionError,
    create_v2_handshake,
    parse_v2_handshake,
)

logger = logging.getLogger(__name__)

# Default peer ID for cold-link fetcher (20 bytes)
_COLD_LINK_PEER_ID = b"-CCX01-" + b"0" * 14

# BEP 10 extended message type
_EXTENDED_MSG_ID = 20

# Max peers to try in parallel
_MAX_PEERS_TO_TRY = 10

# Read timeout per message
_READ_TIMEOUT = 15.0


def _normalize_peers(peers: list[Any]) -> list[tuple[str, int]]:
    """Normalize peer list to (ip, port) tuples."""
    result: list[tuple[str, int]] = []
    for p in peers:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            ip, port = str(p[0]), int(p[1])
            result.append((ip, port))
        elif isinstance(p, dict):
            ip = p.get("ip") or p.get("host")
            port = p.get("port")
            if ip is not None and port is not None:
                result.append((str(ip), int(port)))
    return result


async def _connect_and_fetch_one(
    workspace_id: bytes,
    ip: str,
    port: int,
    timeout: float,
) -> Optional[bytes]:
    """Connect to one peer, perform v2 handshake + extended + XET metadata request, return .tonic bytes."""
    if len(workspace_id) != 32:
        return None
    xet_ext = XetExtension()
    xet_meta = XetMetadataExchange(xet_ext)
    handshake_bytes = create_v2_handshake(workspace_id, _COLD_LINK_PEER_ID)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=min(timeout, 10.0),
        )
    except (OSError, asyncio.TimeoutError, ConnectionError) as e:
        logger.debug("Cold link fetch: connect to %s:%s failed: %s", ip, port, e)
        return None
    try:
        writer.write(handshake_bytes)
        await asyncio.wait_for(writer.drain(), timeout=5.0)
        peer_handshake = await asyncio.wait_for(
            reader.readexactly(HANDSHAKE_V2_SIZE),
            timeout=_READ_TIMEOUT,
        )
        try:
            parsed = parse_v2_handshake(peer_handshake)
        except ProtocolVersionError:
            logger.debug("Cold link fetch: invalid handshake from %s:%s", ip, port)
            return None
        info_hash_v2 = parsed.get("info_hash_v2")
        if not info_hash_v2 or info_hash_v2 != workspace_id:
            logger.debug("Cold link fetch: workspace_id mismatch from %s:%s", ip, port)
            return None

        # BEP 10 extended handshake: send our extensions (we want xet)
        from ccbt.core.bencode import BencodeEncoder

        ext_handshake = BencodeEncoder().encode({b"m": {b"xet": 1}})
        ext_msg = (
            struct.pack("!I", 2 + len(ext_handshake))
            + struct.pack("!BB", 20, 0)
            + ext_handshake
        )
        writer.write(ext_msg)
        await asyncio.wait_for(writer.drain(), timeout=5.0)

        # Read until we get extended handshake (msg_id 20, ext_id 0)
        ut_xet_id: Optional[int] = None
        for _ in range(20):
            len_buf = await asyncio.wait_for(
                reader.readexactly(4), timeout=_READ_TIMEOUT
            )
            msg_len = struct.unpack("!I", len_buf)[0]
            if msg_len == 0:
                continue
            if msg_len > 2 * 1024 * 1024:
                break
            payload = await asyncio.wait_for(
                reader.readexactly(msg_len), timeout=_READ_TIMEOUT
            )
            if len(payload) < 2:
                continue
            msg_id = payload[0]
            if msg_id != _EXTENDED_MSG_ID:
                continue
            ext_id = payload[1]
            if ext_id == 0:
                from ccbt.core.bencode import BencodeDecoder

                dec = BencodeDecoder(payload[2:])
                data = dec.decode()
                m = data.get(b"m") or data.get("m") or {}
                if isinstance(m, dict):
                    ut_xet_id = m.get(b"xet") or m.get("xet")
                    if ut_xet_id is not None:
                        ut_xet_id = int(ut_xet_id)
                break
        if ut_xet_id is None:
            logger.debug("Cold link fetch: peer %s:%s does not support xet", ip, port)
            return None

        # Send XET FOLDER_METADATA_REQUEST (piece 0)
        req_payload = xet_meta.encode_metadata_request(workspace_id, piece=0)
        ext_req = (
            struct.pack("!I", 2 + len(req_payload))
            + struct.pack("!BB", 20, ut_xet_id)
            + req_payload
        )
        writer.write(ext_req)
        await asyncio.wait_for(writer.drain(), timeout=5.0)

        # Read until we get FOLDER_METADATA_RESPONSE
        metadata_bytes = b""
        for _ in range(30):
            len_buf = await asyncio.wait_for(
                reader.readexactly(4), timeout=_READ_TIMEOUT
            )
            msg_len = struct.unpack("!I", len_buf)[0]
            if msg_len == 0:
                continue
            if msg_len > 10 * 1024 * 1024:
                break
            payload = await asyncio.wait_for(
                reader.readexactly(msg_len), timeout=_READ_TIMEOUT
            )
            if len(payload) < 2:
                continue
            if payload[0] != _EXTENDED_MSG_ID or payload[1] != ut_xet_id:
                continue
            body = payload[2:]
            if len(body) < 45:
                continue
            try:
                info_hash, piece_idx, total_pieces, piece_data = (
                    xet_meta.decode_metadata_response(body)
                )
            except ValueError:
                continue
            if info_hash != workspace_id:
                continue
            if total_pieces == 1 and piece_idx == 0:
                metadata_bytes = piece_data
                break
            if total_pieces > 1:
                metadata_bytes = piece_data
                break
            metadata_bytes = piece_data
            break
        else:
            logger.debug("Cold link fetch: no metadata response from %s:%s", ip, port)
            return None

        if not metadata_bytes:
            return None
        # Validate
        try:
            tonic_file = TonicFile()
            parsed_metadata = tonic_file.parse_bytes(metadata_bytes)
            if tonic_file.get_info_hash(parsed_metadata) != workspace_id:
                logger.debug(
                    "Cold link fetch: metadata workspace_id mismatch from %s:%s",
                    ip,
                    port,
                )
                return None
        except Exception:
            logger.debug("Cold link fetch: invalid metadata from %s:%s", ip, port)
            return None
        return metadata_bytes
    except (asyncio.TimeoutError, ConnectionError, OSError, ValueError) as e:
        logger.debug("Cold link fetch: %s:%s error: %s", ip, port, e)
        return None
    finally:
        try:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
        except Exception:
            pass


async def fetch_xet_metadata_from_peers(
    workspace_id: bytes,
    peers: list[Any],
    timeout: float = 30.0,
) -> Optional[bytes]:
    """Fetch .tonic metadata from a list of peers via XET extension.

    Connects to up to max_peers peers in parallel; returns the first
    successful metadata bytes, or None if none succeed.

    Args:
        workspace_id: 32-byte workspace (info) hash.
        peers: List of (ip, port) tuples or dicts with ip/port keys.
        timeout: Overall timeout in seconds.

    Returns:
        Assembled .tonic metadata bytes, or None.
    """
    if len(workspace_id) != 32:
        return None
    normalized = _normalize_peers(peers)
    if not normalized:
        logger.debug("Cold link fetch: no valid peers")
        return None
    logger.debug(
        "Cold link fetch: trying %d peers for workspace %s",
        len(normalized),
        workspace_id.hex()[:16],
    )
    to_try = normalized[:_MAX_PEERS_TO_TRY]
    task_objects = [
        asyncio.create_task(_connect_and_fetch_one(workspace_id, ip, port, timeout))
        for ip, port in to_try
    ]
    try:
        done, pending = await asyncio.wait(
            task_objects,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            try:
                result = task.result()
                if result is not None:
                    return result
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug("Cold link fetch task error: %s", e)
        for task in pending:
            task.cancel()
        return None
    finally:
        for t in task_objects:
            if not t.done():
                t.cancel()
            with suppress(asyncio.CancelledError, Exception):
                t.result()
