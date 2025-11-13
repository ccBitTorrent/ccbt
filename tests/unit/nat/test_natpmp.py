"""Unit tests for NAT-PMP client."""

from __future__ import annotations

import asyncio
import ipaddress
import struct
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.nat.exceptions import NATPMPError
from ccbt.nat.natpmp import (
    NATPMPClient,
    NATPMPOpcode,
    NATPMPPortMapping,
    NATPMPResult,
    decode_port_mapping_response,
    decode_public_address_response,
    discover_gateway,
    encode_port_mapping_request,
    encode_public_address_request,
)


@pytest.mark.asyncio
async def test_discover_gateway_success():
    """Test successful gateway discovery."""
    with patch("ccbt.nat.natpmp.get_gateway_ip", new_callable=AsyncMock) as mock_gateway:
        mock_gateway.return_value = ipaddress.IPv4Address("192.168.1.1")

        result = await discover_gateway()

        assert result == ipaddress.IPv4Address("192.168.1.1")


@pytest.mark.asyncio
async def test_discover_gateway_failure():
    """Test gateway discovery failure."""
    with patch("ccbt.nat.natpmp.get_gateway_ip", new_callable=AsyncMock) as mock_gateway:
        mock_gateway.side_effect = Exception("Failed")

        result = await discover_gateway()

        assert result is None


def test_encode_public_address_request():
    """Test encoding public address request."""
    data = encode_public_address_request()

    assert len(data) == 2
    version, opcode = struct.unpack("!BB", data)
    assert version == 0  # NAT_PMP_VERSION
    assert opcode == NATPMPOpcode.PUBLIC_ADDRESS_REQUEST.value


def test_encode_port_mapping_request():
    """Test encoding port mapping request."""
    data = encode_port_mapping_request(6881, 6881, 3600, "tcp")

    assert len(data) == 12
    # Format: version(1), opcode(1), reserved(2), internal(2), external(2), lifetime(4)
    # !BBHHHI = B(1) + B(1) + H(2) + H(2) + H(2) + I(4) = 12 bytes
    version, opcode, reserved, internal, external, lifetime = struct.unpack(
        "!BBHHHI", data
    )
    assert version == 0
    assert opcode == NATPMPOpcode.TCP_MAPPING_REQUEST.value
    assert internal == 6881
    assert external == 6881
    assert lifetime == 3600


def test_encode_port_mapping_request_udp():
    """Test encoding UDP port mapping request."""
    data = encode_port_mapping_request(6882, 6882, 1800, "udp")

    assert len(data) == 12
    version, opcode, reserved, internal, external, lifetime = struct.unpack(
        "!BBHHHI", data
    )
    assert opcode == NATPMPOpcode.UDP_MAPPING_REQUEST.value


def test_decode_public_address_response_success():
    """Test decoding successful public address response."""
    ip = ipaddress.IPv4Address("192.168.1.1")
    seconds = 1234567890  # Unix timestamp

    # Encode response: !BBHII = version(1), opcode(1), result(2), seconds(4), ip(4)
    data = struct.pack(
        "!BBHII",
        0,  # version
        NATPMPOpcode.PUBLIC_ADDRESS_REQUEST.value,  # opcode
        NATPMPResult.SUCCESS.value,  # result (2 bytes = H)
        seconds,  # seconds since epoch (4 bytes = I)
        int(ip),  # external IP (4 bytes = I)
    )

    result_ip, result_seconds = decode_public_address_response(data)

    assert result_ip == ip
    assert result_seconds == seconds


def test_decode_public_address_response_too_short():
    """Test decoding response that's too short."""
    data = b"\x00\x00"

    with pytest.raises(ValueError, match="too short"):
        decode_public_address_response(data)


def test_decode_public_address_response_error():
    """Test decoding response with error code."""
    data = struct.pack(
        "!BBHII",
        0,
        NATPMPOpcode.PUBLIC_ADDRESS_REQUEST.value,
        NATPMPResult.NOT_AUTHORIZED.value,  # Error
        0,
        0,
    )

    with pytest.raises(NATPMPError):
        decode_public_address_response(data)


