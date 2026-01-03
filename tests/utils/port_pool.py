"""Port pool manager for unique port allocation in tests.

This module provides a centralized port pool manager to prevent port conflicts
between tests by ensuring each test gets unique ports.
"""

from __future__ import annotations

import socket
import threading
from typing import Optional

# Default port range for test allocation
DEFAULT_START_PORT = 64000
DEFAULT_END_PORT = 65000


class PortPool:
    """Manages a pool of available ports for test allocation.
    
    This class ensures that each test gets unique ports to prevent conflicts.
    Ports are allocated from a configurable range and tracked per test.
    """
    
    _instance: Optional[PortPool] = None
    _lock = threading.Lock()
    
    def __init__(self, start_port: int = DEFAULT_START_PORT, end_port: int = DEFAULT_END_PORT):
        """Initialize port pool.
        
        Args:
            start_port: Starting port number for allocation range
            end_port: Ending port number for allocation range (exclusive)
        """
        self.start_port = start_port
        self.end_port = end_port
        self._allocated_ports: set[int] = set()
        self._current_port = start_port
        self._lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> PortPool:
        """Get singleton instance of PortPool.
        
        Returns:
            PortPool instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None
    
    def get_free_port(self) -> int:
        """Get a free port from the pool.
        
        Returns:
            Port number that is available and not allocated
            
        Raises:
            RuntimeError: If no free ports are available in the range
        """
        with self._lock:
            # Try to find a free port starting from current position
            attempts = 0
            max_attempts = self.end_port - self.start_port
            
            while attempts < max_attempts:
                port = self._current_port
                self._current_port += 1
                if self._current_port >= self.end_port:
                    self._current_port = self.start_port
                
                # Check if port is already allocated
                if port in self._allocated_ports:
                    attempts += 1
                    continue
                
                # Check if port is actually available (not in use by OS)
                if self._is_port_available(port):
                    self._allocated_ports.add(port)
                    return port
                
                attempts += 1
            
            # If we've exhausted all ports, raise error
            raise RuntimeError(
                f"No free ports available in range {self.start_port}-{self.end_port}. "
                f"Allocated ports: {len(self._allocated_ports)}"
            )
    
    def release_port(self, port: int) -> None:
        """Release a port back to the pool.
        
        Args:
            port: Port number to release
        """
        with self._lock:
            self._allocated_ports.discard(port)
    
    def release_all_ports(self) -> None:
        """Release all allocated ports (for cleanup)."""
        with self._lock:
            self._allocated_ports.clear()
            self._current_port = self.start_port
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available (not in use by OS).
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is available, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False
    
    def get_allocated_count(self) -> int:
        """Get count of currently allocated ports.
        
        Returns:
            Number of allocated ports
        """
        with self._lock:
            return len(self._allocated_ports)
    
    def get_allocated_ports(self) -> set[int]:
        """Get set of currently allocated ports.
        
        Returns:
            Set of allocated port numbers
        """
        with self._lock:
            return set(self._allocated_ports)


# Convenience function for backward compatibility
def get_free_port() -> int:
    """Get a free port from the port pool.
    
    Returns:
        Port number that is available
    """
    pool = PortPool.get_instance()
    return pool.get_free_port()






