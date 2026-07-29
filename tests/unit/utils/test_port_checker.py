"""Tests for port_checker utilities."""

from __future__ import annotations

import socket
import threading

from ccbt.utils.port_checker import is_port_listening


def test_is_port_listening_detects_bound_tcp_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    try:
        port = sock.getsockname()[1]
        assert is_port_listening("127.0.0.1", port) is True
        assert is_port_listening("127.0.0.1", port + 1) is False
    finally:
        sock.close()


def test_is_port_listening_accepts_connections() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    accepted: list[socket.socket] = []

    def accept_once() -> None:
        conn, _addr = sock.accept()
        accepted.append(conn)

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()
    try:
        assert is_port_listening("127.0.0.1", port) is True
    finally:
        sock.close()
        for conn in accepted:
            conn.close()
        thread.join(timeout=1.0)
