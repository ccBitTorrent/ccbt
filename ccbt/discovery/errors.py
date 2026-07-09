"""Discovery-layer exceptions shared across modules."""


class SockRecvfromUnsupportedError(RuntimeError):
    """Raised when the asyncio event loop does not provide sock_recvfrom."""

    def __init__(self) -> None:
        """Initialize with the standard error message."""
        super().__init__("Event loop does not support sock_recvfrom")
