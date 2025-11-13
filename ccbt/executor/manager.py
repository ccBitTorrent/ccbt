"""Executor manager for managing executor instances.

Provides singleton pattern to ensure single executor instance per session manager,
preventing duplicate executors and session reference mismatches.
"""

from __future__ import annotations

import logging
import weakref
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.daemon.ipc_client import IPCClient
    from ccbt.executor.executor import UnifiedCommandExecutor
    from ccbt.executor.session_adapter import SessionAdapter
    from ccbt.session.session import AsyncSessionManager

logger = logging.getLogger(__name__)


class ExecutorManager:
    """Singleton manager for executor instances.

    Ensures single executor instance per session manager to prevent
    duplicate executors and session reference mismatches.
    """

    _instance: ExecutorManager | None = None
    _lock: Any = None  # threading.Lock, but avoid import if not needed

    def __init__(self) -> None:
        """Initialize executor manager."""
        # Use weak references to allow garbage collection
        # Key: session manager ID (id() of the object)
        # Value: (executor, adapter) tuple
        self._executors: dict[int, tuple[UnifiedCommandExecutor, SessionAdapter]] = {}
        # Track session managers by weak reference for cleanup
        self._session_refs: dict[int, weakref.ref[Any]] = {}
        # Track IPC clients for daemon sessions
        self._ipc_clients: dict[int, IPCClient] = {}
        # Initialize lock if threading is available
        try:
            import threading

            self._lock = threading.Lock()
        except ImportError:
            # No threading support, operations won't be thread-safe
            # This is acceptable for single-threaded async code
            self._lock = None

    @classmethod
    def get_instance(cls) -> ExecutorManager:
        """Get singleton instance of ExecutorManager.

        Returns:
            ExecutorManager instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_session_id(self, session_manager: Any) -> int:
        """Get unique ID for session manager.

        Args:
            session_manager: Session manager instance

        Returns:
            Unique ID (using id() of the object)
        """
        return id(session_manager)

    def _cleanup_dead_references(self) -> None:
        """Clean up references to dead session managers."""
        dead_ids = []
        for session_id, ref in self._session_refs.items():
            if ref() is None:
                dead_ids.append(session_id)

        for session_id in dead_ids:
            logger.debug(
                "Cleaning up executor for dead session manager (id: %d)",
                session_id,
            )
            self._executors.pop(session_id, None)
            self._session_refs.pop(session_id, None)
            self._ipc_clients.pop(session_id, None)

    def get_executor(
        self,
        session_manager: AsyncSessionManager | None = None,
        ipc_client: IPCClient | None = None,
    ) -> UnifiedCommandExecutor:
        """Get or create executor for session manager or IPC client.

        Args:
            session_manager: AsyncSessionManager instance (for local sessions)
            ipc_client: IPCClient instance (for daemon sessions)

        Returns:
            UnifiedCommandExecutor instance

        Raises:
            ValueError: If neither session_manager nor ipc_client is provided
            RuntimeError: If executor creation fails or session reference mismatch
        """
        if session_manager is None and ipc_client is None:
            raise ValueError(
                "Either session_manager or ipc_client must be provided"
            )

        # Clean up dead references first
        self._cleanup_dead_references()

        # Determine session ID
        if session_manager is not None:
            session_id = self._get_session_id(session_manager)
            session_key = "session_manager"
            session_obj = session_manager
        else:
            # For IPC client, use the client object ID
            assert ipc_client is not None
            session_id = self._get_session_id(ipc_client)
            session_key = "ipc_client"
            session_obj = ipc_client

        # Check if executor already exists
        if session_id in self._executors:
            executor, adapter = self._executors[session_id]
            # Validate that adapter still references correct session
            if session_manager is not None:
                if (
                    hasattr(adapter, "session_manager")
                    and adapter.session_manager is not session_manager
                ):
                    logger.warning(
                        "Session manager reference mismatch detected. "
                        "Recreating executor."
                    )
                    # Remove old executor and create new one
                    self._executors.pop(session_id, None)
                    self._session_refs.pop(session_id, None)
                else:
                    # Executor is valid, return it
                    logger.debug(
                        "Reusing existing executor for %s (id: %d)",
                        session_key,
                        session_id,
                    )
                    return executor
            elif ipc_client is not None:
                if (
                    hasattr(adapter, "ipc_client")
                    and adapter.ipc_client is not ipc_client
                ):
                    logger.warning(
                        "IPC client reference mismatch detected. "
                        "Recreating executor."
                    )
                    # Remove old executor and create new one
                    self._executors.pop(session_id, None)
                    self._ipc_clients.pop(session_id, None)
                else:
                    # Executor is valid, return it
                    logger.debug(
                        "Reusing existing executor for %s (id: %d)",
                        session_key,
                        session_id,
                    )
                    return executor

        # Create new executor
        logger.debug(
            "Creating new executor for %s (id: %d)",
            session_key,
            session_id,
        )

        try:
            from ccbt.executor.executor import UnifiedCommandExecutor
            from ccbt.executor.session_adapter import (
                DaemonSessionAdapter,
                LocalSessionAdapter,
            )

            if session_manager is not None:
                # Local session adapter
                adapter = LocalSessionAdapter(session_manager)
                # Validate adapter
                if (
                    not hasattr(adapter, "session_manager")
                    or adapter.session_manager is not session_manager
                ):
                    raise RuntimeError(
                        "LocalSessionAdapter session_manager reference mismatch"
                    )
            else:
                # Daemon session adapter
                assert ipc_client is not None
                adapter = DaemonSessionAdapter(ipc_client)
                # Validate adapter
                if (
                    not hasattr(adapter, "ipc_client")
                    or adapter.ipc_client is not ipc_client
                ):
                    raise RuntimeError(
                        "DaemonSessionAdapter ipc_client reference mismatch"
                    )

            executor = UnifiedCommandExecutor(adapter)

            # Validate executor
            if not hasattr(executor, "adapter") or executor.adapter is None:
                raise RuntimeError("Executor adapter not initialized")
            if executor.adapter is not adapter:
                raise RuntimeError("Executor adapter reference mismatch")

            # Store executor and create weak reference
            self._executors[session_id] = (executor, adapter)
            if session_manager is not None:
                self._session_refs[session_id] = weakref.ref(session_manager)
            if ipc_client is not None:
                self._ipc_clients[session_id] = ipc_client

            logger.info(
                "Created executor for %s (id: %d, adapter=%s)",
                session_key,
                session_id,
                type(adapter).__name__,
            )

            return executor

        except Exception as e:
            logger.exception(
                "Failed to create executor for %s (id: %d): %s",
                session_key,
                session_id,
                e,
            )
            raise RuntimeError(f"Failed to create executor: {e}") from e

    def remove_executor(
        self,
        session_manager: AsyncSessionManager | None = None,
        ipc_client: IPCClient | None = None,
    ) -> None:
        """Remove executor for session manager or IPC client.

        Args:
            session_manager: AsyncSessionManager instance (for local sessions)
            ipc_client: IPCClient instance (for daemon sessions)
        """
        if session_manager is None and ipc_client is None:
            return

        # Determine session ID
        if session_manager is not None:
            session_id = self._get_session_id(session_manager)
        else:
            assert ipc_client is not None
            session_id = self._get_session_id(ipc_client)

        # Remove executor
        if session_id in self._executors:
            logger.debug(
                "Removing executor for session (id: %d)",
                session_id,
            )
            self._executors.pop(session_id, None)
            self._session_refs.pop(session_id, None)
            self._ipc_clients.pop(session_id, None)

    def clear_all(self) -> None:
        """Clear all executors (for testing or shutdown)."""
        logger.debug("Clearing all executors")
        self._executors.clear()
        self._session_refs.clear()
        self._ipc_clients.clear()








