"""UPnP IGD (Internet Gateway Device) client implementation."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import warnings
from urllib.parse import urljoin

try:
    import defusedxml.ElementTree as ET  # noqa: N817
except (
    ImportError
):  # pragma: no cover - defensive import fallback, tested via integration
    # Fallback for systems without defusedxml (should never happen as defusedxml is required)
    import xml.etree.ElementTree as ET  # nosec B405 - Fallback only, defusedxml is required dependency

    warnings.warn(  # pragma: no cover - defensive import fallback
        "defusedxml not installed. XML parsing may be vulnerable to attacks. "
        "Install with: pip install defusedxml",
        UserWarning,
        stacklevel=2,
    )

try:
    import aiohttp
except ImportError:  # pragma: no cover - defensive import fallback
    aiohttp = None  # type: ignore[assignment,misc]

from ccbt.nat.exceptions import UPnPError

logger = logging.getLogger(__name__)

# SSDP constants
SSDP_MULTICAST_IP = "239.255.255.250"
SSDP_MULTICAST_PORT = 1900
SSDP_MSEARCH_TIMEOUT = 5.0  # Increased from 3.0s for better reliability
SSDP_MSEARCH_RETRIES = 3

# UPnP IGD service constants
UPNP_IGD_SERVICE_TYPE = "urn:schemas-upnp-org:service:WANIPConnection:1"
UPNP_IGD2_SERVICE_TYPE = "urn:schemas-upnp-org:service:WANIPConnection:2"
UPNP_IGD_DEVICE_TYPE = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"


def build_msearch_request(search_target: str | None = None) -> bytes:
    """Build SSDP M-SEARCH request (UPnP Device Architecture 1.1).

    Args:
        search_target: ST (Search Target) header value. If None, uses UPNP_IGD_SERVICE_TYPE.

    Returns:
        M-SEARCH request bytes

    """
    if search_target is None:
        search_target = UPNP_IGD_SERVICE_TYPE

    # Build M-SEARCH message
    # CRITICAL FIX: MX (Maximum wait time) should be at least 1-5 seconds
    # Some routers need time to respond, so we use 3 seconds
    msg = (
        f"M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_MULTICAST_IP}:{SSDP_MULTICAST_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        f"ST: {search_target}\r\n"
        "\r\n"
    )
    return msg.encode("utf-8")


def parse_ssdp_response(response: bytes) -> dict[str, str]:
    """Parse SSDP response headers.

    Args:
        response: SSDP response bytes

    Returns:
        Dictionary of header fields

    """
    # Parse HTTP-style headers
    headers: dict[str, str] = {}
    lines = response.decode("utf-8", errors="ignore").split("\r\n")
    for line in lines[1:]:  # Skip status line
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return headers


async def discover_upnp_devices() -> list[dict[str, str]]:
    """Discover UPnP IGD devices via SSDP with retry logic.

    CRITICAL FIX: Uses asyncio for socket operations and properly joins multicast group.
    On Windows, multicast requires proper interface binding and group membership.

    Returns:
        List of device info dictionaries with 'location' URL

    """
    if not aiohttp:
        msg = "aiohttp is required for UPnP support. Install with: pip install aiohttp"
        raise UPnPError(msg)

    devices: list[dict[str, str]] = []
    seen_locations: set[str] = set()  # Cache clearing: track seen devices to avoid duplicates

    # CRITICAL FIX: Get local network interfaces for proper multicast binding
    import sys

    # Try to get local IP address for multicast interface binding
    local_ip = None
    try:
        # Get default gateway interface IP
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.connect(("8.8.8.8", 80))
        local_ip = test_sock.getsockname()[0]
        test_sock.close()
        logger.debug("Detected local IP for multicast: %s", local_ip)
    except Exception as e:
        logger.debug("Could not detect local IP for multicast: %s, using default", e)

    # Retry logic: send multiple M-SEARCH requests with delays
    for attempt in range(SSDP_MSEARCH_RETRIES):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # CRITICAL FIX: Windows-specific multicast configuration
            if sys.platform == "win32":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                # CRITICAL FIX: Set multicast TTL (required on Windows)
                # TTL of 2 allows packets to traverse one router hop (local network)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

                # CRITICAL FIX: Set multicast interface BEFORE binding
                # This tells Windows which interface to use for sending multicast
                if local_ip:
                    try:
                        interface_ip = socket.inet_aton(local_ip)
                        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, interface_ip)
                        logger.debug("Set multicast interface to %s", local_ip)
                    except OSError as e:
                        logger.debug("Failed to set multicast interface: %s", e)
                        # Continue - some systems don't require this

            # CRITICAL FIX: Bind to INADDR_ANY (0.0.0.0) to receive on all interfaces
            # Binding to specific port 0 lets OS choose ephemeral port
            # On Windows, binding to 0.0.0.0:0 is required for multicast
            try:
                sock.bind(("0.0.0.0", 0))  # nosec B104 - Multicast socket must bind to 0.0.0.0 for SSDP discovery
                logger.debug("Bound socket to 0.0.0.0:0 for multicast")
            except OSError as e:
                logger.debug("Failed to bind socket: %s", e)
                # Try binding to local IP if 0.0.0.0 fails
                if local_ip:
                    try:
                        sock.bind((local_ip, 0))
                        logger.debug("Bound socket to %s:0 for multicast", local_ip)
                    except OSError as e2:
                        logger.debug("Failed to bind to local IP: %s", e2)
                        raise

            # CRITICAL FIX: Join multicast group properly
            # IP_ADD_MEMBERSHIP is required to receive multicast packets
            multicast_ip = socket.inet_aton(SSDP_MULTICAST_IP)
            if local_ip:
                # Bind to specific interface if we detected it
                try:
                    interface_ip = socket.inet_aton(local_ip)
                    mreq = multicast_ip + interface_ip
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                    logger.debug("Joined SSDP multicast group %s on interface %s", SSDP_MULTICAST_IP, local_ip)
                except OSError as e:
                    logger.debug("Failed to join multicast group on %s: %s, trying INADDR_ANY", local_ip, e)
                    # Fallback to INADDR_ANY
                    mreq = multicast_ip + socket.inet_aton("0.0.0.0")  # nosec B104 - Multicast membership fallback to INADDR_ANY for SSDP
                    try:
                        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                        logger.debug("Joined SSDP multicast group %s on all interfaces", SSDP_MULTICAST_IP)
                    except OSError as e2:
                        logger.debug("Failed to join multicast group on all interfaces: %s", e2)
                        # Continue anyway - some systems don't require explicit membership
            else:
                # Use INADDR_ANY (0.0.0.0) to receive on all interfaces
                mreq = multicast_ip + socket.inet_aton("0.0.0.0")  # nosec B104 - Multicast membership uses INADDR_ANY for all interfaces
                try:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                    logger.debug("Joined SSDP multicast group %s on all interfaces", SSDP_MULTICAST_IP)
                except OSError as e:
                    logger.debug("Failed to join multicast group (may be normal): %s", e)
                    # Continue anyway - some systems don't require explicit membership

            multicast_addr = (SSDP_MULTICAST_IP, SSDP_MULTICAST_PORT)

            # CRITICAL FIX: Set socket to non-blocking BEFORE sending (required for asyncio)
            # This must be done after binding but before sending
            sock.setblocking(False)

            # CRITICAL FIX: Send M-SEARCH requests for both service type and device type
            # Some routers only respond to device type searches, not service type
            search_targets = [
                UPNP_IGD_SERVICE_TYPE,  # Try service type first
                UPNP_IGD_DEVICE_TYPE,   # Fallback to device type
                "ssdp:all",              # Last resort: search for all devices
            ]

            for search_idx, search_target in enumerate(search_targets):
                request = build_msearch_request(search_target)
                try:
                    # Use asyncio for non-blocking sendto on Windows
                    bytes_sent = await asyncio.get_event_loop().sock_sendto(sock, request, multicast_addr)
                    logger.debug(
                        "Sent M-SEARCH request (attempt %d/%d, target %d/%d: %s): %d bytes to %s:%d",
                        attempt + 1,
                        SSDP_MSEARCH_RETRIES,
                        search_idx + 1,
                        len(search_targets),
                        search_target[:50],
                        bytes_sent,
                        SSDP_MULTICAST_IP,
                        SSDP_MULTICAST_PORT,
                    )
                    # Small delay between different search targets
                    if search_idx < len(search_targets) - 1:
                        await asyncio.sleep(0.2)
                except Exception as e:
                    logger.debug("Failed to send M-SEARCH request for %s: %s", search_target, e)

            # CRITICAL FIX: Wait a bit after sending before listening for responses
            # Routers need time to process M-SEARCH and send responses
            # MX header says 3 seconds, so wait at least 0.5s before checking
            await asyncio.sleep(0.5)

            # CRITICAL FIX: Use asyncio for non-blocking socket operations
            # Socket is already set to non-blocking above
            start_time = asyncio.get_event_loop().time()
            responses_received = 0
            timeout_remaining = SSDP_MSEARCH_TIMEOUT - 0.5  # Account for initial delay

            # Receive responses with timeout
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout_remaining:
                    break

                try:
                    # Use asyncio.wait_for to handle timeout properly
                    remaining_time = timeout_remaining - elapsed
                    if remaining_time <= 0:
                        break
                    data, addr = await asyncio.wait_for(
                        asyncio.get_event_loop().sock_recvfrom(sock, 4096),
                        timeout=min(remaining_time, 1.0),  # Check every 1s
                    )
                    responses_received += 1
                    logger.debug(
                        "Received SSDP response from %s:%d (%d bytes)",
                        addr[0],
                        addr[1],
                        len(data),
                    )

                    headers = parse_ssdp_response(data)
                    logger.debug("SSDP response headers: %s", list(headers.keys()))

                    # Check if IGD device
                    st = headers.get("st", "")
                    nt = headers.get("nt", "")
                    location = headers.get("location", "")

                    logger.debug(
                        "SSDP response: ST=%s, NT=%s, Location=%s",
                        st[:100] if st else "(empty)",
                        nt[:100] if nt else "(empty)",
                        location[:100] if location else "(empty)",
                    )

                    # CRITICAL FIX: Check multiple UPnP service types
                    is_igd = (
                        UPNP_IGD_SERVICE_TYPE in st
                        or UPNP_IGD_DEVICE_TYPE in nt
                        or UPNP_IGD_SERVICE_TYPE in nt
                        or "InternetGatewayDevice" in st
                        or "WANIPConnection" in st
                        or "WANIPConnection" in nt
                    )

                    if is_igd:
                        if location and location not in seen_locations:
                            seen_locations.add(location)
                            devices.append(
                                {
                                    "location": location,
                                    "server": headers.get("server", ""),
                                    "usn": headers.get("usn", ""),
                                }
                            )
                            logger.info(
                                "Found UPnP IGD device: %s (server: %s)",
                                location,
                                headers.get("server", "unknown"),
                            )
                        else:
                            logger.debug("Skipping duplicate device location: %s", location)
                    else:
                        logger.debug(
                            "SSDP response is not IGD device (ST=%s, NT=%s)",
                            st[:50] if st else "(empty)",
                            nt[:50] if nt else "(empty)",
                        )
                except asyncio.TimeoutError:
                    # Timeout waiting for response - continue checking
                    continue
                except Exception as e:
                    logger.debug("Error receiving SSDP response: %s", e)
                    continue

            if responses_received == 0:
                logger.debug(
                    "No SSDP responses received in attempt %d/%d (timeout: %.1fs)",
                    attempt + 1,
                    SSDP_MSEARCH_RETRIES,
                    SSDP_MSEARCH_TIMEOUT,
                )
            else:
                logger.debug(
                    "Received %d SSDP response(s) in attempt %d/%d",
                    responses_received,
                    attempt + 1,
                    SSDP_MSEARCH_RETRIES,
                )

        except Exception as e:
            logger.debug(
                "SSDP discovery attempt %d/%d failed: %s",
                attempt + 1,
                SSDP_MSEARCH_RETRIES,
                e,
                exc_info=True,
            )
        finally:
            if sock:
                try:
                    # Leave multicast group
                    if local_ip:
                        try:
                            interface_ip = socket.inet_aton(local_ip)
                            mreq = socket.inet_aton(SSDP_MULTICAST_IP) + interface_ip
                            sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                        except Exception:
                            pass
                    sock.close()
                except Exception:
                    pass

        # If we found devices, no need to retry
        if devices:
            logger.info("UPnP discovery successful: found %d device(s)", len(devices))
            break

        # Wait before retry (exponential backoff: 0.5s, 1.0s)
        if attempt < SSDP_MSEARCH_RETRIES - 1:
            wait_time = 0.5 * (attempt + 1)
            logger.debug("Waiting %.1fs before retry...", wait_time)
            await asyncio.sleep(wait_time)

    if not devices:
        logger.warning(
            "UPnP discovery failed: no IGD devices found after %d attempts. "
            "Check that UPnP is enabled on your router and firewall allows multicast.",
            SSDP_MSEARCH_RETRIES,
        )

    return devices


async def fetch_device_description(location_url: str) -> dict[str, str]:
    """Fetch and parse UPnP device description XML with improved error handling.

    Args:
        location_url: Device description URL

    Returns:
        Dictionary with service URLs and control URLs

    Raises:
        UPnPError: If unable to fetch or parse device description

    """
    if not aiohttp:
        msg = "aiohttp is required for UPnP support. Install with: pip install aiohttp"
        raise UPnPError(msg)

    # Improved error handling with retries for device description fetching
    max_retries = 2
    last_error: Exception | None = None
    xml_content: str | None = None

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session, session.get(
                location_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    msg = f"Failed to fetch device description: HTTP {response.status}"
                    last_error = UPnPError(msg)
                    if attempt < max_retries - 1:
                        logger.debug(
                            "Device description fetch failed (attempt %d/%d): %s, retrying...",
                            attempt + 1,
                            max_retries,
                            msg,
                        )
                        await asyncio.sleep(0.5)
                        continue
                    raise last_error
                xml_content = await response.text()
                break
        except asyncio.TimeoutError as e:
            last_error = UPnPError(f"Timeout fetching device description: {e}")
            if attempt < max_retries - 1:
                logger.debug(
                    "Device description fetch timeout (attempt %d/%d), retrying...",
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(0.5)
                continue
            raise last_error from e
        except aiohttp.ClientError as e:
            last_error = UPnPError(f"Network error fetching device description: {e}")
            if attempt < max_retries - 1:
                logger.debug(
                    "Device description fetch network error (attempt %d/%d): %s, retrying...",
                    attempt + 1,
                    max_retries,
                    e,
                )
                await asyncio.sleep(0.5)
                continue
            raise last_error from e

    if xml_content is None:
        # All retries exhausted
        if last_error:
            raise last_error
        raise UPnPError("Failed to fetch device description after retries")

    # Parse XML (UPnP device description from trusted local network)
    # Uses defusedxml.ElementTree for secure parsing (imported above)
    try:
        root = ET.fromstring(xml_content)  # noqa: S314  # nosec B314 - defusedxml.ElementTree.fromstring

        # Extract IGD service info
        # Find deviceType = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
        # Navigate to serviceList -> service with serviceType containing "WANIPConnection"
        # Extract controlURL, eventSubURL, SCPDURL

        service_info: dict[str, str] = {}

        # Define namespace
        ns = {
            "device": "urn:schemas-upnp-org:device-1-0",
            "service": "urn:schemas-upnp-org:service-1-0",
        }

        # Find IGD service - look for WANIPConnection service
        services = root.findall(".//device:service", ns)
        for service in services:
            service_type_elem = service.find("device:serviceType", ns)
            if service_type_elem is not None:
                service_type = service_type_elem.text or ""
                if "WANIPConnection" in service_type:
                    control_url_elem = service.find("device:controlURL", ns)
                    if control_url_elem is not None and control_url_elem.text:
                        control_url = urljoin(location_url, control_url_elem.text)
                        service_info["control_url"] = control_url
                        service_info["service_type"] = service_type
                        break

        if not service_info:
            msg = "No WANIPConnection service found in device description"
            raise UPnPError(msg)

        return service_info
    except ET.ParseError as e:
        msg = f"Failed to parse device description XML: {e}"
        raise UPnPError(msg) from e
    except Exception as e:
        msg = f"Error fetching device description: {e}"
        raise UPnPError(msg) from e


def build_soap_action(
    action_name: str,
    service_type: str,
    parameters: dict[str, str],
) -> str:
    """Build SOAP action request body.

    Args:
        action_name: SOAP action name (e.g., "AddPortMapping")
        service_type: UPnP service type
        parameters: Action parameters

    Returns:
        SOAP request XML string

    """
    # Build SOAP envelope
    param_xml = "\n".join(
        f"    <{key}>{value}</{key}>" for key, value in parameters.items()
    )

    return f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action_name} xmlns:u="{service_type}">
{param_xml}
    </u:{action_name}>
  </s:Body>
</s:Envelope>"""


