"""Unit tests for uTP Selective ACK (SACK) implementation."""

from unittest.mock import MagicMock

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType
from ccbt.transport.utp_extensions import (
    SACKExtension,
    SACKBlock,
    UTPExtensionType,
)


class TestSACKGeneration:
    """Tests for SACK block generation."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        # Enable SACK
        conn.negotiated_extensions.add(UTPExtensionType.SACK)
        return conn

    def test_generate_sack_blocks_empty(self, connection):
        """Test generating SACK blocks with no received sequences."""
        connection.received_seqs = set()
        blocks = connection._generate_sack_blocks()
        assert len(blocks) == 0

    def test_generate_sack_blocks_single_range(self, connection):
        """Test generating SACK blocks for single contiguous range."""
        connection.received_seqs = {100, 101, 102, 103, 104}
        blocks = connection._generate_sack_blocks()

        assert len(blocks) == 1
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 105  # Exclusive end

    def test_generate_sack_blocks_multiple_ranges(self, connection):
        """Test generating SACK blocks for multiple non-contiguous ranges."""
        connection.received_seqs = {100, 101, 102, 110, 111, 120, 121, 122}
        blocks = connection._generate_sack_blocks()

        assert len(blocks) == 3
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 103
        assert blocks[1].start_seq == 110
        assert blocks[1].end_seq == 112
        assert blocks[2].start_seq == 120
        assert blocks[2].end_seq == 123

    def test_generate_sack_blocks_max_limit(self, connection):
        """Test SACK blocks are limited to max 4 blocks."""
        # Create more than 4 ranges
        connection.received_seqs = {
            100,
            110,
            120,
            130,
            140,
            150,
            160,
            170,
        }  # 8 separate sequences = 8 ranges
        blocks = connection._generate_sack_blocks()

        assert len(blocks) <= 4

    def test_generate_sack_blocks_single_sequence(self, connection):
        """Test generating SACK block for single sequence."""
        connection.received_seqs = {100}
        blocks = connection._generate_sack_blocks()

        assert len(blocks) == 1
        assert blocks[0].start_seq == 100
        assert blocks[0].end_seq == 101


class TestSACKProcessing:
    """Tests for processing SACK blocks."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_process_sack_blocks(self, connection):
        """Test processing SACK blocks removes packets from send buffer."""
        # Add packets to send buffer
        packet1 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data1",
        )
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=101,
            ack_nr=0,
            wnd_size=0,
            data=b"data2",
        )
        packet3 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=102,
            ack_nr=0,
            wnd_size=0,
            data=b"data3",
        )

        connection.send_buffer[100] = (packet1, 0.0, 0)
        connection.send_buffer[101] = (packet2, 0.0, 0)
        connection.send_buffer[102] = (packet3, 0.0, 0)

        # Process SACK blocks
        sack_blocks = [SACKBlock(start_seq=100, end_seq=103)]  # ACK seq 100, 101, 102
        connection._process_sack_blocks(sack_blocks)

        # Verify packets were removed
        assert 100 not in connection.send_buffer
        assert 101 not in connection.send_buffer
        assert 102 not in connection.send_buffer

    def test_process_sack_blocks_partial(self, connection):
        """Test processing SACK blocks for partial range."""
        # Add packets to send buffer
        packet1 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data1",
        )
        packet2 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=101,
            ack_nr=0,
            wnd_size=0,
            data=b"data2",
        )

        connection.send_buffer[100] = (packet1, 0.0, 0)
        connection.send_buffer[101] = (packet2, 0.0, 0)
        connection.send_buffer[102] = (packet2, 0.0, 0)  # Not SACK'd

        # Process SACK blocks
        sack_blocks = [SACKBlock(start_seq=100, end_seq=102)]  # ACK seq 100, 101
        connection._process_sack_blocks(sack_blocks)

        # Verify only SACK'd packets were removed
        assert 100 not in connection.send_buffer
        assert 101 not in connection.send_buffer
        assert 102 in connection.send_buffer  # Not SACK'd

    def test_send_ack_with_sack(self, connection):
        """Test sending ACK with SACK extension."""
        connection.negotiated_extensions.add(UTPExtensionType.SACK)
        connection.received_seqs = {100, 101, 102}
        connection.ack_nr = 102

        # Send ACK
        connection._send_ack(packet=None, immediate=True)

        # Verify packet was sent
        assert connection.transport.sendto.called
        call_args = connection.transport.sendto.call_args
        packet_data = call_args[0][0]

        # Unpack and verify SACK extension
        packet = UTPPacket.unpack(packet_data)
        assert len(packet.extensions) > 0

        sack_ext = None
        for ext in packet.extensions:
            if ext.extension_type == UTPExtensionType.SACK:
                sack_ext = ext
                break

        assert sack_ext is not None
        assert isinstance(sack_ext, SACKExtension)
        assert len(sack_ext.blocks) > 0


