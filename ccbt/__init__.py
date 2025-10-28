"""ccBitTorrent - A BitTorrent client implementation."""

from __future__ import annotations

__version__ = "0.1.0"

# Ensure a default asyncio event loop exists on import for libraries/tests that
# construct futures outside of a running loop (e.g., asyncio.Future()).
# This avoids RuntimeError: There is no current event loop in thread 'MainThread'.
try:
    import asyncio

    class _SafeEventLoopPolicy(asyncio.AbstractEventLoopPolicy):
        """Wrapper policy that ensures a loop exists when requested."""

        def __init__(self, base: asyncio.AbstractEventLoopPolicy):
            self._base = base

        def get_event_loop(self):  # type: ignore[override]
            try:
                return asyncio.get_running_loop()
            except RuntimeError:
                # Create a new event loop if none exists
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop

        def set_event_loop(self, loop):  # type: ignore[override]
            return self._base.set_event_loop(loop)

        def new_event_loop(self):  # type: ignore[override]
            return self._base.new_event_loop()

        # Python 3.12+: get_running_loop is used in many places; delegate directly
        def get_running_loop(self):  # type: ignore[override]
            return self._base.get_running_loop()  # type: ignore[attr-defined]

        # Child watcher methods (posix); delegate if present
        def get_child_watcher(self):  # type: ignore[override]
            def _raise_not_implemented():
                raise NotImplementedError  # pragma: no cover

            if hasattr(self._base, "get_child_watcher"):
                return self._base.get_child_watcher()  # pragma: no cover
            return _raise_not_implemented()

        def set_child_watcher(self, watcher):  # type: ignore[override]
            def _raise_not_implemented():
                raise NotImplementedError  # pragma: no cover

            if hasattr(self._base, "set_child_watcher"):
                return self._base.set_child_watcher(watcher)  # pragma: no cover
            return _raise_not_implemented()

    # Install safe policy once
    try:
        base_policy = asyncio.get_event_loop_policy()
        if not isinstance(base_policy, _SafeEventLoopPolicy):
            asyncio.set_event_loop_policy(_SafeEventLoopPolicy(base_policy))
    except Exception:
        # As a fallback, ensure a loop is set at import time
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
except Exception:  # nosec B110 - If asyncio is unavailable or any error occurs, silently continue.
    # If asyncio is unavailable or any error occurs, silently continue.
    pass
