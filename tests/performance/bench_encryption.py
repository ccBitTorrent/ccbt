#!/usr/bin/env python3
"""Encryption performance benchmark.

Benchmarks:
- Cipher encryption/decryption throughput (RC4, AES-128, AES-256)
- DH keypair generation (768-bit, 1024-bit)
- Shared secret computation
- Key derivation performance
"""

from __future__ import annotations

import os
import sys

# Add project root to path for imports when run as script
# This must be done before any local imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, os.pardir, os.pardir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
import asyncio
import gc
import json
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

try:
    import psutil
except ImportError:
    psutil = None

from ccbt.peer.peer import Handshake
from ccbt.security.ciphers.aes import AESCipher
from ccbt.security.ciphers.rc4 import RC4Cipher
from ccbt.security.dh_exchange import DHPeerExchange
from ccbt.security.encrypted_stream import (
    EncryptedStreamReader,
    EncryptedStreamWriter,
)
from ccbt.security.mse_handshake import MSEHandshake

# Import bench_utils using relative import or direct import
try:
    from tests.performance.bench_utils import record_benchmark_results
except ImportError:
    # Fallback: import directly from same directory
    import importlib.util
    _bench_utils_path = os.path.join(os.path.dirname(__file__), "bench_utils.py")
    _spec = importlib.util.spec_from_file_location("bench_utils", _bench_utils_path)
    _bench_utils = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_bench_utils)  # type: ignore
    record_benchmark_results = _bench_utils.record_benchmark_results


@dataclass
class CipherResult:
    """Cipher benchmark result."""

    cipher: str
    operation: str
    data_size_bytes: int
    iterations: int
    elapsed_s: float
    throughput_bytes_per_s: float


@dataclass
class DHResult:
    """DH benchmark result."""

    operation: str
    key_size: int
    iterations: int
    elapsed_s: float
    avg_latency_ms: float


@dataclass
class HandshakeResult:
    """MSE handshake benchmark result."""

    role: str  # "initiator" or "receiver"
    dh_key_size: int
    iterations: int
    elapsed_s: float
    avg_latency_ms: float
    success_rate: float  # Percentage of successful handshakes


@dataclass
class StreamResult:
    """Stream wrapper benchmark result."""

    operation: str  # "read" or "write"
    stream_type: str  # "plain" or "encrypted"
    data_size_bytes: int
    buffer_size: int
    iterations: int
    elapsed_s: float
    throughput_bytes_per_s: float
    overhead_ms: float  # Additional latency vs plain stream


@dataclass
class ConnectionSetupResult:
    """Connection setup benchmark result."""

    connection_type: str  # "plain" or "encrypted"
    dh_key_size: int
    iterations: int
    elapsed_s: float
    avg_latency_ms: float
    overhead_ms: float  # Additional latency vs plain connection
    overhead_percent: float  # Percentage overhead


@dataclass
class DataTransferResult:
    """Data transfer throughput benchmark result."""

    transfer_type: str  # "plain" or "encrypted"
    piece_size_bytes: int
    iterations: int
    elapsed_s: float
    throughput_bytes_per_s: float
    overhead_percent: float  # Throughput reduction percentage


@dataclass
class MemoryResult:
    """Memory usage benchmark result."""

    operation: str  # "cipher" or "handshake"
    cipher_type: str  # "RC4", "AES-128", "AES-256", or "N/A"
    dh_key_size: int
    memory_bytes: int
    instances: int  # Number of instances measured
    avg_bytes_per_instance: int


def parse_size(size_str: str) -> int:
    """Parse size string to bytes."""
    suffixes = [
        ("gib", 1024**3),
        ("gb", 1024**3),
        ("mib", 1024**2),
        ("mb", 1024**2),
        ("kib", 1024),
        ("kb", 1024),
        ("b", 1),
    ]
    s = size_str.strip().lower()
    for suf, mul in suffixes:
        if s.endswith(suf):
            return int(float(s[:- len(suf)]) * mul)
    return int(s)


def format_bytes(n: float) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.2f} {unit}" if isinstance(n, float) else f"{n} {unit}"
        n = n / 1024
    return f"{n} B"


def run_cipher_benchmark(
    cipher_class: type,
    cipher_name: str,
    key_size: int,
    data_size: int,
    iterations: int,
    operation: str = "encrypt",
) -> CipherResult:
    """Run cipher benchmark."""
    key = b"x" * key_size
    data = b"x" * data_size

    # Initialize cipher (both AESCipher and RC4Cipher take key in __init__)
    cipher = cipher_class(key)

    # Warm up
    if operation == "encrypt":
        _ = cipher.encrypt(data[: min(data_size, 1024)])
    else:
        encrypted = cipher.encrypt(data[: min(data_size, 1024)])
        _ = cipher.decrypt(encrypted)

    # Benchmark
    start = time.perf_counter()
    total = 0
    for _ in range(iterations):
        if operation == "encrypt":
            result = cipher.encrypt(data)
        # For decryption, we need to encrypt first to get encrypted data
        elif cipher_class == RC4Cipher:
            # RC4 needs fresh instance for decryption
            encrypt_cipher = cipher_class(key)
            encrypted = encrypt_cipher.encrypt(data)
            decrypt_cipher = cipher_class(key)
            result = decrypt_cipher.decrypt(encrypted)
        else:
            encrypted = cipher.encrypt(data)
            result = cipher.decrypt(encrypted)
        total += len(result)
    elapsed = time.perf_counter() - start

    throughput = total / max(elapsed, 1e-9)
    return CipherResult(
        cipher=cipher_name,
        operation=operation,
        data_size_bytes=data_size,
        iterations=iterations,
        elapsed_s=elapsed,
        throughput_bytes_per_s=throughput,
    )


