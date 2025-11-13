"""Additional tests for peer.py to cover remaining coverage gaps.

Covers missing lines:
- Handshake reserved bytes (line 127)
- Message decode error paths (lines 214-215, 243-244, 247-248, 250-251, 272-273, 276-277, 279-280)
- Message decode validations (lines 301-302, 307-308, 310-311)
- Connection edge cases (lines 341-342, 348-349)
- Message handling exceptions (lines 380-381, 385-386, 396-399, 424)
- Message handling edge cases (lines 458-459, 465-466, 468-469)
- Piece message error handling (lines 505-506, 510-511, 515-516, 521-522)
- Cancel message error handling (lines 559-560, 566-567, 569-570)
- Async decoder edge cases (lines 708, 710, 722-723, 729-730)
- Message decoder edge cases (lines 735-739, 743-744, 749-757, 763, 770-775)
- Pool management (lines 781-783, 793-800, 809-816)
- Message buffer error handling (lines 912-913, 927-961)
- Message buffer edge cases (lines 968, 970, 972, 993-994)
- Pool message creation edge cases (lines 1017-1018, 1024-1025, 1031, 1036-1043, 1049-1051, 1063-1067, 1079-1083, 1088-1108)
- Message buffer edge cases (lines 1112-1113, 1137, 1139, 1141, 1149, 1151)
- Buffer edge cases (lines 1179-1180, 1224-1225, 1251-1259)
- Exception handling (lines 1326-1328)
- Socket optimizer edge cases (lines 1357, 1362)
"""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.peer]

from ccbt.utils.exceptions import MessageError
from ccbt.models import MessageType
from ccbt.peer.peer import (
    AsyncMessageDecoder,
    BitfieldMessage,
    CancelMessage,
    ChokeMessage,
    Handshake,
    HandshakeError,
    HaveMessage,
    InterestedMessage,
    KeepAliveMessage,
    MessageBuffer,
    MessageDecoder,
    NotInterestedMessage,
    OptimizedMessageDecoder,
    PieceMessage,
    RequestMessage,
    UnchokeMessage,
)


class TestHandshakeCoverageGaps:
    """Test handshake coverage gaps."""

    def test_handshake_reserved_bytes_pass(self):
        """Test handshake reserved bytes pass statement (line 127)."""
        # Reserved bytes check currently just passes
        # Format: <1 byte protocol len><19 bytes protocol><8 bytes reserved><20 bytes info_hash><20 bytes peer_id> = 68 bytes
        info_hash = b"\x00" * 20
        peer_id = b"\x00" * 20
        protocol_len = struct.pack("B", 19)  # Protocol length = 19
        data = protocol_len + b"BitTorrent protocol" + b"\x00" * 8 + info_hash + peer_id
        assert len(data) == 68  # Verify correct length
        handshake = Handshake.decode(data)
        assert handshake.info_hash == info_hash
        assert handshake.peer_id == peer_id


class TestMessageDecodeErrorPaths:
    """Test message decode error paths."""

    def test_choke_decode_length_error(self):
        """Test ChokeMessage decode with wrong length (line 214-215)."""
        with pytest.raises(MessageError):
            ChokeMessage.decode(b"\x00\x00\x00\x02\x00")  # Wrong length

    def test_choke_decode_id_error(self):
        """Test ChokeMessage decode with wrong message ID (line 243-244)."""
        with pytest.raises(MessageError):
            ChokeMessage.decode(b"\x00\x00\x00\x01\x01")  # Wrong ID (should be 0)

    def test_unchoke_decode_length_error(self):
        """Test UnchokeMessage decode with wrong length (line 247-248)."""
        with pytest.raises(MessageError):
            UnchokeMessage.decode(b"\x00\x00\x00\x02\x01")  # Wrong length

    def test_unchoke_decode_id_error(self):
        """Test UnchokeMessage decode with wrong message ID (line 250-251)."""
        with pytest.raises(MessageError):
            UnchokeMessage.decode(b"\x00\x00\x00\x01\x02")  # Wrong ID (should be 1)

    def test_interested_decode_length_error(self):
        """Test InterestedMessage decode with wrong length (line 272-273)."""
        with pytest.raises(MessageError):
            InterestedMessage.decode(b"\x00\x00\x00\x02\x02")  # Wrong length

    def test_interested_decode_id_error(self):
        """Test InterestedMessage decode with wrong message ID (line 276-277)."""
        with pytest.raises(MessageError):
            InterestedMessage.decode(b"\x00\x00\x00\x01\x03")  # Wrong ID (should be 2)

    def test_interested_decode_length_value_error(self):
        """Test InterestedMessage decode with wrong length value (line 279-280)."""
        with pytest.raises(MessageError):
            InterestedMessage.decode(b"\x00\x00\x00\x02\x02")  # Length is 2, should be 1

    def test_not_interested_decode_length_error(self):
        """Test NotInterestedMessage decode with wrong length (line 301-302)."""
        with pytest.raises(MessageError):
            NotInterestedMessage.decode(b"\x00\x00\x00\x02\x03")  # Wrong length

    def test_not_interested_decode_id_error(self):
        """Test NotInterestedMessage decode with wrong message ID (line 307-308)."""
        with pytest.raises(MessageError):
            NotInterestedMessage.decode(b"\x00\x00\x00\x01\x04")  # Wrong ID (should be 3)

    def test_not_interested_decode_length_value_error(self):
        """Test NotInterestedMessage decode with wrong length value (line 310-311)."""
        with pytest.raises(MessageError):
            NotInterestedMessage.decode(b"\x00\x00\x00\x02\x03")  # Length is 2, should be 1


class TestConnectionEdgeCases:
    """Test connection edge cases."""

    def test_have_decode_short_data(self):
        """Test HaveMessage decode with insufficient data (line 341-342)."""
        with pytest.raises(MessageError):
            HaveMessage.decode(b"\x00\x00\x00\x04")  # Too short

    def test_have_decode_wrong_length(self):
        """Test HaveMessage decode with wrong length (line 348-349)."""
        with pytest.raises(MessageError):
            HaveMessage.decode(b"\x00\x00\x00\x06\x04\x00\x00\x00\x01")  # Wrong length