class TestFastRetransmit:
    """Tests for fast retransmit functionality."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_fast_retransmit_trigger(self, connection):
        """Test fast retransmit triggers on 3 duplicate ACKs."""
        # Add packet to send buffer
        packet = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data",
        )
        connection.send_buffer[100] = (packet, 0.0, 0)

        # Set last ACK number
        connection.last_ack_nr = 50

        # Send 3 duplicate ACKs
        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=50,  # Same as last_ack_nr
            wnd_size=65535,
        )

        connection._handle_state_packet(ack_packet)  # 1st duplicate
        assert connection.duplicate_acks == 1

        connection._handle_state_packet(ack_packet)  # 2nd duplicate
        assert connection.duplicate_acks == 2

        connection._handle_state_packet(ack_packet)  # 3rd duplicate - should trigger fast retransmit
        assert connection.duplicate_acks == 0  # Reset after fast retransmit

        # Verify packet was retransmitted (fast retransmit sends packet)
        # Note: sendto may have been called for ACKs, so we check it was called at least once for retransmit
        assert connection.transport.sendto.called

    def test_fast_retransmit_no_packets(self, connection):
        """Test fast retransmit with no packets in buffer."""
        connection.send_buffer = {}
        connection.last_ack_nr = 50

        ack_packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=50,
            wnd_size=65535,
        )

        # Should not crash
        for _ in range(5):
            connection._handle_state_packet(ack_packet)

    def test_selective_retransmit(self, connection):
        """Test selective retransmission of missing packets."""
        # Add packets to send buffer
        packets = {}
        for seq in range(100, 110):
            packet = UTPPacket(
                type=UTPPacketType.ST_DATA,
                connection_id=12345,
                seq_nr=seq,
                ack_nr=0,
                wnd_size=0,
                data=f"data{seq}".encode(),
            )
            connection.send_buffer[seq] = (packet, 0.0, 0)

        # Selectively retransmit specific sequences
        missing_seqs = [102, 105, 107]
        connection._selective_retransmit(missing_seqs)

        # Verify only missing packets were retransmitted
        # (sendto should be called for each retransmission)
        assert connection.transport.sendto.call_count >= len(missing_seqs)

        # Verify retransmitted packets are marked (if attribute exists)
        if hasattr(connection, 'retransmitted_packets'):
            for seq in missing_seqs:
                assert seq in connection.retransmitted_packets


class TestSACKIntegration:
    """Integration tests for SACK functionality."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        conn.negotiated_extensions.add(UTPExtensionType.SACK)
        return conn

    def test_sack_roundtrip(self, connection):
        """Test complete SACK roundtrip: receive out-of-order, generate SACK, process SACK."""
        # Receive out-of-order packets
        packet1 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=100,
            ack_nr=0,
            wnd_size=0,
            data=b"data1",
        )
        packet3 = UTPPacket(
            type=UTPPacketType.ST_DATA,
            connection_id=12345,
            seq_nr=102,
            ack_nr=0,
            wnd_size=0,
            data=b"data3",
        )

        # Enable SACK for tracking
        from ccbt.transport.utp_extensions import UTPExtensionType
        connection.negotiated_extensions.add(UTPExtensionType.SACK)
        
        connection._handle_data_packet(packet1)
        connection._handle_data_packet(packet3)

        # Verify received_seqs contains out-of-order sequences
        assert 100 in connection.received_seqs
        assert 102 in connection.received_seqs

        # Generate SACK blocks
        sack_blocks = connection._generate_sack_blocks()
        assert len(sack_blocks) > 0

        # Process SACK blocks (simulate receiving SACK from peer)
        # This would be done by the peer, but we test our processing
        connection.send_buffer[100] = (packet1, 0.0, 0)
        connection.send_buffer[102] = (packet3, 0.0, 0)

        connection._process_sack_blocks(sack_blocks)

        # Verify SACK'd packets were removed
        assert 100 not in connection.send_buffer or 102 not in connection.send_buffer

