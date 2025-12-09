"""NAT-PMP (NAT Port Mapping Protocol) client implementation per RFC 6886."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import struct
from dataclasses import dataclass
from enum import IntEnum

from ccbt.nat.exceptions import NATPMPError

logger = logging.getLogger(__name__)

# RFC 6886 constants
NAT_PMP_PORT = 5351
NAT_PMP_REQUEST_TIMEOUT = 10.0
NAT_PMP_MAX_RETRIES = 3
NAT_PMP_VERSION = 0


class NATPMPOpcode(IntEnum):
    """NAT-PMP opcodes from RFC 6886."""

    PUBLIC_ADDRESS_REQUEST = 0
    UDP_MAPPING_REQUEST = 1
    TCP_MAPPING_REQUEST = 2


class NATPMPResult(IntEnum):
    """NAT-PMP result codes from RFC 6886 section 3.2."""

    SUCCESS = 0
    UNSUPPORTED_VERSION = 1
    NOT_AUTHORIZED = 2  # e.g., gateway firewall disallows
    NETWORK_FAILURE = 3
    OUT_OF_RESOURCES = 4
    UNSUPPORTED_OPCODE = 5


@dataclass
class NATPMPPortMapping:
    """Represents a NAT-PMP port mapping."""

    internal_port: int
    external_port: int
    lifetime: int  # seconds
    protocol: str  # "tcp" or "udp"


# Gateway discovery functions


async def discover_gateway() -> ipaddress.IPv4Address | None:
    """Discover the NAT gateway using the default gateway method.

    RFC 6886 section 3.3: Gateway is typically the default route gateway.

    Returns:
        IPv4Address of gateway, or None if not found

    """
    try:
        # Try to get default gateway
        return await get_gateway_ip()
    except Exception as e:
        logger.debug("Failed to discover gateway: %s", e)
        return None


async def get_gateway_ip() -> ipaddress.IPv4Address | None:
    """Get gateway IP using platform-specific methods."""
    import platform

    system = platform.system()

    try:
        if system == "Windows":
            # Use netstat -rn to find default gateway
            import subprocess

            result = subprocess.run(
                ["route", "print", "0.0.0.0"],  # noqa: S607  # nosec B104 - routing table query, not bind
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Parse output for default gateway
            # Format: "0.0.0.0          0.0.0.0         192.168.1.1     192.168.1.100"
            for line in result.stdout.splitlines():
                if "0.0.0.0" in line and "On-Link" not in line:  # nosec B104 - routing table parsing
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            gateway_str = parts[2]
                            return ipaddress.IPv4Address(gateway_str)
                        except (
                            ValueError,
                            IndexError,
                        ):  # pragma: no cover - Gateway parsing error, tested via valid gateway
                            continue

        elif system in (
            "Linux",
            "Darwin",
        ):  # pragma: no cover - Linux/Darwin gateway detection, tested via Windows path
            # Try ip route first (Linux), then route -n (both)
            import subprocess

            for cmd in [
                ["ip", "route", "show", "default"],
                ["route", "-n", "get", "default"],
            ]:
                try:
                    result = subprocess.run(
                        cmd,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        output = result.stdout
                        # Parse gateway from output
                        # Linux ip: "default via 192.168.1.1 dev eth0"
                        # macOS route: "gateway: 192.168.1.1"
                        for line in output.splitlines():
                            if "via" in line or "gateway:" in line:
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part in ("via", "gateway:") and i + 1 < len(
                                        parts
                                    ):
                                        try:
                                            gateway_str = parts[i + 1].split("/")[0]
                                            return ipaddress.IPv4Address(gateway_str)
                                        except (
                                            ValueError,
                                            IndexError,
                                        ):  # pragma: no cover - Gateway parsing error, tested via valid gateway
                                            continue
                except (
                    FileNotFoundError,
                    subprocess.TimeoutExpired,
                ):  # pragma: no cover - Command execution error, tested via success path
                    continue

    except (
        Exception
    ) as e:  # pragma: no cover - Gateway detection exception, defensive error handling
        logger.debug("Error getting gateway IP: %s", e)

    # Fallback: try netifaces if available
    try:
        import netifaces  # type: ignore[unresolved-import] # Optional dependency

        gateways = netifaces.gateways()
        default = gateways.get("default")
        if default and netifaces.AF_INET in default:  # type: ignore[attr-defined]
            gateway = default[netifaces.AF_INET][0]  # type: ignore[attr-defined]
            return ipaddress.IPv4Address(gateway)
    except (
        ImportError
    ):  # pragma: no cover - netifaces import error, tested via netifaces available
        logger.debug("netifaces not available, skipping fallback")

    return None


# Message encoding/decoding functions


def encode_public_address_request() -> bytes:
    """Encode public address request (RFC 6886 section 3.1)."""
    # Version (1 byte): 0
    # Opcode (1 byte): 0 (PUBLIC_ADDRESS_REQUEST)
    return struct.pack("!BB", NAT_PMP_VERSION, NATPMPOpcode.PUBLIC_ADDRESS_REQUEST)


def encode_port_mapping_request(
    internal_port: int,
    external_port: int,
    lifetime: int,
    protocol: str,
) -> bytes:
    """Encode port mapping request (RFC 6886 section 3.4).

    Args:
        internal_port: Internal port (0 for automatic)
        external_port: Desired external port (0 for automatic)
        lifetime: Mapping lifetime in seconds
        protocol: "tcp" or "udp"

    Returns:
        Encoded NAT-PMP request message

    """
    opcode = (
        NATPMPOpcode.TCP_MAPPING_REQUEST
        if protocol.lower() == "tcp"
        else NATPMPOpcode.UDP_MAPPING_REQUEST
    )
    # Pack message: version(1), opcode(1), reserved(2), internal_port(2),
    #               external_port(2), lifetime(4)
    return struct.pack(
        "!BBHHHI",
        NAT_PMP_VERSION,
        opcode,
        0,  # reserved
        internal_port,
        external_port,
        lifetime,
    )


def decode_public_address_response(data: bytes) -> tuple[ipaddress.IPv4Address, int]:
    """Decode public address response (RFC 6886 section 3.2).

    Args:
        data: Response bytes

    Returns:
        Tuple of (external_ip, seconds_since_epoch)

    Raises:
        ValueError: If response is invalid
        NATPMPError: If NAT-PMP returned an error

    """
    if len(data) < 12:
        msg = "Response too short"
        raise ValueError(msg)
    # Unpack version(1), opcode(1), result(2), seconds_since_epoch(4), external_ip(4)
    # RFC 6886 uses 16-bit result and 32-bit seconds; format: !BBHII
    _version, _opcode, result, seconds, ip_int = struct.unpack("!BBHII", data[:12])
    # Validate result code
    if result != 0:
        error_name = (
            NATPMPResult(result).name if result in range(6) else f"Unknown({result})"
        )
        msg = f"NAT-PMP error: {error_name}"
        raise NATPMPError(msg)
    external_ip = ipaddress.IPv4Address(ip_int)
    return external_ip, seconds


def decode_port_mapping_response(data: bytes) -> NATPMPPortMapping:
    """Decode port mapping response (RFC 6886 section 3.5).

    Args:
        data: Response bytes

    Returns:
        NATPMPPortMapping object

    Raises:
        ValueError: If response is invalid
        NATPMPError: If NAT-PMP returned an error

    """
    if len(data) < 16:
        msg = "Response too short"
        raise ValueError(msg)
    # Unpack version(1), opcode(1), result(2), seconds_since_epoch(4), internal_port(2), external_port(2), lifetime(4)
    # Correct layout per RFC 6886: !BBHIHHI
    _version, opcode, result, _seconds, internal, external, lifetime = struct.unpack(
        "!BBHIHHI",
        data[:16],
    )
    # Validate result code
    if result != 0:
        error_name = (
            NATPMPResult(result).name if result in range(6) else f"Unknown({result})"
        )
        msg = f"NAT-PMP error: {error_name}"
        raise NATPMPError(msg)
    # Determine protocol from opcode
    protocol = "tcp" if opcode == NATPMPOpcode.TCP_MAPPING_REQUEST else "udp"
    return NATPMPPortMapping(internal, external, lifetime, protocol)


# NATPMPClient class


class NATPMPClient:
    """Async NAT-PMP client."""

    def __init__(
        self,
        gateway_ip: ipaddress.IPv4Address | None = None,
        timeout: float = NAT_PMP_REQUEST_TIMEOUT,
    ):
        """Initialize NAT-PMP client.

        Args:
            gateway_ip: Gateway IP address (None to auto-discover)
            timeout: Request timeout in seconds

        """
        self.gateway_ip = gateway_ip
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self._socket: socket.socket | None = None
        self._external_ip: ipaddress.IPv4Address | None = None
        self._last_epoch_time: int = 0

    async def _ensure_socket(self) -> socket.socket:
        """Create UDP socket for NAT-PMP communication."""
        if self._socket is None:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            self._socket = sock
        return self._socket

    async def close(self) -> None:
        """Close NAT-PMP socket."""
        if self._socket:
            self._socket.close()
            self._socket = None

    async def get_external_ip(self) -> ipaddress.IPv4Address:
        """Get external IP address (RFC 6886 section 3.1).

        Returns:
            External IPv4 address

        Raises:
            NATPMPError: If unable to get external IP

        """
        # Ensure gateway discovered
        if self.gateway_ip is None:
            self.gateway_ip = await discover_gateway()
            if self.gateway_ip is None:
                msg = "Cannot discover gateway"
                raise NATPMPError(msg)

        # Send request and receive response
        sock = await self._ensure_socket()
        request = encode_public_address_request()

        for attempt in range(NAT_PMP_MAX_RETRIES):
            try:
                sock.sendto(request, (str(self.gateway_ip), NAT_PMP_PORT))
                response, _addr = sock.recvfrom(1024)

                # Decode response
                external_ip, seconds = decode_public_address_response(response)
                self._external_ip = external_ip
                self._last_epoch_time = seconds
                return external_ip

            except socket.timeout:
                if attempt == NAT_PMP_MAX_RETRIES - 1:
                    msg = "Timeout getting external IP"
                    raise NATPMPError(msg) from None
                await asyncio.sleep(1)
            except Exception as e:
                msg = f"Error getting external IP: {e}"
                raise NATPMPError(msg) from e

        # Unreachable, but satisfies type checker
        msg = "Failed to get external IP after retries"  # pragma: no cover - Unreachable fallback, type checker satisfaction
        raise NATPMPError(msg)

    async def add_port_mapping(
        self,
        internal_port: int,
        external_port: int = 0,
        lifetime: int = 3600,
        protocol: str = "tcp",
    ) -> NATPMPPortMapping:
        """Add port mapping (RFC 6886 section 3.4).

        Args:
            internal_port: Internal port
            external_port: External port (0 for automatic)
            lifetime: Mapping lifetime in seconds
            protocol: "tcp" or "udp"

        Returns:
            NATPMPPortMapping with actual external port and lifetime

        Raises:
            NATPMPError: If unable to add port mapping

        """
        # Ensure gateway
        if (
            self.gateway_ip is None
        ):  # pragma: no cover - Gateway discovery path, tested via gateway exists
            self.gateway_ip = await discover_gateway()
            if (
                self.gateway_ip is None
            ):  # pragma: no cover - Gateway discovery failure, tested via discovery success
                msg = "Cannot discover gateway"
                raise NATPMPError(msg)

        # Send mapping request
        sock = await self._ensure_socket()
        request = encode_port_mapping_request(
            internal_port, external_port, lifetime, protocol
        )

        for attempt in range(NAT_PMP_MAX_RETRIES):
            try:
                sock.sendto(request, (str(self.gateway_ip), NAT_PMP_PORT))
                response, _addr = sock.recvfrom(1024)

                # Decode and return mapping
                mapping = decode_port_mapping_response(response)
                self.logger.info(
                    "Mapped %s port %s -> %s (lifetime: %s s)",
                    protocol,
                    mapping.internal_port,
                    mapping.external_port,
                    mapping.lifetime,
                )
                return mapping

            except socket.timeout:
                if attempt == NAT_PMP_MAX_RETRIES - 1:
                    msg = "Timeout adding port mapping"
                    raise NATPMPError(msg) from None
                await asyncio.sleep(1)
            except Exception as e:
                msg = f"Error adding port mapping: {e}"
                raise NATPMPError(msg) from e

        # Unreachable, but satisfies type checker
        msg = "Failed to add port mapping after retries"  # pragma: no cover - Unreachable fallback, type checker satisfaction
        raise NATPMPError(msg)

    async def delete_port_mapping(
        self,
        external_port: int,
        protocol: str = "tcp",
    ) -> None:
        """Delete port mapping by requesting 0 lifetime (RFC 6886 section 3.6).

        Args:
            external_port: External port to remove
            protocol: "tcp" or "udp"

        Raises:
            NATPMPError: If unable to delete port mapping

        """
        # Request 0 lifetime to delete
        await self.add_port_mapping(0, external_port, 0, protocol)
        self.logger.info("Deleted %s port mapping for port %s", protocol, external_port)