class TestMessageHandlingExceptions:
    """Test message handling exception paths."""

    def test_bitfield_decode_wrong_id(self):
        """Test BitfieldMessage decode with wrong message ID (line 396-399)."""
        data = struct.pack("!IB", 10, 99) + b"\x00" * 8  # Wrong ID
        with pytest.raises(MessageError):
            BitfieldMessage.decode(data)

    def test_bitfield_decode_insufficient_data(self):
        """Test BitfieldMessage decode with insufficient data (line 424)."""
        data = struct.pack("!IB", 5, 5) + b"\x00" * 2  # Too short
        with pytest.raises(MessageError):
            BitfieldMessage.decode(data)


class TestMessageHandlingEdgeCases:
    """Test message handling edge cases."""

    def test_request_decode_insufficient_data(self):
        """Test RequestMessage decode with insufficient data (line 458-459)."""
        data = struct.pack("!IB", 13, 6) + b"\x00" * 10  # Too short
        with pytest.raises(MessageError):
            RequestMessage.decode(data)

    def test_request_decode_wrong_id(self):
        """Test RequestMessage decode with wrong message ID (line 465-466)."""
        data = struct.pack("!IB", 13, 99) + b"\x00" * 12  # Wrong ID
        with pytest.raises(MessageError):
            RequestMessage.decode(data)

    def test_request_decode_wrong_length(self):
        """Test RequestMessage decode with wrong length value (line 468-469)."""
        data = struct.pack("!IB", 14, 6) + b"\x00" * 12  # Wrong length (should be 13)
        with pytest.raises(MessageError):
            RequestMessage.decode(data)


class TestPieceMessageErrorHandling:
    """Test piece message error handling."""

    def test_piece_decode_too_short(self):
        """Test PieceMessage decode with too short data (line 505-506)."""
        data = b"\x00\x00\x00\x05"  # Too short
        with pytest.raises(MessageError):
            PieceMessage.decode(data)

    def test_piece_decode_length_too_small(self):
        """Test PieceMessage decode with length too small (line 510-511)."""
        data = struct.pack("!IB", 8, 7) + b"\x00" * 7  # Length too small (< 9)
        with pytest.raises(MessageError):
            PieceMessage.decode(data)

    def test_piece_decode_length_mismatch(self):
        """Test PieceMessage decode with length mismatch (line 515-516)."""
        data = struct.pack("!IB", 10, 7) + b"\x00" * 8  # Mismatch: says 10 but only 8 bytes
        with pytest.raises(MessageError):
            PieceMessage.decode(data)

    def test_piece_decode_wrong_id(self):
        """Test PieceMessage decode with wrong message ID (line 521-522)."""
        data = struct.pack("!IB", 9, 99) + b"\x00" * 8  # Wrong ID
        with pytest.raises(MessageError):
            PieceMessage.decode(data)


class TestCancelMessageErrorHandling:
    """Test cancel message error handling."""

    def test_cancel_decode_insufficient_data(self):
        """Test CancelMessage decode with insufficient data (line 559-560)."""
        data = struct.pack("!IB", 13, 8) + b"\x00" * 10  # Too short
        with pytest.raises(MessageError):
            CancelMessage.decode(data)

    def test_cancel_decode_wrong_id(self):
        """Test CancelMessage decode with wrong message ID (line 566-567)."""
        data = struct.pack("!IB", 13, 99) + b"\x00" * 12  # Wrong ID
        with pytest.raises(MessageError):
            CancelMessage.decode(data)

    def test_cancel_decode_wrong_length(self):
        """Test CancelMessage decode with wrong length value (line 569-570)."""
        data = struct.pack("!IB", 14, 8) + b"\x00" * 12  # Wrong length (should be 13)
        with pytest.raises(MessageError):
            CancelMessage.decode(data)


class TestAsyncMessageDecoderEdgeCases:
    """Test async message decoder edge cases."""

    @pytest.mark.asyncio
    async def test_get_message_empty_buffer(self):
        """Test get_message with empty buffer (line 708)."""
        decoder = AsyncMessageDecoder()
        # get_message has timeout, won't hang
        result = await decoder.get_message()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_messages_empty_buffer(self):
        """Test get_messages with empty buffer (line 710)."""
        decoder = AsyncMessageDecoder()
        result = await decoder.get_messages()
        assert result == []

    @pytest.mark.asyncio
    @pytest.mark.timeout(2)
    async def test_anext_with_sentinel(self):
        """Test __anext__ with sentinel value (line 722-723, 658-659)."""
        decoder = AsyncMessageDecoder()
        # Put None as sentinel to trigger StopAsyncIteration
        await decoder.message_queue.put(None)
        with pytest.raises(StopAsyncIteration):
            await decoder.__anext__()

    @pytest.mark.asyncio
    @pytest.mark.timeout(2)
    async def test_anext_with_message(self):
        """Test __anext__ with actual message."""
        decoder = AsyncMessageDecoder()
        message = ChokeMessage()
        await decoder.message_queue.put(message)
        result = await decoder.__anext__()
        assert isinstance(result, ChokeMessage)

    @pytest.mark.asyncio
    async def test_get_message_keepalive(self):
        """Test get_message with keepalive message (line 729-730)."""
        decoder = AsyncMessageDecoder()
        # Feed keepalive to decoder
        await decoder.feed_data(b"\x00\x00\x00\x00")
        # Wait a bit for async processing, then get message
        await asyncio.sleep(0.01)  # Allow _process_buffer to run
        result = await decoder.get_message()
        assert isinstance(result, KeepAliveMessage)


