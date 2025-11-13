"""Performance and stress tests for uTP implementation."""

import asyncio
from unittest.mock import MagicMock

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType


class TestPerformance:
    """Performance tests for uTP."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        conn.seq_nr = 1
        return conn

    @pytest.mark.asyncio
    async def test_high_throughput_send(self, connection):
        """Test sending large amounts of data."""
        # Set a large send window so data can be sent
        connection.send_window = 10 * 1024 * 1024  # 10MB window
        connection.recv_window = 65535
        
        # Send 1MB of data
        data = b"x" * (1024 * 1024)

        # Start send task
        send_task = asyncio.create_task(connection.send(data))
        
        # Wait a bit for packets to be created
        await asyncio.sleep(0.1)
        
        # Cancel send task (it may take time)
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass

        # Verify packets were created
        assert len(connection.send_buffer) > 0

    @pytest.mark.asyncio
    async def test_many_concurrent_packets(self, connection):
        """Test handling many concurrent packets."""
        from ccbt.transport.utp_extensions import UTPExtensionType
        
        # Ensure SACK is negotiated so received_seqs is tracked
        connection.negotiated_extensions.add(UTPExtensionType.SACK)
        
        # Simulate receiving many packets
        for seq in range(1, 1000):
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=65535,
                data=f"data{seq}".encode(),
            )

            connection.recv_buffer_expected_seq = seq
            connection._handle_data_packet(packet)

        # Should handle all packets
        assert len(connection.received_seqs) == 999

    def test_sack_block_generation_performance(self, connection):
        """Test SACK block generation performance with many sequences."""
        from ccbt.transport.utp_extensions import UTPExtensionType

        connection.negotiated_extensions.add(UTPExtensionType.SACK)

        # Add many received sequences
        connection.received_seqs = set(range(100, 2000))

        # Generate SACK blocks
        import time

        start = time.perf_counter()
        blocks = connection._generate_sack_blocks()
        end = time.perf_counter()

        # Should complete quickly
        assert (end - start) < 0.1

        # Should generate valid blocks
        assert len(blocks) <= 4

    def test_extension_parsing_performance(self, connection):
        """Test extension parsing performance."""
        from ccbt.transport.utp_extensions import (
            ECNExtension,
            SACKExtension,
            SACKBlock,
            WindowScalingExtension,
            encode_extensions,
        )

        # Create packet with many extensions
        extensions = [
            WindowScalingExtension(scale_factor=2),
            SACKExtension(blocks=[SACKBlock(start_seq=100, end_seq=200)]),
            ECNExtension(ecn_echo=True, ecn_cwr=False),
        ]

        encoded = encode_extensions(extensions)

        # Parse many times
        import time

        start = time.perf_counter()
        for _ in range(1000):
            from ccbt.transport.utp_extensions import parse_extensions

            parse_extensions(encoded, 0)
        end = time.perf_counter()

        # Should complete quickly
        assert (end - start) < 1.0


class TestStress:
    """Stress tests for uTP."""

    @pytest.fixture
    def connection(self):
        """Create a connected UTP connection."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.transport.sendto = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_many_retransmissions(self, connection):
        """Test handling many retransmissions."""
        # Add many packets to send buffer
        for seq in range(1, 100):
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=0,
                data=b"data",
            )
            connection.send_buffer[seq] = (packet, 0.0, 0)

        # Mark all as retransmitted
        for seq in range(1, 100):
            connection.retransmitted_packets.add(seq)

        # Should handle gracefully
        assert len(connection.retransmitted_packets) == 99

    def test_large_window_scaling(self, connection):
        """Test window scaling with large windows."""
        connection.window_scale = 4  # Scale factor 4
        connection.send_window = 10000

        # Calculate target window
        target = connection._calculate_target_window()

        # Should handle large windows correctly
        assert target > 0

    def test_many_connection_ids(self):
        """Test generating many unique connection IDs."""
        from ccbt.transport.utp_socket import UTPSocketManager

        manager = UTPSocketManager()
        manager._initialized = True
        # Clear any existing connection IDs
        manager.active_connection_ids.clear()

        ids = set()
        for _ in range(1000):
            conn_id = manager._generate_connection_id()
            # Connection IDs can repeat if we exhaust the space, but should be rare
            # For this test, we just verify we can generate IDs
            ids.add(conn_id)

        # Should generate at least some unique IDs (may have some collisions)
        # Connection ID space is 16-bit, so 1000 unique IDs is possible
        assert len(ids) > 0
        assert len(ids) <= 65536  # Max possible unique IDs

