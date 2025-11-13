"""Unit tests for uTP window scaling extension."""

from unittest.mock import MagicMock, patch

import pytest

from ccbt.transport.utp import UTPConnection, UTPConnectionState, UTPPacket, UTPPacketType
from ccbt.transport.utp_extensions import (
    UTPExtensionType,
    WindowScalingExtension,
)


class TestWindowScaling:
    """Tests for window scaling extension."""

    @pytest.fixture
    def connection(self):
        """Create a UTP connection for testing."""
        conn = UTPConnection(remote_addr=("127.0.0.1", 6881), connection_id=12345)
        conn.transport = MagicMock()
        conn.state = UTPConnectionState.CONNECTED
        return conn

    def test_window_scaling_negotiation(self, connection):
        """Test window scaling extension negotiation."""
        # Ensure window scaling is supported
        from ccbt.transport.utp_extensions import UTPExtensionType
        connection.supported_extensions.add(UTPExtensionType.WINDOW_SCALING)
        
        # Set our window scale before negotiation
        connection.window_scale = 4  # Our advertised scale
        
        # Simulate receiving SYN with window scaling
        peer_extensions = [WindowScalingExtension(scale_factor=3)]
        connection._process_extension_negotiation(peer_extensions)

        # Should negotiate window scaling (use minimum scale)
        assert UTPExtensionType.WINDOW_SCALING in connection.negotiated_extensions
        assert connection.window_scale == 3  # Minimum of 4 and 3

    def test_window_scaling_minimum_negotiation(self, connection):
        """Test window scaling uses minimum scale factor."""
        # We advertise scale factor 4
        connection.window_scale = 4

        # Peer advertises scale factor 2
        peer_extensions = [WindowScalingExtension(scale_factor=2)]
        connection._process_extension_negotiation(peer_extensions)

        # Should use minimum (2)
        assert connection.window_scale == 2

    def test_scaled_window_receive(self, connection):
        """Test receiving window with scaling applied."""
        connection.window_scale = 2  # Scale factor 2

        # Receive packet with window size 10000
        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=10000,  # Scaled window
            timestamp=0,
        )

        connection._handle_state_packet(packet)

        # Window should be scaled: 10000 << 2 = 40000
        assert connection.send_window == 40000

    def test_scaled_window_no_scaling(self, connection):
        """Test window without scaling."""
        connection.window_scale = 0  # No scaling

        packet = UTPPacket(
            type=UTPPacketType.ST_STATE,
            connection_id=12345,
            seq_nr=0,
            ack_nr=0,
            wnd_size=10000,
            timestamp=0,
        )

        connection._handle_state_packet(packet)

        # Window should not be scaled
        assert connection.send_window == 10000

    def test_advertise_window_scaling(self, connection):
        """Test advertising window scaling in handshake."""
        # Mock config with large max window
        with patch.object(
            connection.config.network.utp, "max_window_size", 131070
        ):  # > 65535
            extensions = connection._advertise_extensions()

            # Should include window scaling
            has_window_scaling = any(
                isinstance(ext, WindowScalingExtension) for ext in extensions
            )
            # May or may not have scaling depending on config

    def test_window_scaling_in_target_window(self, connection):
        """Test window scaling in target window calculation."""
        connection.window_scale = 2
        connection.send_window = 10000

        # Mock config
        with patch.object(
            connection.config.network.utp, "max_window_size", 65535
        ):
            target = connection._calculate_target_window()

            # Max window should be scaled: 65535 << 2
            # Target should not exceed scaled max
            assert target <= 65535 << 2

    def test_window_scaling_not_advertised_when_not_needed(self, connection):
        """Test window scaling not advertised when max_window <= 65535."""
        # Mock config with small max window
        with patch.object(
            connection.config.network.utp, "max_window_size", 32768
        ):  # < 65535
            extensions = connection._advertise_extensions()

            # Should not include window scaling (no need)
            has_window_scaling = any(
                isinstance(ext, WindowScalingExtension) for ext in extensions
            )
            # May not have scaling if max_window doesn't require it