def test_decode_port_mapping_response_success():
    """Test decoding successful port mapping response."""
    internal = 6881
    external = 6881
    lifetime = 3600

    # Encode response for TCP: !BBHIHHI format
    # version(1), opcode(1), result(2), seconds(4), internal(2), external(2), lifetime(4)
    data = struct.pack(
        "!BBHIHHI",
        0,  # version
        NATPMPOpcode.TCP_MAPPING_REQUEST.value,  # opcode
        NATPMPResult.SUCCESS.value,  # result
        0,  # seconds (not used in mapping response)
        internal,
        external,
        lifetime,
    )

    result = decode_port_mapping_response(data)

    assert isinstance(result, NATPMPPortMapping)
    assert result.internal_port == internal
    assert result.external_port == external
    assert result.lifetime == lifetime
    assert result.protocol == "tcp"


def test_decode_port_mapping_response_udp():
    """Test decoding UDP port mapping response."""
    # Format: version(1), opcode(1), result(2), seconds(4), internal(2), external(2), lifetime(4)
    data = struct.pack(
        "!BBHIHHI",
        0,
        NATPMPOpcode.UDP_MAPPING_REQUEST.value,
        NATPMPResult.SUCCESS.value,
        0,
        6882,
        6882,
        1800,
    )

    result = decode_port_mapping_response(data)

    assert result.protocol == "udp"


def test_decode_port_mapping_response_error():
    """Test decoding port mapping response with error."""
    # Format: version(1), opcode(1), result(2), seconds(4), internal(2), external(2), lifetime(4)
    data = struct.pack(
        "!BBHIHHI",
        0,
        NATPMPOpcode.TCP_MAPPING_REQUEST.value,
        NATPMPResult.OUT_OF_RESOURCES.value,
        0,
        0,
        0,
        0,
    )

    with pytest.raises(NATPMPError):
        decode_port_mapping_response(data)


def test_decode_port_mapping_response_too_short():
    """Test decoding response that's too short."""
    data = b"\x00\x00\x00\x00"

    with pytest.raises(ValueError, match="too short"):
        decode_port_mapping_response(data)


@pytest.fixture
def natpmp_client():
    """Create NAT-PMP client instance."""
    return NATPMPClient()


