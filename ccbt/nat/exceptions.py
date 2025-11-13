"""NAT traversal exceptions."""


class NATError(Exception):
    """Base exception for NAT traversal errors."""


class NATPMPError(NATError):
    """NAT-PMP specific error."""


class UPnPError(NATError):
    """UPnP specific error."""
