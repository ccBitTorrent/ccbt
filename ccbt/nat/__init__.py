"""NAT traversal module for automatic port forwarding.

Provides support for NAT-PMP (RFC 6886) and UPnP IGD protocols
to enable automatic port mapping for peer connections.
"""

from ccbt.nat.exceptions import NATError, NATPMPError, UPnPError
from ccbt.nat.manager import NATManager

__all__ = ["NATError", "NATManager", "NATPMPError", "UPnPError"]
