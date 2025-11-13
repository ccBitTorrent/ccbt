"""Unit tests for uTP extension protocol."""

import pytest

from ccbt.transport.utp_extensions import (
    ECNExtension,
    SACKExtension,
    SACKBlock,
    UTPExtensionType,
    WindowScalingExtension,
    encode_extensions,
    parse_extensions,
)


class TestSACKBlock:
    """Tests for SACKBlock dataclass."""

    def test_sack_block_creation(self):
        """Test creating a valid SACK block."""
        block = SACKBlock(start_seq=100, end_seq=105)
        assert block.start_seq == 100
        assert block.end_seq == 105

    def test_sack_block_invalid_start_seq(self):
        """Test SACK block with invalid start_seq."""
        with pytest.raises(ValueError, match="Invalid start_seq"):
            SACKBlock(start_seq=0x10000, end_seq=0x10005)

    def test_sack_block_invalid_end_seq(self):
        """Test SACK block with invalid end_seq."""
        with pytest.raises(ValueError, match="Invalid end_seq"):
            SACKBlock(start_seq=100, end_seq=0x10000)

    def test_sack_block_start_greater_than_end(self):
        """Test SACK block where start_seq >= end_seq."""
        with pytest.raises(ValueError, match="start_seq.*>=.*end_seq"):
            SACKBlock(start_seq=105, end_seq=100)


class TestSACKExtension:
    """Tests for SACKExtension."""

    def test_sack_extension_empty(self):
        """Test SACK extension with no blocks."""
        ext = SACKExtension(blocks=[])
        assert ext.extension_type == UTPExtensionType.SACK
        assert len(ext.blocks) == 0

    def test_sack_extension_single_block(self):
        """Test SACK extension with single block."""
        block = SACKBlock(start_seq=100, end_seq=105)
        ext = SACKExtension(blocks=[block])
        assert len(ext.blocks) == 1
        assert ext.blocks[0].start_seq == 100
        assert ext.blocks[0].end_seq == 105

    def test_sack_extension_multiple_blocks(self):
        """Test SACK extension with multiple blocks."""
        blocks = [
            SACKBlock(start_seq=100, end_seq=105),
            SACKBlock(start_seq=110, end_seq=115),
        ]
        ext = SACKExtension(blocks=blocks)
        assert len(ext.blocks) == 2

    def test_sack_extension_max_blocks(self):
        """Test SACK extension limits to max 4 blocks."""
        blocks = [
            SACKBlock(start_seq=100, end_seq=105),
            SACKBlock(start_seq=110, end_seq=115),
            SACKBlock(start_seq=120, end_seq=125),
            SACKBlock(start_seq=130, end_seq=135),
            SACKBlock(start_seq=140, end_seq=145),  # 5th block
        ]
        ext = SACKExtension(blocks=blocks)
        assert len(ext.blocks) == 4  # Limited to 4

    def test_sack_extension_pack(self):
        """Test packing SACK extension."""
        block = SACKBlock(start_seq=100, end_seq=105)
        ext = SACKExtension(blocks=[block])
        data = ext.pack()

        assert len(data) == 1 + 4  # block_count (1) + block (4)
        assert data[0] == 1  # block_count

    def test_sack_extension_pack_empty(self):
        """Test packing empty SACK extension."""
        ext = SACKExtension(blocks=[])
        data = ext.pack()
        assert data == b"\x00"

    def test_sack_extension_unpack(self):
        """Test unpacking SACK extension."""
        # Pack: block_count=1, start_seq=100, end_seq=105
        data = b"\x01" + (100).to_bytes(2, "big") + (105).to_bytes(2, "big")
        ext = SACKExtension.unpack(data)

        assert len(ext.blocks) == 1
        assert ext.blocks[0].start_seq == 100
        assert ext.blocks[0].end_seq == 105

    def test_sack_extension_unpack_invalid(self):
        """Test unpacking invalid SACK extension."""
        with pytest.raises(ValueError, match="too small"):
            SACKExtension.unpack(b"")

        with pytest.raises(ValueError, match="too small for"):
            SACKExtension.unpack(b"\x02\x00\x00")  # Claims 2 blocks but insufficient data


class TestWindowScalingExtension:
    """Tests for WindowScalingExtension."""

    def test_window_scaling_extension_creation(self):
        """Test creating window scaling extension."""
        ext = WindowScalingExtension(scale_factor=2)
        assert ext.extension_type == UTPExtensionType.WINDOW_SCALING
        assert ext.scale_factor == 2

    def test_window_scaling_invalid_scale_factor(self):
        """Test window scaling with invalid scale factor."""
        with pytest.raises(ValueError, match="Invalid scale_factor"):
            WindowScalingExtension(scale_factor=15)

        with pytest.raises(ValueError, match="Invalid scale_factor"):
            WindowScalingExtension(scale_factor=-1)

    def test_window_scaling_pack(self):
        """Test packing window scaling extension."""
        ext = WindowScalingExtension(scale_factor=3)
        data = ext.pack()
        assert data == b"\x03"

    def test_window_scaling_unpack(self):
        """Test unpacking window scaling extension."""
        data = b"\x05"
        ext = WindowScalingExtension.unpack(data)
        assert ext.scale_factor == 5

    def test_window_scaling_unpack_invalid(self):
        """Test unpacking invalid window scaling extension."""
        with pytest.raises(ValueError, match="too small"):
            WindowScalingExtension.unpack(b"")