async def send_soap_action(
    control_url: str,
    action_name: str,
    service_type: str,
    parameters: dict[str, str],
) -> dict[str, str]:
    """Send SOAP action request and parse response.

    Args:
        control_url: Control URL for the service
        action_name: SOAP action name
        service_type: UPnP service type
        parameters: Action parameters

    Returns:
        Dictionary of response parameters

    Raises:
        UPnPError: If SOAP action fails

    """
    if not aiohttp:
        msg = "aiohttp is required for UPnP support. Install with: pip install aiohttp"
        raise UPnPError(msg)

    soap_body = build_soap_action(action_name, service_type, parameters)

    headers = {
        "Content-Type": 'text/xml; charset="utf-8"',
        "SOAPAction": f'"{service_type}#{action_name}"',
    }

    try:
        async with aiohttp.ClientSession() as session, session.post(
            control_url,
            data=soap_body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            response_xml = await resp.text()
            http_status = resp.status

        # Parse SOAP response (from trusted local network UPnP device)
        # Uses defusedxml.ElementTree for secure parsing (imported above)
        # Even on HTTP 500, the response body may contain useful SOAP fault information
        try:
            root = ET.fromstring(response_xml)  # noqa: S314  # nosec B314 - defusedxml.ElementTree.fromstring
        except ET.ParseError as e:
            # If we can't parse XML and status is not 200, raise HTTP error
            if http_status != 200:
                msg = f"SOAP action failed: HTTP {http_status} (response not parseable as XML)"
                raise UPnPError(msg) from e
            raise

        # Extract response parameters
        response_params: dict[str, str] = {}
        ns = {"soap": "http://schemas.xmlsoap.org/soap/envelope/"}
        body = root.find(".//soap:Body", ns)
        if body is not None:
            # Find the response element
            for elem in body:
                if elem.tag.endswith("Response"):
                    for child in elem:
                        # Remove namespace prefix
                        tag_name = (
                            child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        )
                        response_params[tag_name] = child.text or ""
                    break

        # Check for SOAP faults (even on HTTP 200, SOAP can have faults)
        fault = root.find(".//soap:Fault", ns)
        if fault is not None:
            fault_code_elem = fault.find("faultcode")
            fault_string_elem = fault.find("faultstring")
            fault_code = (
                fault_code_elem.text if fault_code_elem is not None else "Unknown"
            )
            fault_string = (
                fault_string_elem.text
                if fault_string_elem is not None
                else "Unknown error"
            )
            # Try to extract error code from detail section
            detail_elem = fault.find("detail")
            error_code = None
            error_description = None
            if detail_elem is not None:
                # Look for UPnP errorCode element (may be in different namespaces)
                # Try without namespace first
                error_code_elem = detail_elem.find(".//errorCode")
                if error_code_elem is None:
                    # Try with UPnP namespace
                    upnp_ns = {"upnp": "urn:schemas-upnp-org:control-1-0"}
                    error_code_elem = detail_elem.find(".//upnp:errorCode", upnp_ns)
                if error_code_elem is not None:
                    error_code = error_code_elem.text

                # Look for errorDescription
                error_desc_elem = detail_elem.find(".//errorDescription")
                if error_desc_elem is None:
                    upnp_ns = {"upnp": "urn:schemas-upnp-org:control-1-0"}
                    error_desc_elem = detail_elem.find(
                        ".//upnp:errorDescription", upnp_ns
                    )
                if error_desc_elem is not None:
                    error_description = error_desc_elem.text

                # Log full detail section for debugging
                detail_text = ET.tostring(detail_elem, encoding="unicode")
                logger.debug("UPnP SOAP fault detail section: %s", detail_text[:500])

            # Log full SOAP response for debugging
            logger.debug(
                "UPnP SOAP fault response (HTTP %d): %s",
                http_status,
                response_xml[:1000] if len(response_xml) > 1000 else response_xml,
            )

            # Build error message with UPnP error code interpretation
            if error_code:
                # Map common UPnP error codes to user-friendly messages
                error_code_map = {
                    "402": "Invalid Args - Check parameter formats",
                    "501": "Action Failed - Router rejected the request",
                    "714": "NoSuchEntryInArray - Port mapping not found (may already exist)",
                    "715": "WildCardNotPermittedInSrcIP - Invalid remote host parameter",
                    "716": "WildCardNotPermittedInExtPort - Invalid external port",
                    "718": "ConflictInMappingEntry - Port mapping conflict (port may be in use)",
                    "724": "SamePortValuesRequired - Internal and external ports must match for this router",
                    "725": "OnlyPermanentLeasesSupported - Router only supports permanent mappings",
                    "726": "RemoteHostOnlySupportsWildcard - Remote host must be empty",
                }
                error_hint = error_code_map.get(error_code, "")
                msg = (
                    f"SOAP fault: {fault_code} - {fault_string} "
                    f"(UPnP error code: {error_code}"
                    + (
                        f", description: {error_description}"
                        if error_description
                        else ""
                    )
                    + (f", hint: {error_hint}" if error_hint else "")
                    + ")"
                )
            else:
                msg = f"SOAP fault: {fault_code} - {fault_string}"
            raise UPnPError(msg)

        # Check HTTP status after parsing SOAP (some routers return HTTP 500 with valid SOAP faults)
        if http_status != 200:
            # If we got here, there's no SOAP fault but HTTP status is not 200
            # This is unusual - log the response for debugging
            logger.debug(
                "UPnP SOAP action returned HTTP %d but no SOAP fault. Response: %s",
                http_status,
                response_xml[:500] if len(response_xml) > 500 else response_xml,
            )
            msg = f"SOAP action failed: HTTP {http_status}"
            raise UPnPError(msg)

        return response_params
    except ET.ParseError as e:
        msg = f"Failed to parse SOAP response: {e}"
        raise UPnPError(msg) from e
    except Exception as e:
        msg = f"Error sending SOAP action: {e}"
        raise UPnPError(msg) from e


# UPnPClient class


class UPnPClient:
    """Async UPnP IGD client."""

    def __init__(self, device_url: str | None = None):
        """Initialize UPnP client.

        Args:
            device_url: Device description URL (None to auto-discover)

        """
        self.device_url = device_url
        self.control_url: str | None = None
        self.service_type: str = UPNP_IGD_SERVICE_TYPE
        self.logger = logging.getLogger(__name__)

    def clear_cache(self) -> None:
        """Clear cached device URL and control URL to force re-discovery.

        This is useful when the router's UPnP service may have changed
        or when stale device URLs are causing discovery failures.
        """
        self.device_url = None
        self.control_url = None
        self.logger.debug("Cleared UPnP client cache (device_url and control_url)")

    async def discover(self) -> bool:
        """Discover UPnP IGD device and initialize control URL.

        Returns:
            True if discovery successful, False otherwise

        """
        if self.device_url is None:
            devices = await discover_upnp_devices()
            if not devices:
                return False
            self.device_url = devices[0]["location"]

        service_info = await fetch_device_description(self.device_url)
        control_url = service_info.get("control_url")
        if not control_url:
            return False

        self.control_url = control_url
        self.service_type = service_info.get("service_type", UPNP_IGD_SERVICE_TYPE)
        return True

    async def get_external_ip(self) -> ipaddress.IPv4Address:
        """Get external IP address.

        Returns:
            External IPv4 address

        Raises:
            UPnPError: If unable to get external IP

        """
        if not self.control_url:
            discovered = await self.discover()
            if not discovered:
                msg = "Failed to discover UPnP device"
                raise UPnPError(msg)

        if not self.control_url:
            msg = "Control URL not set"
            raise UPnPError(msg)

        params: dict[str, str] = {}
        response = await send_soap_action(
            self.control_url,
            "GetExternalIPAddress",
            self.service_type,
            params,
        )

        external_ip_str = response.get("NewExternalIPAddress")
        if not external_ip_str:
            msg = "No external IP in response"
            raise UPnPError(msg)

        try:
            return ipaddress.IPv4Address(external_ip_str)
        except ValueError as e:
            msg = f"Invalid external IP address: {external_ip_str}"
            raise UPnPError(msg) from e

    async def add_port_mapping(
        self,
        internal_port: int,
        external_port: int,
        protocol: str = "TCP",
        description: str = "ccBitTorrent",
        remote_host: str = "",
        duration: int = 3600,
    ) -> bool:
        """Add port mapping.

        Args:
            internal_port: Internal port
            external_port: External port
            protocol: "TCP" or "UDP"
            description: Port mapping description
            remote_host: Remote host IP (empty for any)
            duration: Mapping duration in seconds (0 for permanent)

        Returns:
            True if mapping added successfully

        Raises:
            UPnPError: If unable to add port mapping

        """
        if not self.control_url:
            discovered = await self.discover()
            if not discovered:
                msg = "Failed to discover UPnP device"
                raise UPnPError(msg)

        # Get internal client IP (our IP)
        # Many routers require the actual internal IP address, not empty string
        # Some routers reject empty string, so we should always try to get the real IP
        internal_client_ip = ""
        try:
            # Get local IPv4 address using same method as session manager
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            internal_client_ip = s.getsockname()[0]
            s.close()
            self.logger.debug(
                "Determined local IP for UPnP mapping: %s", internal_client_ip
            )
        except Exception as e:
            # If we can't determine IP, log warning but try empty string
            # Some routers accept empty string, others require the actual IP
            self.logger.warning(
                "Could not determine local IP for UPnP mapping (error: %s), using empty string. "
                "This may cause the router to reject the mapping request.",
                e,
            )

        params = {
            "NewRemoteHost": remote_host,
            "NewExternalPort": str(external_port),
            "NewProtocol": protocol.upper(),
            "NewInternalPort": str(internal_port),
            "NewInternalClient": internal_client_ip,
            "NewEnabled": "1",
            "NewPortMappingDescription": description,
            "NewLeaseDuration": str(duration),
        }

        if not self.control_url:
            msg = "Control URL not set"
            raise UPnPError(msg)

        try:
            # Some routers require deleting existing mapping first
            # Try to delete any existing mapping for this port/protocol
            # Try with empty remote_host first (most common case)
            deleted = await self.delete_port_mapping(
                external_port,
                protocol,
                "",  # Empty remote_host (wildcard)
            )
            if deleted:
                self.logger.debug(
                    "Deleted existing port mapping for %s:%s before adding new one",
                    protocol,
                    external_port,
                )
            # If that didn't work and we have a specific remote_host, try with it
            elif remote_host:
                deleted = await self.delete_port_mapping(
                    external_port,
                    protocol,
                    remote_host,
                )
                if deleted:
                    self.logger.debug(
                        "Deleted existing port mapping for %s:%s (remote_host=%s) before adding new one",
                        protocol,
                        external_port,
                        remote_host,
                    )

            response = await send_soap_action(
                self.control_url,
                "AddPortMapping",
                self.service_type,
                params,
            )

            # Check for error code (some routers return errorCode in response)
            error_code = response.get("errorCode")
            if error_code and error_code != "0":
                msg = f"AddPortMapping failed: error code {error_code}"
                raise UPnPError(msg)

            self.logger.info(
                "Mapped %s port %s -> %s (duration: %s s, internal IP: %s)",
                protocol,
                internal_port,
                external_port,
                duration,
                internal_client_ip or "auto",
            )
            return True
        except UPnPError:
            raise
        except Exception as e:
            msg = f"Error adding port mapping: {e}"
            raise UPnPError(msg) from e

    async def delete_port_mapping(
        self,
        external_port: int,
        protocol: str = "TCP",
        remote_host: str = "",
    ) -> bool:
        """Delete port mapping.

        Args:
            external_port: External port to remove
            protocol: "TCP" or "UDP"
            remote_host: Remote host IP (empty for any)

        Returns:
            True if mapping deleted successfully, False if mapping doesn't exist

        Raises:
            UPnPError: If unable to delete port mapping (other than not existing)

        """
        if not self.control_url:
            discovered = await self.discover()
            if not discovered:
                msg = "Failed to discover UPnP device"
                raise UPnPError(msg)

        params = {
            "NewRemoteHost": remote_host,
            "NewExternalPort": str(external_port),
            "NewProtocol": protocol.upper(),
        }

        if not self.control_url:
            msg = "Control URL not set"
            raise UPnPError(msg)

        try:
            response = await send_soap_action(
                self.control_url,
                "DeletePortMapping",
                self.service_type,
                params,
            )

            # Check for error code
            error_code = response.get("errorCode")
            if error_code and error_code != "0":
                msg = f"DeletePortMapping failed: error code {error_code}"
                raise UPnPError(msg)

            self.logger.info(
                "Deleted %s port mapping for port %s", protocol, external_port
            )
            return True
        except UPnPError as e:
            # Error 714 means the mapping doesn't exist - this is OK, return False
            error_msg = str(e)
            if "714" in error_msg or "NoSuchEntryInArray" in error_msg:
                self.logger.debug(
                    "Port mapping %s:%s does not exist (error 714), nothing to delete",
                    protocol,
                    external_port,
                )
                return False
            # For other errors, re-raise
            raise
        except Exception as e:
            msg = f"Error deleting port mapping: {e}"
            raise UPnPError(msg) from e

    async def get_port_mappings(self) -> list[dict[str, str]]:
        """Get all port mappings using GetGenericPortMappingEntry.

        This method queries the router for all existing port mappings.
        Some routers may not support this action, in which case an empty list is returned.

        Returns:
            List of port mapping dictionaries with keys:
            - NewRemoteHost
            - NewExternalPort
            - NewProtocol
            - NewInternalPort
            - NewInternalClient
            - NewEnabled
            - NewPortMappingDescription
            - NewLeaseDuration

        """
        if not self.control_url:
            discovered = await self.discover()
            if not discovered:
                msg = "Failed to discover UPnP device"
                raise UPnPError(msg)

        if not self.control_url:
            msg = "Control URL not set"
            raise UPnPError(msg)

        mappings: list[dict[str, str]] = []
        index = 0

        try:
            # GetGenericPortMappingEntry is called repeatedly with increasing index
            # until an error is returned (indicating no more entries)
            while True:
                params = {
                    "NewPortMappingIndex": str(index),
                }

                try:
                    response = await send_soap_action(
                        self.control_url,
                        "GetGenericPortMappingEntry",
                        self.service_type,
                        params,
                    )
                    mappings.append(response)
                    index += 1
                except UPnPError as e:
                    # Error 713 or 714 means no more entries (end of list)
                    error_msg = str(e)
                    if "713" in error_msg or "714" in error_msg or "NoSuchEntryInArray" in error_msg:
                        break
                    # Other errors are unexpected - log and stop
                    self.logger.debug(
                        "GetGenericPortMappingEntry failed at index %d: %s",
                        index,
                        error_msg,
                    )
                    break
        except Exception as e:
            # Some routers don't support GetGenericPortMappingEntry
            # This is OK - we'll just skip cleanup and rely on delete before add
            self.logger.debug(
                "GetGenericPortMappingEntry not supported or failed: %s. "
                "Will rely on delete before add strategy.",
                e,
            )
            return []

        return mappings

    async def clear_all_mappings(self, description_filter: str = "ccBitTorrent") -> int:
        """Clear all port mappings matching the description filter.

        This method queries all port mappings and deletes those that match
        the description filter (default: "ccBitTorrent"). This is useful
        for cleaning up stale mappings on startup.

        Args:
            description_filter: Description string to match (default: "ccBitTorrent")

        Returns:
            Number of mappings deleted

        """
        if not self.control_url:
            discovered = await self.discover()
            if not discovered:
                self.logger.debug(
                    "Cannot clear mappings: UPnP device not discovered"
                )
                return 0

        try:
            mappings = await self.get_port_mappings()
        except UPnPError:
            # GetGenericPortMappingEntry not supported - skip cleanup
            self.logger.debug(
                "Cannot query mappings for cleanup (GetGenericPortMappingEntry not supported). "
                "Will rely on delete before add strategy."
            )
            return 0

        deleted_count = 0
        for mapping in mappings:
            desc = mapping.get("NewPortMappingDescription", "")
            if description_filter.lower() in desc.lower():
                try:
                    external_port = int(mapping.get("NewExternalPort", "0"))
                    protocol = mapping.get("NewProtocol", "TCP")
                    remote_host = mapping.get("NewRemoteHost", "")

                    if external_port > 0:
                        deleted = await self.delete_port_mapping(
                            external_port,
                            protocol,
                            remote_host,
                        )
                        if deleted:
                            deleted_count += 1
                            self.logger.debug(
                                "Cleared existing mapping: %s:%s (description: %s)",
                                protocol,
                                external_port,
                                desc,
                            )
                except (ValueError, UPnPError) as e:
                    self.logger.debug(
                        "Failed to delete mapping during cleanup: %s", e
                    )
                    continue

        if deleted_count > 0:
            self.logger.info(
                "Cleared %d existing port mapping(s) with description '%s'",
                deleted_count,
                description_filter,
            )

        return deleted_count