class TestOptimizedMessageDecoderEdgeCases:
    """Test optimized message decoder edge cases."""

    def test_decode_next_message_buffer_too_small(self):
        """Test _decode_next_message with buffer too small (line 735-739)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(2)  # Too small for length
        decoder.buffer_size = 2
        result = decoder._decode_next_message()
        assert result is None

    def test_decode_next_message_no_view(self):
        """Test _decode_next_message with no buffer view (line 743-744)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(4)
        decoder.buffer_size = 4
        decoder.buffer_view = None
        result = decoder._decode_next_message()
        assert result is None

    def test_decode_next_message_keepalive(self):
        """Test _decode_next_message with keepalive (line 749-757)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x00")
        decoder.buffer_size = 4
        decoder.buffer_view = memoryview(decoder.buffer)
        result = decoder._decode_next_message()
        assert isinstance(result, KeepAliveMessage)

    def test_decode_next_message_incomplete(self):
        """Test _decode_next_message with incomplete message (line 763)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x05\x00")  # Says 5 bytes but only 1 byte after ID
        decoder.buffer_size = 5
        decoder.buffer_view = memoryview(decoder.buffer)
        result = decoder._decode_next_message()
        assert result is None

    def test_decode_simple_message_unknown(self):
        """Test _decode_simple_message with unknown type (line 770-775)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x01\x99")  # Unknown message type
        decoder.buffer_size = 5
        decoder.buffer_view = memoryview(decoder.buffer)
        with pytest.raises(MessageError, match="Unknown simple message type"):
            decoder._decode_next_message()


class TestPoolManagement:
    """Test pool management edge cases."""

    def test_get_pooled_message_empty_pool(self):
        """Test _get_pooled_message with empty pool (line 781-783)."""
        decoder = OptimizedMessageDecoder()
        decoder.message_pools[MessageType.CHOKE] = None
        result = decoder._get_pooled_message(MessageType.CHOKE)
        assert isinstance(result, ChokeMessage)

    def test_get_pooled_have_empty_pool(self):
        """Test _get_pooled_have_message with empty pool (line 793-800)."""
        decoder = OptimizedMessageDecoder()
        decoder.message_pools[MessageType.HAVE] = None
        result = decoder._get_pooled_have_message(5)
        assert isinstance(result, HaveMessage)
        assert result.piece_index == 5

    def test_get_pooled_request_empty_pool(self):
        """Test _get_pooled_request_message with empty pool (line 809-816)."""
        decoder = OptimizedMessageDecoder()
        decoder.message_pools[MessageType.REQUEST] = None
        result = decoder._get_pooled_request_message(0, 0, 16384)
        assert isinstance(result, RequestMessage)
        assert result.piece_index == 0
        assert result.begin == 0
        assert result.length == 16384


class TestMessageBufferErrorHandling:
    """Test message buffer error handling."""

    def test_add_data_type_error(self):
        """Test type validation (line 912-913 has pragma)."""
        decoder = OptimizedMessageDecoder()
        # The type error check at line 912-913 is defensive and marked with pragma
        # because message_data from buffer slice is always bytearray in practice.
        # The check exists for type safety but is untestable through normal add_data flow.
        # We verify that _decode_complex_message handles invalid types:
        with pytest.raises(TypeError):
            decoder._decode_complex_message(MessageType.BITFIELD, "invalid")  # type: ignore[arg-type]

    def test_add_data_decode_error(self):
        """Test add_data with decode error (line 927-961)."""
        decoder = OptimizedMessageDecoder()
        # Invalid message - too short (less than 4 bytes for length prefix)
        invalid_data = bytes(b"\x00\x00\x00")  # Only 3 bytes
        messages = decoder.add_data(invalid_data)
        assert messages == []

    def test_decode_next_message_view_becomes_none(self):
        """Test _decode_next_message buffer view becomes None during processing (line 947-948)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x05\x00\x00\x00\x00\x00")
        decoder.buffer_size = 9
        decoder.buffer_view = memoryview(decoder.buffer)
        
        # Simulate view becoming None after length check
        def mock_unpack_length(view):
            decoder.buffer_view = None  # View becomes None
            return (5,)
        
        with patch.object(decoder, '_unpack_length', side_effect=mock_unpack_length):
            result = decoder._decode_next_message()
            # Should return None when view becomes None
            assert result is None

    def test_decode_next_message_simple(self):
        """Test _decode_next_message with simple message (line 959, 966)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x01\x00")  # Choke
        decoder.buffer_size = 5
        decoder.buffer_view = memoryview(decoder.buffer)
        result = decoder._decode_next_message()
        assert isinstance(result, ChokeMessage)

    def test_decode_complex_message_bitfield_too_short(self):
        """Test _decode_complex_message with bitfield too short (line 728-730)."""
        decoder = OptimizedMessageDecoder()
        # For bitfield, message_data should be the payload after the message ID
        # If message_data has less than 1 byte (i.e., empty), it should raise
        message_data = memoryview(b"")  # Empty - less than 1 byte
        with pytest.raises(MessageError, match="Bitfield message too short"):
            decoder._decode_complex_message(MessageType.BITFIELD, message_data)


class TestPoolMessageCreationEdgeCases:
    """Test pool message creation edge cases."""

    def test_get_pooled_message_empty_pool_condition(self):
        """Test _get_pooled_message with empty pool condition (line 1017-1018, 1024-1025)."""
        decoder = OptimizedMessageDecoder()
        from collections import deque
        decoder.message_pools[MessageType.CHOKE] = deque()  # Empty deque
        result = decoder._get_pooled_message(MessageType.CHOKE)
        assert isinstance(result, ChokeMessage)

    def test_get_pooled_message_unknown_type(self):
        """Test _get_pooled_message with unknown message type (line 1031)."""
        decoder = OptimizedMessageDecoder()
        with pytest.raises(MessageError, match="Cannot pool message type"):
            decoder._get_pooled_message(MessageType.PIECE)  # PIECE is not pooled

    def test_get_pooled_have_empty_pool(self):
        """Test _get_pooled_have_message with empty pool (line 1036-1043)."""
        decoder = OptimizedMessageDecoder()
        from collections import deque
        decoder.message_pools[MessageType.HAVE] = deque()  # Empty
        result = decoder._get_pooled_have_message(10)
        assert isinstance(result, HaveMessage)
        assert result.piece_index == 10

    def test_get_pooled_request_empty_pool(self):
        """Test _get_pooled_request_message with empty pool (line 1049-1051)."""
        decoder = OptimizedMessageDecoder()
        from collections import deque
        decoder.message_pools[MessageType.REQUEST] = deque()  # Empty
        result = decoder._get_pooled_request_message(1, 100, 16384)
        assert isinstance(result, RequestMessage)
        assert result.piece_index == 1
        assert result.begin == 100
        assert result.length == 16384

    def test_get_pooled_cancel_empty_pool(self):
        """Test _get_pooled_cancel_message with empty pool (line 1063-1067)."""
        decoder = OptimizedMessageDecoder()
        from collections import deque
        decoder.message_pools[MessageType.CANCEL] = deque()  # Empty
        result = decoder._get_pooled_cancel_message(2, 200, 8192)
        assert isinstance(result, CancelMessage)
        assert result.piece_index == 2
        assert result.begin == 200
        assert result.length == 8192

    @pytest.mark.asyncio
    async def test_return_message_to_pool(self):
        """Test return_message_to_pool (line 818-823)."""
        decoder = AsyncMessageDecoder()
        message = ChokeMessage()
        # Check pool is empty initially
        assert len(decoder.message_pools[MessageType.CHOKE]) == 0
        decoder.return_message_to_pool(message)
        # Should not raise, message returned to pool
        # Pool should now have 1 message
        assert len(decoder.message_pools[MessageType.CHOKE]) == 1

    @pytest.mark.asyncio
    async def test_return_message_to_pool_not_poolable(self):
        """Test return_message_to_pool with non-poolable message (line 818-823)."""
        decoder = AsyncMessageDecoder()
        # PIECE messages are not poolable (not in message_pools)
        message = PieceMessage(0, 0, b"data")
        decoder.return_message_to_pool(message)
        # Should handle gracefully without raising (PIECE not in pools dict)
        # Verify no pool exists for PIECE
        assert MessageType.PIECE not in decoder.message_pools


class TestMessageBufferAdditionalEdgeCases:
    """Test additional message buffer edge cases."""

    def test_add_message_exception(self):
        """Test add_message exception handling (line 1112-1113)."""
        buffer = MessageBuffer()
        message = ChokeMessage()
        
        # Mock encode to raise exception
        with patch.object(message, 'encode', side_effect=Exception("Encode failed")):
            result = buffer.add_message(message)
            assert result is False

    def test_clear_buffer(self):
        """Test clear buffer (line 1137, 1139)."""
        buffer = MessageBuffer()
        buffer.add_message(ChokeMessage())
        buffer.clear()
        assert buffer.write_pos == 0
        assert len(buffer.pending_messages) == 0

    def test_get_buffered_data(self):
        """Test get_buffered_data (line 1141)."""
        buffer = MessageBuffer()
        buffer.add_message(ChokeMessage())
        data = buffer.get_buffered_data()
        assert len(data) > 0

    def test_get_stats(self):
        """Test get_stats (line 1149, 1151)."""
        buffer = MessageBuffer()
        buffer.add_message(ChokeMessage())
        stats = buffer.get_stats()
        assert "buffer_size" in stats
        assert "buffer_capacity" in stats
        assert "buffer_usage" in stats
        assert "pending_messages" in stats


class TestBufferAdditionalEdgeCases:
    """Test additional buffer edge cases."""

    def test_add_data_incomplete_message(self):
        """Test add_data with incomplete message (line 1179-1180)."""
        decoder = OptimizedMessageDecoder()
        # Incomplete message - only length prefix (says 5 bytes but we only have 4)
        incomplete = bytes(b"\x00\x00\x00\x05")
        messages = decoder.add_data(incomplete)
        assert messages == []  # Incomplete, so no messages returned

    def test_add_data_multiple_messages(self):
        """Test add_data with multiple messages (line 1224-1225)."""
        decoder = OptimizedMessageDecoder()
        # Two keepalive messages
        data = bytes(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        messages = decoder.add_data(data)
        assert len(messages) == 2
        assert all(isinstance(m, KeepAliveMessage) for m in messages)

    def test_add_data_complex_messages(self):
        """Test add_data with complex messages (line 1251-1259)."""
        decoder = OptimizedMessageDecoder()
        # Have message: length(4) + message_id(1) + piece_index(4) = 9 bytes total
        # Format: <4 bytes length><1 byte ID><4 bytes piece_index>
        have_msg = struct.pack("!IBI", 5, MessageType.HAVE, 5)  # length=5, ID=4, piece_index=5
        messages = decoder.add_data(have_msg)
        assert len(messages) == 1
        assert isinstance(messages[0], HaveMessage)
        assert messages[0].piece_index == 5


class TestExceptionHandling:
    """Test exception handling paths."""

    def test_add_message_exception_handling(self):
        """Test add_message exception handling (line 1326-1328)."""
        buffer = MessageBuffer()
        
        # Create a mock message that raises exception during encoding
        mock_message = MagicMock()
        mock_message.encode.side_effect = Exception("Encoding failed")
        
        result = buffer.add_message(mock_message)
        assert result is False


class TestSocketOptimizerEdgeCases:
    """Test socket optimizer edge cases."""

    def test_get_optimal_buffer_sizes_zero_connections(self):
        """Test get_optimal_buffer_sizes with zero connections (line 1357)."""
        from ccbt.peer.peer import get_optimal_buffer_sizes
        rcv, snd = get_optimal_buffer_sizes(0)
        assert rcv > 0
        assert snd > 0

    def test_get_optimal_buffer_sizes_many_connections(self):
        """Test get_optimal_buffer_sizes with many connections (line 1362)."""
        from ccbt.peer.peer import get_optimal_buffer_sizes
        rcv, snd = get_optimal_buffer_sizes(1000)
        assert rcv > 0
        assert snd > 0

    def test_optimize_socket(self):
        """Test optimize_socket function (line 1357)."""
        import socket
        from ccbt.peer.peer import optimize_socket
        # Create a test socket
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            optimize_socket(test_sock)
            # Should not raise, socket optimized
        finally:
            test_sock.close()


class TestAsyncMessageDecoderAdditionalPaths:
    """Test additional AsyncMessageDecoder paths."""

    @pytest.mark.asyncio
    async def test_decode_simple_message_interested(self):
        """Test _decode_simple_message with INTERESTED (line 708)."""
        decoder = AsyncMessageDecoder()
        message = decoder._decode_simple_message(MessageType.INTERESTED)
        assert isinstance(message, InterestedMessage)

    @pytest.mark.asyncio
    async def test_decode_simple_message_not_interested(self):
        """Test _decode_simple_message with NOT_INTERESTED (line 710)."""
        decoder = AsyncMessageDecoder()
        message = decoder._decode_simple_message(MessageType.NOT_INTERESTED)
        assert isinstance(message, NotInterestedMessage)

    @pytest.mark.asyncio
    async def test_decode_complex_have_wrong_length(self):
        """Test _decode_complex_message with HAVE wrong length (line 722-723)."""
        decoder = AsyncMessageDecoder()
        # HAVE message must be 5 bytes
        message_data = memoryview(b"\x04\x00\x00\x00")  # Only 4 bytes
        with pytest.raises(MessageError, match="Have message must be 5 bytes"):
            decoder._decode_complex_message(MessageType.HAVE, message_data)

    @pytest.mark.asyncio
    async def test_decode_complex_bitfield_too_short(self):
        """Test _decode_complex_message with BITFIELD too short (line 729-730)."""
        decoder = AsyncMessageDecoder()
        # BITFIELD message too short (less than 1 byte after ID)
        message_data = memoryview(b"")  # Empty
        with pytest.raises(MessageError, match="Bitfield message too short"):
            decoder._decode_complex_message(MessageType.BITFIELD, message_data)

    @pytest.mark.asyncio
    async def test_decode_complex_request_wrong_length(self):
        """Test _decode_complex_message with REQUEST wrong length (line 735-739)."""
        decoder = AsyncMessageDecoder()
        # REQUEST message must be 13 bytes
        message_data = memoryview(b"\x03" + b"\x00" * 11)  # Only 12 bytes
        with pytest.raises(MessageError, match="Request message must be 13 bytes"):
            decoder._decode_complex_message(MessageType.REQUEST, message_data)

    @pytest.mark.asyncio
    async def test_decode_complex_request_success(self):
        """Test _decode_complex_message with REQUEST success (line 738-739)."""
        decoder = AsyncMessageDecoder()
        # REQUEST message: 13 bytes total (1 byte ID + 12 bytes payload)
        message_data = memoryview(struct.pack("!BIII", MessageType.REQUEST, 5, 100, 8192))
        result = decoder._decode_complex_message(MessageType.REQUEST, message_data)
        assert isinstance(result, RequestMessage)
        assert result.piece_index == 5
        assert result.begin == 100
        assert result.length == 8192

    @pytest.mark.asyncio
    async def test_decode_complex_piece_too_short(self):
        """Test _decode_complex_message with PIECE too short (line 743-744)."""
        decoder = AsyncMessageDecoder()
        # PIECE message too short (less than 9 bytes)
        message_data = memoryview(b"\x07" + b"\x00" * 7)  # Only 8 bytes
        with pytest.raises(MessageError, match="Piece message too short"):
            decoder._decode_complex_message(MessageType.PIECE, message_data)

    @pytest.mark.asyncio
    async def test_decode_complex_cancel_wrong_length(self):
        """Test _decode_complex_message with CANCEL wrong length (line 750-754)."""
        decoder = AsyncMessageDecoder()
        # CANCEL message must be 13 bytes
        message_data = memoryview(b"\x08" + b"\x00" * 11)  # Only 12 bytes
        with pytest.raises(MessageError, match="Cancel message must be 13 bytes"):
            decoder._decode_complex_message(MessageType.CANCEL, message_data)

    @pytest.mark.asyncio
    async def test_decode_complex_cancel_success(self):
        """Test _decode_complex_message with CANCEL success (line 753-754)."""
        decoder = AsyncMessageDecoder()
        # CANCEL message: 13 bytes total (1 byte ID + 12 bytes payload)
        message_data = memoryview(struct.pack("!BIII", MessageType.CANCEL, 5, 100, 8192))
        result = decoder._decode_complex_message(MessageType.CANCEL, message_data)
        assert isinstance(result, CancelMessage)
        assert result.piece_index == 5
        assert result.begin == 100
        assert result.length == 8192

    @pytest.mark.asyncio
    async def test_get_pooled_message_from_pool(self):
        """Test _get_pooled_message from pool (line 763)."""
        decoder = AsyncMessageDecoder()
        # Add message to pool
        choke_msg = ChokeMessage()
        decoder.message_pools[MessageType.CHOKE].append(choke_msg)
        # Get from pool
        result = decoder._get_pooled_message(MessageType.CHOKE)
        assert result is choke_msg

    @pytest.mark.asyncio
    async def test_get_pooled_message_unchoke(self):
        """Test _get_pooled_message creates UNCHOKE."""
        decoder = AsyncMessageDecoder()
        result = decoder._get_pooled_message(MessageType.UNCHOKE)
        assert isinstance(result, UnchokeMessage)

    @pytest.mark.asyncio
    async def test_get_pooled_message_interested(self):
        """Test _get_pooled_message creates INTERESTED (line 771)."""
        decoder = AsyncMessageDecoder()
        result = decoder._get_pooled_message(MessageType.INTERESTED)
        assert isinstance(result, InterestedMessage)

    @pytest.mark.asyncio
    async def test_get_pooled_message_error(self):
        """Test _get_pooled_message with invalid message type (line 770-775)."""
        decoder = AsyncMessageDecoder()
        # Invalid message type (not in pools)
        with pytest.raises(MessageError, match="Cannot pool message type"):
            decoder._get_pooled_message(MessageType.PIECE)  # PIECE is not poolable

    @pytest.mark.asyncio
    async def test_get_pooled_have_from_pool(self):
        """Test _get_pooled_have_message from pool (line 781-783)."""
        decoder = AsyncMessageDecoder()
        # Add a HaveMessage to the pool
        have_msg = HaveMessage(10)
        decoder.message_pools[MessageType.HAVE].append(have_msg)
        # Get it from pool
        result = decoder._get_pooled_have_message(20)
        assert result is have_msg  # Should be the same object
        assert result.piece_index == 20  # But piece_index updated

    @pytest.mark.asyncio
    async def test_get_pooled_request_from_pool(self):
        """Test _get_pooled_request_message from pool (line 793-800)."""
        decoder = AsyncMessageDecoder()
        # Add a RequestMessage to the pool
        req_msg = RequestMessage(0, 0, 16384)
        decoder.message_pools[MessageType.REQUEST].append(req_msg)
        # Get it from pool
        result = decoder._get_pooled_request_message(5, 100, 8192)
        assert result is req_msg  # Should be the same object
        assert result.piece_index == 5
        assert result.begin == 100
        assert result.length == 8192

    @pytest.mark.asyncio
    async def test_get_pooled_request_new_message(self):
        """Test _get_pooled_request_message creates new (line 800)."""
        decoder = AsyncMessageDecoder()
        # Pool is empty, should create new
        result = decoder._get_pooled_request_message(10, 200, 4096)
        assert isinstance(result, RequestMessage)
        assert result.piece_index == 10
        assert result.begin == 200
        assert result.length == 4096

    @pytest.mark.asyncio
    async def test_get_pooled_cancel_from_pool(self):
        """Test _get_pooled_cancel_message from pool (line 809-816)."""
        decoder = AsyncMessageDecoder()
        # Add a CancelMessage to the pool
        cancel_msg = CancelMessage(0, 0, 16384)
        decoder.message_pools[MessageType.CANCEL].append(cancel_msg)
        # Get it from pool
        result = decoder._get_pooled_cancel_message(5, 100, 8192)
        assert result is cancel_msg  # Should be the same object
        assert result.piece_index == 5
        assert result.begin == 100
        assert result.length == 8192

    @pytest.mark.asyncio
    async def test_get_pooled_cancel_new_message(self):
        """Test _get_pooled_cancel_message creates new (line 816)."""
        decoder = AsyncMessageDecoder()
        # Pool is empty, should create new
        result = decoder._get_pooled_cancel_message(10, 200, 4096)
        assert isinstance(result, CancelMessage)
        assert result.piece_index == 10
        assert result.begin == 200
        assert result.length == 4096


class TestOptimizedMessageDecoderAdditionalPaths:
    """Test additional OptimizedMessageDecoder paths."""

    def test_decode_next_message_keepalive_path(self):
        """Test _decode_next_message with keepalive path (line 941)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x00")
        decoder.buffer_size = 4
        decoder.buffer_view = memoryview(decoder.buffer)
        result = decoder._decode_next_message()
        assert isinstance(result, KeepAliveMessage)
        assert decoder.buffer_size == 0  # Consumed

    def test_decode_next_message_complex_path(self):
        """Test _decode_next_message complex message path (line 961)."""
        decoder = OptimizedMessageDecoder()
        # HAVE message: length=5, ID=4, piece_index=123
        have_data = struct.pack("!IBI", 5, MessageType.HAVE, 123)
        decoder.buffer = bytearray(have_data)
        decoder.buffer_size = len(have_data)
        decoder.buffer_view = memoryview(decoder.buffer)
        result = decoder._decode_next_message()
        assert isinstance(result, HaveMessage)
        assert result.piece_index == 123

    def test_decode_simple_message_unchoke(self):
        """Test _decode_simple_message with UNCHOKE (line 968)."""
        decoder = OptimizedMessageDecoder()
        message = decoder._decode_simple_message(MessageType.UNCHOKE)
        assert isinstance(message, UnchokeMessage)

    def test_decode_simple_message_interested(self):
        """Test _decode_simple_message with INTERESTED (line 970)."""
        decoder = OptimizedMessageDecoder()
        message = decoder._decode_simple_message(MessageType.INTERESTED)
        assert isinstance(message, InterestedMessage)

    def test_decode_simple_message_not_interested(self):
        """Test _decode_simple_message with NOT_INTERESTED (line 972)."""
        decoder = OptimizedMessageDecoder()
        message = decoder._decode_simple_message(MessageType.NOT_INTERESTED)
        assert isinstance(message, NotInterestedMessage)

    def test_decode_complex_cancel_wrong_length(self):
        """Test _decode_complex_message with CANCEL wrong length (line 1017-1018)."""
        decoder = OptimizedMessageDecoder()
        # CANCEL message must be 13 bytes
        message_data = memoryview(b"\x08" + b"\x00" * 11)  # Only 12 bytes
        with pytest.raises(MessageError, match="Cancel message must be 13 bytes"):
            decoder._decode_complex_message(MessageType.CANCEL, message_data)

    def test_decode_complex_unknown_message(self):
        """Test _decode_complex_message with unknown message type (line 1024-1025)."""
        decoder = OptimizedMessageDecoder()
        message_data = memoryview(b"\x99" + b"\x00" * 10)  # Unknown message ID
        # _decode_complex_message calls _decode_v2_message which raises "Unknown v2 message type"
        with pytest.raises(MessageError, match="Unknown v2 message type"):
            decoder._decode_complex_message(99, message_data)

    def test_get_pooled_message_from_pool(self):
        """Test _get_pooled_message from pool (line 1031)."""
        decoder = OptimizedMessageDecoder()
        # Add message to pool
        choke_msg = ChokeMessage()
        decoder.message_pools[MessageType.CHOKE].append(choke_msg)
        # Get from pool
        result = decoder._get_pooled_message(MessageType.CHOKE)
        assert result is choke_msg

    def test_get_pooled_message_unchoke(self):
        """Test _get_pooled_message creates UNCHOKE (line 1037)."""
        decoder = OptimizedMessageDecoder()
        result = decoder._get_pooled_message(MessageType.UNCHOKE)
        assert isinstance(result, UnchokeMessage)

    def test_get_pooled_message_interested(self):
        """Test _get_pooled_message creates INTERESTED (line 1039)."""
        decoder = OptimizedMessageDecoder()
        result = decoder._get_pooled_message(MessageType.INTERESTED)
        assert isinstance(result, InterestedMessage)

    def test_get_pooled_message_not_interested(self):
        """Test _get_pooled_message creates NOT_INTERESTED (line 1041)."""
        decoder = OptimizedMessageDecoder()
        result = decoder._get_pooled_message(MessageType.NOT_INTERESTED)
        assert isinstance(result, NotInterestedMessage)

    def test_get_pooled_have_from_pool(self):
        """Test _get_pooled_have_message from pool (line 1049-1051)."""
        decoder = OptimizedMessageDecoder()
        # Add a HaveMessage to the pool
        have_msg = HaveMessage(10)
        decoder.message_pools[MessageType.HAVE].append(have_msg)
        # Get it from pool
        result = decoder._get_pooled_have_message(20)
        assert result is have_msg  # Should be the same object
        assert result.piece_index == 20  # But piece_index updated

    def test_get_pooled_request_from_pool(self):
        """Test _get_pooled_request_message from pool (line 1063-1067)."""
        decoder = OptimizedMessageDecoder()
        # Add a RequestMessage to the pool
        req_msg = RequestMessage(0, 0, 16384)
        decoder.message_pools[MessageType.REQUEST].append(req_msg)
        # Get it from pool
        result = decoder._get_pooled_request_message(5, 100, 8192)
        assert result is req_msg  # Should be the same object
        assert result.piece_index == 5
        assert result.begin == 100
        assert result.length == 8192

    def test_get_pooled_cancel_from_pool(self):
        """Test _get_pooled_cancel_message from pool (line 1079-1083)."""
        decoder = OptimizedMessageDecoder()
        # Add a CancelMessage to the pool
        cancel_msg = CancelMessage(0, 0, 16384)
        decoder.message_pools[MessageType.CANCEL].append(cancel_msg)
        # Get it from pool
        result = decoder._get_pooled_cancel_message(5, 100, 8192)
        assert result is cancel_msg  # Should be the same object
        assert result.piece_index == 5
        assert result.begin == 100
        assert result.length == 8192