class TestECNExtension:
    """Tests for ECNExtension."""

    def test_ecn_extension_creation(self):
        """Test creating ECN extension."""
        ext = ECNExtension(ecn_echo=False, ecn_cwr=False)
        assert ext.extension_type == UTPExtensionType.ECN
        assert ext.ecn_echo is False
        assert ext.ecn_cwr is False

    def test_ecn_extension_with_flags(self):
        """Test ECN extension with flags set."""
        ext = ECNExtension(ecn_echo=True, ecn_cwr=True)
        assert ext.ecn_echo is True
        assert ext.ecn_cwr is True

    def test_ecn_extension_pack(self):
        """Test packing ECN extension."""
        ext = ECNExtension(ecn_echo=True, ecn_cwr=False)
        data = ext.pack()
        assert data == b"\x01"  # Only echo flag set

        ext = ECNExtension(ecn_echo=False, ecn_cwr=True)
        data = ext.pack()
        assert data == b"\x02"  # Only CWR flag set

        ext = ECNExtension(ecn_echo=True, ecn_cwr=True)
        data = ext.pack()
        assert data == b"\x03"  # Both flags set

    def test_ecn_extension_unpack(self):
        """Test unpacking ECN extension."""
        data = b"\x01"
        ext = ECNExtension.unpack(data)
        assert ext.ecn_echo is True
        assert ext.ecn_cwr is False

        data = b"\x02"
        ext = ECNExtension.unpack(data)
        assert ext.ecn_echo is False
        assert ext.ecn_cwr is True

        data = b"\x03"
        ext = ECNExtension.unpack(data)
        assert ext.ecn_echo is True
        assert ext.ecn_cwr is True

    def test_ecn_extension_unpack_invalid(self):
        """Test unpacking invalid ECN extension."""
        with pytest.raises(ValueError, match="too small"):
            ECNExtension.unpack(b"")


class TestExtensionParsing:
    """Tests for extension parsing and encoding."""

    def test_parse_extensions_empty(self):
        """Test parsing empty extension chain."""
        data = b"\x00"  # Terminator
        extensions, offset = parse_extensions(data, 0)
        assert len(extensions) == 0
        assert offset == 1  # Offset advances past terminator

    def test_parse_extensions_single(self):
        """Test parsing single extension."""
        # SACK extension: type=1, length=5, block_count=1, block=(100, 105)
        sack_data = b"\x01\x05\x01" + (100).to_bytes(2, "big") + (105).to_bytes(2, "big")
        extensions, offset = parse_extensions(sack_data, 0)

        assert len(extensions) == 1
        assert isinstance(extensions[0], SACKExtension)
        assert offset == len(sack_data)

    def test_parse_extensions_multiple(self):
        """Test parsing multiple extensions."""
        # Window scaling: type=2, length=1, scale_factor=3
        ws_data = b"\x02\x01\x03"
        # SACK: type=1, length=5, block_count=1, block=(100, 105)
        sack_data = b"\x01\x05\x01" + (100).to_bytes(2, "big") + (105).to_bytes(2, "big")
        data = ws_data + sack_data

        extensions, offset = parse_extensions(data, 0)

        assert len(extensions) == 2
        assert isinstance(extensions[0], WindowScalingExtension)
        assert isinstance(extensions[1], SACKExtension)
        assert offset == len(data)

    def test_parse_extensions_unknown_type(self):
        """Test parsing extensions with unknown type."""
        # Unknown extension: type=99, length=2, data=0x1234
        data = b"\x63\x02\x12\x34"  # Type 99, length 2
        extensions, offset = parse_extensions(data, 0)

        assert len(extensions) == 0  # Unknown extensions skipped
        assert offset == len(data)

    def test_parse_extensions_incomplete(self):
        """Test parsing incomplete extension data."""
        # Extension claims length 5 but only 2 bytes available
        data = b"\x01\x05\x01\x00"
        extensions, offset = parse_extensions(data, 0)

        # Should skip incomplete extension
        assert len(extensions) == 0

    def test_encode_extensions_empty(self):
        """Test encoding empty extension list."""
        data = encode_extensions([])
        assert data == b"\x00"

    def test_encode_extensions_single(self):
        """Test encoding single extension."""
        ext = WindowScalingExtension(scale_factor=2)
        data = encode_extensions([ext])

        # Should be: type(1) + length(1) + data(1)
        assert len(data) == 3
        assert data[0] == UTPExtensionType.WINDOW_SCALING
        assert data[1] == 1
        assert data[2] == 2

    def test_encode_extensions_multiple(self):
        """Test encoding multiple extensions."""
        extensions = [
            WindowScalingExtension(scale_factor=2),
            SACKExtension(blocks=[SACKBlock(start_seq=100, end_seq=105)]),
        ]
        data = encode_extensions(extensions)

        # Should contain both extensions
        assert len(data) > 0
        extensions_back, _ = parse_extensions(data, 0)
        assert len(extensions_back) == 2

    def test_parse_encode_roundtrip(self):
        """Test roundtrip: encode then parse."""
        original = [
            WindowScalingExtension(scale_factor=3),
            SACKExtension(blocks=[SACKBlock(start_seq=200, end_seq=210)]),
            ECNExtension(ecn_echo=True, ecn_cwr=False),
        ]

        encoded = encode_extensions(original)
        parsed, _ = parse_extensions(encoded, 0)

        assert len(parsed) == 3
        assert isinstance(parsed[0], WindowScalingExtension)
        assert parsed[0].scale_factor == 3
        assert isinstance(parsed[1], SACKExtension)
        assert parsed[1].blocks[0].start_seq == 200
        assert isinstance(parsed[2], ECNExtension)
        assert parsed[2].ecn_echo is True