def run_dh_keypair_benchmark(key_size: int, iterations: int) -> DHResult:
    """Run DH keypair generation benchmark."""
    dh = DHPeerExchange(key_size=key_size)

    start = time.perf_counter()
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = dh.generate_keypair()
        latencies.append((time.perf_counter() - t0) * 1000)  # Convert to ms
    elapsed = time.perf_counter() - start

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    return DHResult(
        operation="keypair_generation",
        key_size=key_size,
        iterations=iterations,
        elapsed_s=elapsed,
        avg_latency_ms=avg_latency,
    )


def run_dh_shared_secret_benchmark(key_size: int, iterations: int) -> DHResult:
    """Run DH shared secret computation benchmark."""
    dh = DHPeerExchange(key_size=key_size)

    # Generate keypairs once
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()

    start = time.perf_counter()
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = dh.compute_shared_secret(keypair1.private_key, keypair2.public_key)
        latencies.append((time.perf_counter() - t0) * 1000)  # Convert to ms
    elapsed = time.perf_counter() - start

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    return DHResult(
        operation="shared_secret",
        key_size=key_size,
        iterations=iterations,
        elapsed_s=elapsed,
        avg_latency_ms=avg_latency,
    )


def run_key_derivation_benchmark(iterations: int) -> DHResult:
    """Run key derivation benchmark."""
    dh = DHPeerExchange(key_size=768)

    # Generate shared secret
    keypair1 = dh.generate_keypair()
    keypair2 = dh.generate_keypair()
    shared_secret = dh.compute_shared_secret(
        keypair1.private_key, keypair2.public_key
    )
    info_hash = b"x" * 20

    start = time.perf_counter()
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = dh.derive_encryption_key(shared_secret, info_hash)
        latencies.append((time.perf_counter() - t0) * 1000)  # Convert to ms
    elapsed = time.perf_counter() - start

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    return DHResult(
        operation="key_derivation",
        key_size=0,  # Not applicable
        iterations=iterations,
        elapsed_s=elapsed,
        avg_latency_ms=avg_latency,
    )