@pytest.mark.asyncio
async def test_get_external_ip_success(natpmp_client):
    """Test successful external IP retrieval."""
    ip = ipaddress.IPv4Address("203.0.113.1")
    seconds = 1234567890
    gateway = ipaddress.IPv4Address("192.168.1.1")

    # Set gateway directly to avoid discovery
    natpmp_client.gateway_ip = gateway

    # Mock socket creation and operations
    mock_socket = MagicMock()
    response_data = struct.pack(
        "!BBHII",
        0,
        NATPMPOpcode.PUBLIC_ADDRESS_REQUEST.value,
        NATPMPResult.SUCCESS.value,
        seconds,
        int(ip),
    )

    mock_socket.sendto = Mock(return_value=12)
    mock_socket.recvfrom = Mock(return_value=(response_data, (str(gateway), 5351)))
    mock_socket.settimeout = Mock()

    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.to_thread") as mock_to_thread:
        # Mock to_thread to execute synchronously for testing
        call_count = 0
        async def sync_thread(fn, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # sendto
                return mock_socket.sendto(*args)
            elif call_count == 2:  # recvfrom
                return mock_socket.recvfrom(*args)

        mock_to_thread.side_effect = sync_thread

        result = await natpmp_client.get_external_ip()

        assert result is not None
        assert result == ip
        assert natpmp_client._external_ip == ip


@pytest.mark.asyncio
async def test_get_external_ip_gateway_failure(natpmp_client):
    """Test external IP retrieval when gateway discovery fails."""
    natpmp_client.gateway_ip = None  # Force discovery

    with patch("ccbt.nat.natpmp.discover_gateway", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = None  # Discovery fails

        with pytest.raises(NATPMPError, match="Cannot discover gateway"):
            await natpmp_client.get_external_ip()


@pytest.mark.asyncio
async def test_add_port_mapping_success(natpmp_client):
    """Test successful port mapping."""
    gateway = ipaddress.IPv4Address("192.168.1.1")
    natpmp_client.gateway_ip = gateway
    natpmp_client._external_ip = ipaddress.IPv4Address("203.0.113.1")

    # Mock socket
    mock_socket = MagicMock()
    response_data = struct.pack(
        "!BBHIHHI",
        0,
        NATPMPOpcode.TCP_MAPPING_REQUEST.value,
        NATPMPResult.SUCCESS.value,
        0,
        6881,
        6881,
        3600,
    )

    mock_socket.sendto = Mock(return_value=12)
    mock_socket.recvfrom = Mock(return_value=(response_data, (str(gateway), 5351)))
    mock_socket.settimeout = Mock()

    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.to_thread") as mock_to_thread:
        call_count = 0
        async def sync_thread(fn, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # sendto
                return mock_socket.sendto(*args)
            elif call_count == 2:  # recvfrom
                return mock_socket.recvfrom(*args)

        mock_to_thread.side_effect = sync_thread

        result = await natpmp_client.add_port_mapping(6881, 6881, 3600, "tcp")

        assert isinstance(result, NATPMPPortMapping)
        assert result.internal_port == 6881
        assert result.external_port == 6881


@pytest.mark.asyncio
async def test_add_port_mapping_error_response(natpmp_client):
    """Test port mapping with error response."""
    gateway = ipaddress.IPv4Address("192.168.1.1")
    natpmp_client.gateway_ip = gateway
    natpmp_client._external_ip = ipaddress.IPv4Address("203.0.113.1")

    mock_socket = MagicMock()
    error_response = struct.pack(
        "!BBHIHHI",
        0,
        NATPMPOpcode.TCP_MAPPING_REQUEST.value,
        NATPMPResult.OUT_OF_RESOURCES.value,
        0,
        0,
        0,
        0,
    )

    mock_socket.sendto = Mock(return_value=12)
    mock_socket.recvfrom = Mock(return_value=(error_response, (str(gateway), 5351)))
    mock_socket.settimeout = Mock()

    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.to_thread") as mock_to_thread:
        call_count = 0
        async def sync_thread(fn, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # sendto
                return mock_socket.sendto(*args)
            elif call_count == 2:  # recvfrom
                return mock_socket.recvfrom(*args)

        mock_to_thread.side_effect = sync_thread

        with pytest.raises(NATPMPError):
            await natpmp_client.add_port_mapping(6881, 6881, 3600, "tcp")


@pytest.mark.asyncio
async def test_delete_port_mapping(natpmp_client):
    """Test deleting port mapping."""
    gateway = ipaddress.IPv4Address("192.168.1.1")
    natpmp_client.gateway_ip = gateway

    mock_socket = MagicMock()
    delete_response = struct.pack(
        "!BBHIHHI",
        0,
        NATPMPOpcode.TCP_MAPPING_REQUEST.value,
        NATPMPResult.SUCCESS.value,
        0,
        6881,
        6881,
        0,  # Lifetime 0 for deletion
    )

    mock_socket.sendto = Mock(return_value=12)
    mock_socket.recvfrom = Mock(return_value=(delete_response, (str(gateway), 5351)))
    mock_socket.settimeout = Mock()

    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.to_thread") as mock_to_thread:
        call_count = 0
        async def sync_thread(fn, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # sendto
                return mock_socket.sendto(*args)
            elif call_count == 2:  # recvfrom
                return mock_socket.recvfrom(*args)

        mock_to_thread.side_effect = sync_thread

        # Should not raise
        await natpmp_client.delete_port_mapping(6881, "tcp")


@pytest.mark.asyncio
async def test_close(natpmp_client):
    """Test closing client."""
    # Create a socket to close
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        natpmp_client._socket = mock_socket

        await natpmp_client.close()

        mock_socket.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_no_socket(natpmp_client):
    """Test closing when no socket exists."""
    natpmp_client._socket = None

    # Should not raise
    await natpmp_client.close()