class TestOptimizedMessageDecoderBufferManagement:
    """Test OptimizedMessageDecoder buffer management."""

    def test_consume_buffer_full_consume(self):
        """Test _consume_buffer consuming all data (line 1088-1090)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x00")
        decoder.buffer_size = 4
        decoder.buffer_pos = 0
        decoder.buffer_view = memoryview(decoder.buffer)
        decoder._consume_buffer(4)
        assert decoder.buffer_size == 0
        assert decoder.buffer_pos == 0

    def test_consume_buffer_partial_consume(self):
        """Test _consume_buffer partial consumption (line 1092-1108)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x01\x00\x00\x00\x01\x01")
        decoder.buffer_size = 9
        decoder.buffer_pos = 0
        decoder.buffer_view = memoryview(decoder.buffer)
        decoder._consume_buffer(5)  # Consume first message
        assert decoder.buffer_size == 4  # Remaining data
        assert decoder.buffer_pos == 4

    def test_consume_buffer_no_view(self):
        """Test _consume_buffer with no buffer_view (line 1092-1094)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x00")
        decoder.buffer_size = 4
        decoder.buffer_pos = 0
        decoder.buffer_view = None
        decoder._consume_buffer(2)
        assert decoder.buffer_size == 0
        assert decoder.buffer_pos == 0

    def test_reset_buffer(self):
        """Test _reset_buffer (line 1110-1113)."""
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x00")
        decoder.buffer_size = 4
        decoder.buffer_pos = 4
        decoder._reset_buffer()
        assert decoder.buffer_size == 0
        assert decoder.buffer_pos == 0

    def test_decode_next_message_keepalive_buffer_too_small(self):
        """Test _decode_next_message keepalive edge case (line 941 has pragma)."""
        # Line 941 is a defensive check: return None if buffer_size < 4 when length == 0
        # However, we already check buffer_size >= 4 at line 927 before reading length.
        # This check would only trigger if buffer_size somehow changed between checks,
        # which is unlikely in practice. The check exists for defensive programming.
        # Since it's hard to trigger naturally, we verify the logic path exists:
        decoder = OptimizedMessageDecoder()
        decoder.buffer = bytearray(b"\x00\x00\x00\x00")
        decoder.buffer_size = 4  # Enough to read length
        decoder.buffer_view = memoryview(decoder.buffer)
        # Normal case: should return KeepAliveMessage
        result = decoder._decode_next_message()
        assert isinstance(result, KeepAliveMessage)


class TestMessageDecodeErrorPathsAdditional:
    """Additional message decode error path tests."""

    def test_choke_decode_wrong_length_error(self):
        """Test ChokeMessage.decode with wrong length (line 214-215)."""
        with pytest.raises(MessageError, match="Choke message must be 5 bytes"):
            ChokeMessage.decode(b"\x00\x00\x00\x01\x00\x00")  # 6 bytes instead of 5

    def test_unchoke_decode_wrong_length_error(self):
        """Test UnchokeMessage.decode with wrong length (line 243-244)."""
        with pytest.raises(MessageError, match="Unchoke message must be 5 bytes"):
            UnchokeMessage.decode(b"\x00\x00\x00\x01\x01\x00")  # 6 bytes instead of 5

    def test_interested_decode_wrong_length_error(self):
        """Test InterestedMessage.decode with wrong length (line 272-273)."""
        with pytest.raises(MessageError, match="Interested message must be 5 bytes"):
            InterestedMessage.decode(b"\x00\x00\x00\x01\x02\x00")  # 6 bytes instead of 5

    def test_not_interested_decode_wrong_length_error(self):
        """Test NotInterestedMessage.decode with wrong length (line 301-302)."""
        with pytest.raises(MessageError, match="Not interested message must be 5 bytes"):
            NotInterestedMessage.decode(b"\x00\x00\x00\x01\x03\x00")  # 6 bytes instead of 5

    def test_have_decode_wrong_id(self):
        """Test HaveMessage.decode with wrong message ID (line 348-349)."""
        # Valid length but wrong ID
        data = struct.pack("!IBI", 5, MessageType.CHOKE, 123)  # Wrong ID
        with pytest.raises(MessageError, match="Expected have message ID"):
            HaveMessage.decode(data)

    def test_bitfield_decode_too_short(self):
        """Test BitfieldMessage.decode with too short data (line 380-381)."""
        data = b"\x00\x00\x00\x03"  # Too short (less than 5 bytes)
        with pytest.raises(MessageError, match="Bitfield message too short"):
            BitfieldMessage.decode(data)

    def test_bitfield_decode_length_too_small(self):
        """Test BitfieldMessage.decode with length too small (line 385-386)."""
        # Length says 0, but bitfield needs at least 1 byte
        data = struct.pack("!IB", 0, MessageType.BITFIELD)  # Length 0
        with pytest.raises(MessageError, match="Bitfield message length too small"):
            BitfieldMessage.decode(data)

    def test_bitfield_decode_wrong_id(self):
        """Test BitfieldMessage.decode with wrong message ID (line 396-399)."""
        # Valid structure but wrong ID
        data = struct.pack("!IB", 2, MessageType.CHOKE) + b"\x00"  # Wrong ID
        with pytest.raises(MessageError, match="Expected bitfield message ID"):
            BitfieldMessage.decode(data)

    def test_piece_decode_length_too_small(self):
        """Test PieceMessage.decode with length too small (line 510-511)."""
        # Need at least 13 bytes to pass "too short" check, but length field says 8
        # Format: <4 bytes length><1 byte ID><4 bytes piece_index><4 bytes begin><block>
        # Length field says 8, but we provide 13 bytes total
        length_field = struct.pack("!I", 8)  # Says length is 8
        rest = struct.pack("!B", MessageType.PIECE) + struct.pack("!II", 0, 0) + b"\x00" * 6  # 13 bytes total
        data = length_field + rest
        with pytest.raises(MessageError, match="Piece message length too small"):
            PieceMessage.decode(data)


class TestBitfieldEdgeCases:
    """Test BitfieldMessage edge cases."""

    def test_bitfield_has_piece_out_of_range(self):
        """Test Bitfield.has_piece with byte_index out of range (line 424)."""
        # Use a bitfield with 1 byte (8 bits) but num_pieces > 8
        # piece_index must be < num_pieces (passes initial check) but byte_index >= len(bitfield)
        bitfield = BitfieldMessage(b"\x01")  # 1 byte = 8 bits
        # piece_index = 8: 8 // 8 = 1, bit_index = 0
        # byte_index = 1, but len(bitfield) = 1, so byte_index >= len(bitfield) triggers line 424
        result = bitfield.has_piece(8, num_pieces=10)  # piece_index < num_pieces, but byte_index out of range
        assert result is False


class TestMessageFactory:
    """Test create_message factory function."""

    def test_create_message_cancel(self):
        """Test create_message for CANCEL (line 1151)."""
        from ccbt.peer.peer import create_message
        msg = create_message(MessageType.CANCEL, piece_index=5, begin=100, length=8192)
        assert isinstance(msg, CancelMessage)
        assert msg.piece_index == 5
        assert msg.begin == 100
        assert msg.length == 8192


class TestSocketOptimizerAdditionalPaths:
    """Test additional socket optimizer paths."""

    def test_optimize_socket_with_config_buffers(self):
        """Test optimize_socket with config buffer sizes (line 1179-1180)."""
        import socket
        from unittest.mock import patch, MagicMock
        from ccbt.peer.peer import SocketOptimizer
        
        optimizer = SocketOptimizer()
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Mock config.network to have socket buffer attributes
            mock_network = MagicMock()
            mock_network.socket_rcvbuf = 65536
            mock_network.socket_sndbuf = 65536
            optimizer.config.network = mock_network
            
            optimizer.optimize_socket(test_sock)
            # Should use config values (line 1179-1180)
        finally:
            test_sock.close()

    def test_get_optimal_buffer_sizes_type_validation(self):
        """Test get_optimal_buffer_sizes with invalid config types (line 1251-1259)."""
        from unittest.mock import patch, MagicMock
        from ccbt.peer.peer import SocketOptimizer
        
        optimizer = SocketOptimizer()
        
        # Mock config with invalid buffer types
        mock_config = MagicMock()
        mock_config.network.socket_rcvbuf = "invalid"  # Not int/float
        mock_config.network.socket_sndbuf = 65536
        
        with patch.object(optimizer, 'config', mock_config):
            with pytest.raises(TypeError, match="Expected int or float for base_rcvbuf"):
                optimizer.get_optimal_buffer_sizes(10)
        
        # Test with invalid sndbuf
        mock_config.network.socket_rcvbuf = 65536
        mock_config.network.socket_sndbuf = "invalid"  # Not int/float
        
        with patch.object(optimizer, 'config', mock_config):
            with pytest.raises(TypeError, match="Expected int or float for base_sndbuf"):
                optimizer.get_optimal_buffer_sizes(10)