async def run_handshake_initiator_benchmark(
    dh_key_size: int, iterations: int
) -> HandshakeResult:
    """Run MSE handshake initiator benchmark."""
    info_hash = b"x" * 20
    latencies = []
    successes = 0

    for _ in range(iterations):
        # Create queues for bidirectional communication
        initiator_to_receiver = asyncio.Queue()
        receiver_to_initiator = asyncio.Queue()

        # Create handshake instances
        initiator = MSEHandshake(dh_key_size=dh_key_size, prefer_rc4=True)
        receiver = MSEHandshake(dh_key_size=dh_key_size, prefer_rc4=True)

        # Setup initiator writer
        def initiator_write(data):
            initiator_to_receiver.put_nowait(data)

        initiator_writer = MagicMock()
        initiator_writer.write = MagicMock(side_effect=initiator_write)
        initiator_writer.drain = AsyncMock()

        # Setup receiver writer
        def receiver_write(data):
            receiver_to_initiator.put_nowait(data)

        receiver_writer = MagicMock()
        receiver_writer.write = MagicMock(side_effect=receiver_write)
        receiver_writer.drain = AsyncMock()

        # Setup initiator reader
        async def initiator_readexactly(n):
            data = b""
            while len(data) < n:
                chunk = await receiver_to_initiator.get()
                data += chunk
            result = data[:n]
            if len(data) > n:
                await receiver_to_initiator.put(data[n:])
            return result

        initiator_reader = AsyncMock()
        initiator_reader.readexactly = initiator_readexactly
        initiator_reader.read = initiator_readexactly

        # Setup receiver reader
        async def receiver_readexactly(n):
            data = b""
            while len(data) < n:
                chunk = await initiator_to_receiver.get()
                data += chunk
            result = data[:n]
            if len(data) > n:
                await initiator_to_receiver.put(data[n:])
            return result

        receiver_reader = AsyncMock()
        receiver_reader.readexactly = receiver_readexactly
        receiver_reader.read = receiver_readexactly

        # Run handshake
        t0 = time.perf_counter()
        initiator_task = asyncio.create_task(
            initiator.initiate_as_initiator(
                initiator_reader, initiator_writer, info_hash
            )
        )
        receiver_task = asyncio.create_task(
            receiver.respond_as_receiver(
                receiver_reader, receiver_writer, info_hash
            )
        )

        initiator_result, receiver_result = await asyncio.gather(
            initiator_task, receiver_task
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        if initiator_result.success and receiver_result.success:
            successes += 1

    elapsed = sum(latencies) / 1000.0 if latencies else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    success_rate = (successes / iterations * 100.0) if iterations > 0 else 0.0

    return HandshakeResult(
        role="initiator",
        dh_key_size=dh_key_size,
        iterations=iterations,
        elapsed_s=elapsed,
        avg_latency_ms=avg_latency,
        success_rate=success_rate,
    )


async def run_stream_read_benchmark(
    stream_type: str, data_size: int, buffer_size: int, iterations: int
) -> StreamResult:
    """Run stream read benchmark (plain vs encrypted)."""
    data = b"x" * data_size

    async def plain_read(reader: AsyncMock, size: int) -> bytes:
        result = b""
        remaining = size
        while remaining > 0:
            chunk = await reader.read(min(buffer_size, remaining))
            if not chunk:
                break
            result += chunk
            remaining -= len(chunk)
        return result

    async def encrypted_read(
        reader: AsyncMock, cipher: RC4Cipher, size: int
    ) -> bytes:
        encrypted_reader = EncryptedStreamReader(reader, cipher)
        result = b""
        remaining = size
        while remaining > 0:
            chunk = await encrypted_reader.read(min(buffer_size, remaining))
            if not chunk:
                break
            result += chunk
            remaining -= len(chunk)
        return result

    plain_times = []
    encrypted_times = []

    for _ in range(iterations):
        # Plain stream benchmark
        plain_reader = AsyncMock()
        chunks = [
            data[i : i + buffer_size]
            for i in range(0, len(data), buffer_size)
        ]
        plain_reader.read = AsyncMock(side_effect=[*chunks, b""])

        t0 = time.perf_counter()
        await plain_read(plain_reader, data_size)
        plain_times.append((time.perf_counter() - t0) * 1000)

        # Encrypted stream benchmark
        cipher = RC4Cipher(b"x" * 16)
        encrypted_data = cipher.encrypt(data)
        encrypted_reader = AsyncMock()
        encrypted_chunks = [
            encrypted_data[i : i + buffer_size]
            for i in range(0, len(encrypted_data), buffer_size)
        ]
        encrypted_reader.read = AsyncMock(side_effect=[*encrypted_chunks, b""])

        t0 = time.perf_counter()
        await encrypted_read(encrypted_reader, cipher, data_size)
        encrypted_times.append((time.perf_counter() - t0) * 1000)

    if stream_type == "plain":
        avg_time = sum(plain_times) / len(plain_times) if plain_times else 0.0
        overhead = 0.0
        elapsed = sum(plain_times) / 1000.0
    else:
        avg_time = (
            sum(encrypted_times) / len(encrypted_times) if encrypted_times else 0.0
        )
        plain_avg = sum(plain_times) / len(plain_times) if plain_times else 0.0
        overhead = avg_time - plain_avg
        elapsed = sum(encrypted_times) / 1000.0

    throughput = (data_size * iterations) / max(elapsed, 1e-9)

    return StreamResult(
        operation="read",
        stream_type=stream_type,
        data_size_bytes=data_size,
        buffer_size=buffer_size,
        iterations=iterations,
        elapsed_s=elapsed,
        throughput_bytes_per_s=throughput,
        overhead_ms=overhead,
    )


async def run_stream_write_benchmark(
    stream_type: str, data_size: int, buffer_size: int, iterations: int
) -> StreamResult:
    """Run stream write benchmark (plain vs encrypted)."""
    data = b"x" * data_size

    async def plain_write(writer: MagicMock, data_to_write: bytes) -> None:
        for i in range(0, len(data_to_write), buffer_size):
            chunk = data_to_write[i : i + buffer_size]
            writer.write(chunk)
            await writer.drain()

    async def encrypted_write(
        writer: MagicMock, cipher: RC4Cipher, data_to_write: bytes
    ) -> None:
        encrypted_writer = EncryptedStreamWriter(writer, cipher)
        for i in range(0, len(data_to_write), buffer_size):
            chunk = data_to_write[i : i + buffer_size]
            encrypted_writer.write(chunk)
            await encrypted_writer.drain()

    plain_times = []
    encrypted_times = []

    for _ in range(iterations):
        # Plain stream benchmark
        plain_writer = MagicMock()
        plain_writer.write = MagicMock()
        plain_writer.drain = AsyncMock()

        t0 = time.perf_counter()
        await plain_write(plain_writer, data)
        plain_times.append((time.perf_counter() - t0) * 1000)

        # Encrypted stream benchmark
        cipher = RC4Cipher(b"x" * 16)
        encrypted_writer_mock = MagicMock()
        encrypted_writer_mock.write = MagicMock()
        encrypted_writer_mock.drain = AsyncMock()

        t0 = time.perf_counter()
        await encrypted_write(encrypted_writer_mock, cipher, data)
        encrypted_times.append((time.perf_counter() - t0) * 1000)

    if stream_type == "plain":
        elapsed = sum(plain_times) / 1000.0
        overhead = 0.0
    else:
        elapsed = sum(encrypted_times) / 1000.0
        plain_avg = sum(plain_times) / len(plain_times) if plain_times else 0.0
        encrypted_avg = (
            sum(encrypted_times) / len(encrypted_times) if encrypted_times else 0.0
        )
        overhead = encrypted_avg - plain_avg

    throughput = (data_size * iterations) / max(elapsed, 1e-9)

    return StreamResult(
        operation="write",
        stream_type=stream_type,
        data_size_bytes=data_size,
        buffer_size=buffer_size,
        iterations=iterations,
        elapsed_s=elapsed,
        throughput_bytes_per_s=throughput,
        overhead_ms=overhead,
    )


async def run_plain_connection_setup_benchmark(
    iterations: int,
) -> ConnectionSetupResult:
    """Run plain connection setup benchmark (TCP + BitTorrent handshake)."""
    info_hash = b"x" * 20
    peer_id = b"-CC0101-" + b"x" * 12

    async def handle_plain_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle plain client connection."""
        # Read BitTorrent handshake (68 bytes)
        await reader.readexactly(68)
        # Send BitTorrent handshake
        handshake = Handshake(info_hash, peer_id)
        writer.write(handshake.encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    latencies = []
    successes = 0

    # Start server on random port
    server = await asyncio.start_server(
        handle_plain_client, "127.0.0.1", 0
    )
    server_addr = server.sockets[0].getsockname()
    port = server_addr[1]

    async with server:
        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                # TCP connect
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", port
                )
                # Send BitTorrent handshake
                handshake = Handshake(info_hash, peer_id)
                writer.write(handshake.encode())
                await writer.drain()

                # Receive handshake
                await reader.readexactly(68)

                elapsed_ms = (time.perf_counter() - t0) * 1000
                latencies.append(elapsed_ms)
                successes += 1

                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: S110 - Benchmark failures are acceptable
                pass  # Count as failure

    elapsed = sum(latencies) / 1000.0 if latencies else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return ConnectionSetupResult(
        connection_type="plain",
        dh_key_size=0,
        iterations=iterations,
        elapsed_s=elapsed,
        avg_latency_ms=avg_latency,
        overhead_ms=0.0,
        overhead_percent=0.0,
    )


async def run_encrypted_connection_setup_benchmark(
    dh_key_size: int, iterations: int
) -> ConnectionSetupResult:
    """Run encrypted connection setup benchmark (TCP + MSE + BitTorrent handshake)."""
    info_hash = b"x" * 20
    peer_id = b"-CC0101-" + b"x" * 12

    async def handle_encrypted_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle encrypted client connection."""
        # Perform MSE handshake as receiver
        mse = MSEHandshake(dh_key_size=dh_key_size, prefer_rc4=True)
        result = await mse.respond_as_receiver(reader, writer, info_hash)

        if result.success and result.cipher:
            # Wrap streams
            encrypted_reader = EncryptedStreamReader(reader, result.cipher)
            encrypted_writer = EncryptedStreamWriter(writer, result.cipher)

            # Read BitTorrent handshake through encrypted stream
            await encrypted_reader.readexactly(68)

            # Send BitTorrent handshake through encrypted stream
            handshake = Handshake(info_hash, peer_id)
            encrypted_writer.write(handshake.encode())
            await encrypted_writer.drain()

        writer.close()
        await writer.wait_closed()

    latencies = []
    successes = 0

    # Start server on random port
    server = await asyncio.start_server(
        handle_encrypted_client, "127.0.0.1", 0
    )
    server_addr = server.sockets[0].getsockname()
    port = server_addr[1]

    async with server:
        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                # TCP connect
                reader, writer = await asyncio.open_connection(
                    "127.0.0.1", port
                )

                # Perform MSE handshake as initiator
                mse = MSEHandshake(dh_key_size=dh_key_size, prefer_rc4=True)
                result = await mse.initiate_as_initiator(
                    reader, writer, info_hash
                )

                if result.success and result.cipher:
                    # Wrap streams
                    encrypted_reader = EncryptedStreamReader(
                        reader, result.cipher
                    )
                    encrypted_writer = EncryptedStreamWriter(
                        writer, result.cipher
                    )

                    # Send BitTorrent handshake through encrypted stream
                    handshake = Handshake(info_hash, peer_id)
                    encrypted_writer.write(handshake.encode())
                    await encrypted_writer.drain()

                    # Receive handshake through encrypted stream
                    await encrypted_reader.readexactly(68)

                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    latencies.append(elapsed_ms)
                    successes += 1

                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: S110 - Benchmark failures are acceptable
                pass  # Count as failure

    elapsed = sum(latencies) / 1000.0 if latencies else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return ConnectionSetupResult(
        connection_type="encrypted",
        dh_key_size=dh_key_size,
        iterations=iterations,
        elapsed_s=elapsed,
        avg_latency_ms=avg_latency,
        overhead_ms=0.0,  # Will be calculated later
        overhead_percent=0.0,  # Will be calculated later
    )


async def run_data_transfer_benchmark(
    transfer_type: str, piece_size: int, iterations: int
) -> DataTransferResult:
    """Run data transfer benchmark (simulated piece transfer)."""
    data = b"x" * piece_size

    async def transfer_plain(
        reader: AsyncMock, writer: AsyncMock, data_to_send: bytes
    ) -> None:
        """Transfer data through plain stream."""
        # Write data
        writer.write(data_to_send)
        await writer.drain()
        # Read data
        await reader.read(len(data_to_send))

    async def transfer_encrypted(
        reader: AsyncMock,
        writer: MagicMock,
        cipher: RC4Cipher,
        data_to_send: bytes,
    ) -> None:
        """Transfer data through encrypted stream."""
        encrypted_writer = EncryptedStreamWriter(writer, cipher)
        encrypted_reader = EncryptedStreamReader(reader, cipher)

        # Write data through encrypted stream
        encrypted_writer.write(data_to_send)
        await encrypted_writer.drain()

        # Read data through encrypted stream
        await encrypted_reader.read(len(data_to_send))

    plain_times = []
    encrypted_times = []

    for _ in range(iterations):
        # Plain transfer
        plain_reader = AsyncMock()
        plain_reader.read = AsyncMock(return_value=data)
        plain_writer = MagicMock()
        plain_writer.write = MagicMock()
        plain_writer.drain = AsyncMock()

        t0 = time.perf_counter()
        await transfer_plain(plain_reader, plain_writer, data)
        plain_times.append((time.perf_counter() - t0) * 1000)

        # Encrypted transfer
        cipher = RC4Cipher(b"x" * 16)
        encrypted_data = cipher.encrypt(data)
        encrypted_reader = AsyncMock()
        encrypted_reader.read = AsyncMock(return_value=encrypted_data)
        encrypted_writer_mock = MagicMock()
        encrypted_writer_mock.write = MagicMock()
        encrypted_writer_mock.drain = AsyncMock()

        t0 = time.perf_counter()
        await transfer_encrypted(
            encrypted_reader, encrypted_writer_mock, cipher, data
        )
        encrypted_times.append((time.perf_counter() - t0) * 1000)

    if transfer_type == "plain":
        elapsed = sum(plain_times) / 1000.0
        throughput = (piece_size * iterations) / max(elapsed, 1e-9)
        overhead_pct = 0.0
    else:
        elapsed = sum(encrypted_times) / 1000.0
        throughput = (piece_size * iterations) / max(elapsed, 1e-9)
        plain_elapsed = sum(plain_times) / 1000.0
        plain_throughput = (piece_size * iterations) / max(plain_elapsed, 1e-9)
        overhead_pct = (
            ((plain_throughput - throughput) / plain_throughput * 100.0)
            if plain_throughput > 0
            else 0.0
        )

    return DataTransferResult(
        transfer_type=transfer_type,
        piece_size_bytes=piece_size,
        iterations=iterations,
        elapsed_s=elapsed,
        throughput_bytes_per_s=throughput,
        overhead_percent=overhead_pct,
    )


def print_data_transfer_table(
    results: list[DataTransferResult],
) -> None:
    """Print data transfer benchmark results table."""
    print(
        "Type | Piece Size | Iterations | Throughput | Overhead %"
    )
    print("-" * 75)
    for r in results:
        tput_str = f"{r.throughput_bytes_per_s / (1024**2):.2f} MiB/s"
        overhead_str = f"{r.overhead_percent:.1f}%"
        print(
            " | ".join(
                [
                    r.transfer_type,
                    format_bytes(r.piece_size_bytes),
                    str(r.iterations),
                    tput_str,
                    overhead_str,
                ]
            )
        )


def get_memory_usage() -> int:
    """Get current process memory usage in bytes."""
    if psutil is None:
        return 0
    process = psutil.Process()
    return process.memory_info().rss


def run_cipher_memory_benchmark(
    cipher_class: type, cipher_name: str, key_size: int, instances: int
) -> MemoryResult:
    """Measure memory footprint of cipher instances."""
    if psutil is None:
        return MemoryResult(
            operation="cipher",
            cipher_type=cipher_name,
            dh_key_size=0,
            memory_bytes=0,
            instances=instances,
            avg_bytes_per_instance=0,
        )

    # Force garbage collection
    gc.collect()
    baseline = get_memory_usage()

    # Create cipher instances
    ciphers = []
    key = b"x" * key_size
    for _ in range(instances):
        cipher = cipher_class(key)
        ciphers.append(cipher)

    # Measure memory after creation
    after_creation = get_memory_usage()
    memory_used = max(0, after_creation - baseline)
    avg_bytes = memory_used // max(instances, 1)

    # Clean up
    del ciphers
    gc.collect()

    return MemoryResult(
        operation="cipher",
        cipher_type=cipher_name,
        dh_key_size=0,
        memory_bytes=memory_used,
        instances=instances,
        avg_bytes_per_instance=avg_bytes,
    )


async def run_handshake_memory_benchmark(
    dh_key_size: int, instances: int
) -> MemoryResult:
    """Measure memory usage during MSE handshake operations."""
    if psutil is None:
        return MemoryResult(
            operation="handshake",
            cipher_type="N/A",
            dh_key_size=dh_key_size,
            memory_bytes=0,
            instances=instances,
            avg_bytes_per_instance=0,
        )

    gc.collect()
    baseline = get_memory_usage()

    # Create handshake instances and perform operations
    handshakes = []
    for _ in range(instances):
        mse = MSEHandshake(dh_key_size=dh_key_size, prefer_rc4=True)
        # Generate keypair (main memory usage)
        dh = DHPeerExchange(key_size=dh_key_size)
        keypair = dh.generate_keypair()
        handshakes.append((mse, dh, keypair))

    # Measure memory after creation
    after_creation = get_memory_usage()
    memory_used = max(0, after_creation - baseline)
    avg_bytes = memory_used // max(instances, 1)

    # Clean up
    del handshakes
    gc.collect()

    return MemoryResult(
        operation="handshake",
        cipher_type="RC4",  # Default cipher used
        dh_key_size=dh_key_size,
        memory_bytes=memory_used,
        instances=instances,
        avg_bytes_per_instance=avg_bytes,
    )


def print_memory_table(results: list[MemoryResult]) -> None:
    """Print memory benchmark results table."""
    print(
        "Operation | Cipher | DH Size | Instances | Total Memory | Avg Per Instance"
    )
    print("-" * 90)
    for r in results:
        total_str = format_bytes(r.memory_bytes)
        avg_str = format_bytes(r.avg_bytes_per_instance)
        dh_str = f"{r.dh_key_size}-bit" if r.dh_key_size > 0 else "N/A"
        print(
            " | ".join(
                [
                    r.operation,
                    r.cipher_type,
                    dh_str,
                    str(r.instances),
                    total_str,
                    avg_str,
                ]
            )
        )


def print_connection_setup_table(
    results: list[ConnectionSetupResult], plain_baseline: float = 0.0  # noqa: ARG001
) -> None:
    """Print connection setup benchmark results table."""
    print(
        "Type | DH Size | Iterations | Avg Latency (ms) | Overhead (ms) | Overhead %"
    )
    print("-" * 85)
    for r in results:
        dh_size_str = f"{r.dh_key_size}-bit" if r.dh_key_size > 0 else "N/A"
        overhead_ms = r.overhead_ms
        overhead_pct = r.overhead_percent
        print(
            " | ".join(
                [
                    r.connection_type,
                    dh_size_str,
                    str(r.iterations),
                    f"{r.avg_latency_ms:.2f}",
                    f"{overhead_ms:.2f}",
                    f"{overhead_pct:.1f}%",
                ]
            )
        )


def print_handshake_table(results: list[HandshakeResult]) -> None:
    """Print handshake benchmark results table."""
    print(
        "Role | DH Size | Iterations | Elapsed (s) | Avg Latency (ms) | Success Rate"
    )
    print("-" * 85)
    for r in results:
        print(
            " | ".join(
                [
                    r.role,
                    f"{r.dh_key_size}-bit",
                    str(r.iterations),
                    f"{r.elapsed_s:.3f}",
                    f"{r.avg_latency_ms:.2f}",
                    f"{r.success_rate:.1f}%",
                ]
            )
        )


def print_cipher_table(results: list[CipherResult]) -> None:
    """Print cipher benchmark results table."""
    print("Cipher | Operation | Size | Iterations | Elapsed (s) | Throughput")
    print("-" * 80)
    for r in results:
        size_str = format_bytes(r.data_size_bytes)
        tput_str = f"{r.throughput_bytes_per_s / (1024**2):.2f} MiB/s"
        print(
            " | ".join(
                [
                    r.cipher,
                    r.operation,
                    size_str,
                    str(r.iterations),
                    f"{r.elapsed_s:.3f}",
                    tput_str,
                ]
            )
        )


def print_dh_table(results: list[DHResult]) -> None:
    """Print DH benchmark results table."""
    print("Operation | Key Size | Iterations | Elapsed (s) | Avg Latency (ms)")
    print("-" * 75)
    for r in results:
        key_size_str = f"{r.key_size}-bit" if r.key_size > 0 else "N/A"
        print(
            " | ".join(
                [
                    r.operation,
                    key_size_str,
                    str(r.iterations),
                    f"{r.elapsed_s:.3f}",
                    f"{r.avg_latency_ms:.2f}",
                ]
            )
        )


def print_stream_table(results: list[StreamResult]) -> None:
    """Print stream wrapper benchmark results table."""
    print(
        "Operation | Type | Size | Buffer | Iterations | Throughput | Overhead (ms)"
    )
    print("-" * 90)
    for r in results:
        tput_str = f"{r.throughput_bytes_per_s / (1024**2):.2f} MiB/s"
        overhead_str = f"{r.overhead_ms:.2f}" if r.overhead_ms > 0 else "0.00"
        print(
            " | ".join(
                [
                    r.operation,
                    r.stream_type,
                    format_bytes(r.data_size_bytes),
                    format_bytes(r.buffer_size),
                    str(r.iterations),
                    tput_str,
                    overhead_str,
                ]
            )
        )


def ensure_artifacts_dir(output_dir: Path) -> None:
    """Ensure output directory exists."""
    output_dir.mkdir(parents=True, exist_ok=True)


def write_json(
    output_dir: Path,
    benchmark: str,
    config_name: str,
    cipher_results: list[CipherResult],
    dh_results: list[DHResult],
    handshake_results: list[HandshakeResult],
    stream_results: list[StreamResult],
    connection_results: list[ConnectionSetupResult],
    transfer_results: list[DataTransferResult],
    memory_results: list[MemoryResult],
) -> Path:
    """Write benchmark results to JSON."""
    meta = {
        "benchmark": benchmark,
        "config": config_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
    }
    data = {
        "meta": meta,
        "cipher_results": [asdict(r) for r in cipher_results],
        "dh_results": [asdict(r) for r in dh_results],
        "handshake_results": [asdict(r) for r in handshake_results],
        "stream_results": [asdict(r) for r in stream_results],
        "connection_results": [asdict(r) for r in connection_results],
        "transfer_results": [asdict(r) for r in transfer_results],
        "memory_results": [asdict(r) for r in memory_results],
    }
    filename = (
        f"{benchmark}-{config_name}-{platform.system()}-{platform.release()}.json"
    )
    path = output_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def derive_config_name(config_file: str | None) -> str:
    """Derive config name from config file path."""
    if not config_file:
        return "default"
    stem = Path(config_file).stem
    parts = stem.split("example-config-")
    if len(parts) == 2 and parts[1]:
        return parts[1]
    return stem


def main() -> int:
    """Main benchmark entry point."""
    parser = argparse.ArgumentParser(description="Encryption performance benchmark")
    parser.add_argument(
        "--sizes",
        nargs="*",
        default=["1KiB", "64KiB", "1MiB"],
        help="Data sizes for cipher benchmarks",
    )
    parser.add_argument(
        "--buffer-sizes",
        nargs="*",
        default=["1KiB", "16KiB", "64KiB"],
        help="Buffer sizes for stream benchmarks",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Iterations per benchmark",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run minimal quick mode",
    )
    parser.add_argument(
        "--config-file",
        default=None,
        help="Path to client config used (for labeling only)",
    )
    parser.add_argument(
        "--output-dir",
        default="site/reports/benchmarks/artifacts",
        help="Output directory for artifacts (deprecated)",
    )
    parser.add_argument(
        "--record-mode",
        choices=["auto", "pre-commit", "commit", "both", "none"],
        default="auto",
        help="Recording mode: auto (detect), pre-commit, commit, both, or none",
    )

    args = parser.parse_args()

    sizes = [parse_size(s) for s in args.sizes]
    iterations = 10 if args.quick else args.iterations

    if args.quick:
        sizes = sizes[:1]  # Only smallest size in quick mode

    cipher_results: list[CipherResult] = []
    dh_results: list[DHResult] = []
    handshake_results: list[HandshakeResult] = []
    stream_results: list[StreamResult] = []
    connection_results: list[ConnectionSetupResult] = []
    transfer_results: list[DataTransferResult] = []
    memory_results: list[MemoryResult] = []

    print("Running cipher benchmarks...")
    for size in sizes:
        # RC4
        cipher_results.append(
            run_cipher_benchmark(RC4Cipher, "RC4", 16, size, iterations, "encrypt")
        )
        cipher_results.append(
            run_cipher_benchmark(RC4Cipher, "RC4", 16, size, iterations, "decrypt")
        )

        # AES-128
        cipher_results.append(
            run_cipher_benchmark(AESCipher, "AES-128", 16, size, iterations, "encrypt")
        )
        cipher_results.append(
            run_cipher_benchmark(AESCipher, "AES-128", 16, size, iterations, "decrypt")
        )

        # AES-256
        cipher_results.append(
            run_cipher_benchmark(AESCipher, "AES-256", 32, size, iterations, "encrypt")
        )
        cipher_results.append(
            run_cipher_benchmark(AESCipher, "AES-256", 32, size, iterations, "decrypt")
        )

    print("\nRunning DH benchmarks...")
    # DH keypair generation
    dh_results.append(run_dh_keypair_benchmark(768, iterations))
    dh_results.append(run_dh_keypair_benchmark(1024, iterations))

    # DH shared secret computation
    dh_results.append(run_dh_shared_secret_benchmark(768, iterations))
    dh_results.append(run_dh_shared_secret_benchmark(1024, iterations))

    # Key derivation
    dh_results.append(run_key_derivation_benchmark(iterations))

    print("\nRunning MSE handshake benchmarks...")
    # MSE handshake latency (initiator side with 768-bit and 1024-bit DH)
    # Use fewer iterations for handshake as it's more expensive
    handshake_iterations = (
        max(5, iterations // 10) if args.quick else max(10, iterations // 5)
    )
    handshake_results.append(
        asyncio.run(run_handshake_initiator_benchmark(768, handshake_iterations))
    )
    handshake_results.append(
        asyncio.run(run_handshake_initiator_benchmark(1024, handshake_iterations))
    )

    print("\nRunning stream wrapper benchmarks...")
    # Stream wrapper overhead benchmarks
    # Use fewer sizes in quick mode
    if args.quick:
        stream_sizes = [parse_size(s) for s in args.sizes[:1]]
    else:
        stream_sizes = [parse_size(s) for s in args.sizes[:2]]
    buffer_sizes = [parse_size(b) for b in args.buffer_sizes]
    if args.quick:
        buffer_sizes = buffer_sizes[:1]  # Only one buffer size in quick mode

    for data_size in stream_sizes:
        for buffer_size in buffer_sizes:
            # Read benchmarks
            stream_results.append(
                asyncio.run(
                    run_stream_read_benchmark(
                        "plain", data_size, buffer_size, iterations
                    )
                )
            )
            stream_results.append(
                asyncio.run(
                    run_stream_read_benchmark(
                        "encrypted", data_size, buffer_size, iterations
                    )
                )
            )

            # Write benchmarks
            stream_results.append(
                asyncio.run(
                    run_stream_write_benchmark(
                        "plain", data_size, buffer_size, iterations
                    )
                )
            )
            stream_results.append(
                asyncio.run(
                    run_stream_write_benchmark(
                        "encrypted", data_size, buffer_size, iterations
                    )
                )
            )

    # Print results
    print("\n=== Cipher Benchmarks ===")
    print_cipher_table(cipher_results)
    print("\n=== DH Benchmarks ===")
    print_dh_table(dh_results)
    print("\n=== MSE Handshake Benchmarks ===")
    print_handshake_table(handshake_results)
    print("\n=== Stream Wrapper Benchmarks ===")
    print_stream_table(stream_results)

    print("\nRunning connection setup benchmarks...")
    # Connection setup benchmarks (fewer iterations due to TCP overhead)
    if args.quick:
        connection_iterations = max(5, iterations // 20)
    else:
        connection_iterations = max(10, iterations // 10)

    # Plain connection baseline
    plain_result = asyncio.run(
        run_plain_connection_setup_benchmark(connection_iterations)
    )
    connection_results.append(plain_result)
    plain_baseline = plain_result.avg_latency_ms

    # Encrypted connections (768-bit and 1024-bit)
    encrypted_768 = asyncio.run(
        run_encrypted_connection_setup_benchmark(768, connection_iterations)
    )
    encrypted_768.overhead_ms = encrypted_768.avg_latency_ms - plain_baseline
    encrypted_768.overhead_percent = (
        (encrypted_768.overhead_ms / plain_baseline * 100.0)
        if plain_baseline > 0
        else 0.0
    )
    connection_results.append(encrypted_768)

    encrypted_1024 = asyncio.run(
        run_encrypted_connection_setup_benchmark(1024, connection_iterations)
    )
    encrypted_1024.overhead_ms = encrypted_1024.avg_latency_ms - plain_baseline
    encrypted_1024.overhead_percent = (
        (encrypted_1024.overhead_ms / plain_baseline * 100.0)
        if plain_baseline > 0
        else 0.0
    )
    connection_results.append(encrypted_1024)

    print("\n=== Connection Setup Benchmarks ===")
    print_connection_setup_table(connection_results, plain_baseline)

    print("\nRunning data transfer benchmarks...")
    # Data transfer benchmarks (piece transfer simulation)
    if args.quick:
        piece_sizes = [256 * 1024]
        transfer_iterations = max(5, iterations // 10)
    else:
        piece_sizes = [256 * 1024, 512 * 1024, 1024 * 1024]
        transfer_iterations = max(10, iterations // 5)

    for piece_size in piece_sizes:
        # Plain transfer baseline
        plain_transfer = asyncio.run(
            run_data_transfer_benchmark("plain", piece_size, transfer_iterations)
        )
        transfer_results.append(plain_transfer)

        # Encrypted transfer
        encrypted_transfer = asyncio.run(
            run_data_transfer_benchmark("encrypted", piece_size, transfer_iterations)
        )
        # Calculate overhead based on plain baseline
        if plain_transfer.throughput_bytes_per_s > 0:
            plain_tput = plain_transfer.throughput_bytes_per_s
            encrypted_tput = encrypted_transfer.throughput_bytes_per_s
            encrypted_transfer.overhead_percent = (
                (plain_tput - encrypted_tput) / plain_tput * 100.0
            )
        transfer_results.append(encrypted_transfer)

    print("\n=== Data Transfer Benchmarks ===")
    print_data_transfer_table(transfer_results)

    if psutil is not None:
        print("\nRunning memory usage benchmarks...")
        # Memory footprint benchmarks
        memory_instances = 100  # Measure 100 instances to get accurate averages

        # Cipher memory footprints
        memory_results.append(
            run_cipher_memory_benchmark(RC4Cipher, "RC4", 16, memory_instances)
        )
        memory_results.append(
            run_cipher_memory_benchmark(AESCipher, "AES-128", 16, memory_instances)
        )
        memory_results.append(
            run_cipher_memory_benchmark(AESCipher, "AES-256", 32, memory_instances)
        )

        # Handshake memory (DH + cipher)
        memory_results.append(
            asyncio.run(
                run_handshake_memory_benchmark(768, memory_instances // 10)
            )
        )
        memory_results.append(
            asyncio.run(
                run_handshake_memory_benchmark(1024, memory_instances // 10)
            )
        )

        print("\n=== Memory Usage Benchmarks ===")
        print_memory_table(memory_results)
    else:
        print("\nSkipping memory benchmarks (psutil not available)")

    # Write JSON output
    output_dir = Path(args.output_dir)
    ensure_artifacts_dir(output_dir)
    config_name = derive_config_name(args.config_file)
    
    # Aggregate all results for recording
    all_results = (
        cipher_results
        + dh_results
        + handshake_results
        + stream_results
        + connection_results
        + transfer_results
        + memory_results
    )
    
    # Record benchmark results using new system
    per_run_path, timeseries_path = record_benchmark_results(
        "encryption", config_name, all_results, args.record_mode
    )
    
    # Backward compatibility
    out_path = write_json(
        output_dir,
        "encryption",
        config_name,
        cipher_results,
        dh_results,
        handshake_results,
        stream_results,
        connection_results,
        transfer_results,
        memory_results,
    )
    print(f"\nWrote (legacy): {out_path}")
    
    # Print recording results
    if per_run_path:
        print(f"Recorded per-run: {per_run_path}")
    if timeseries_path:
        print(f"Updated timeseries: {timeseries_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

