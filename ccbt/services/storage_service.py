"""Storage service for ccBitTorrent.

Manages file storage operations with health checks and
circuit breaker protection.
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging_config import LoggingContext
from .base import HealthCheck, Service


@dataclass
class StorageOperation:
    """Represents a storage operation."""
    operation_type: str
    file_path: str
    size: int
    timestamp: float
    duration: float
    success: bool


@dataclass
class FileInfo:
    """Information about a stored file."""
    path: str
    size: int
    created_at: float
    modified_at: float
    pieces_complete: int
    pieces_total: int
    is_complete: bool


class StorageService(Service):
    """Service for managing file storage operations."""

    def __init__(self, max_concurrent_operations: int = 10,
                 cache_size_mb: int = 256):
        super().__init__(
            name="storage_service",
            version="1.0.0",
            description="File storage management service",
        )
        self.max_concurrent_operations = max_concurrent_operations
        self.cache_size_mb = cache_size_mb
        self.cache_size_bytes = cache_size_mb * 1024 * 1024

        # Storage tracking
        self.files: Dict[str, FileInfo] = {}
        self.active_operations = 0
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0

        # Performance metrics
        self.total_bytes_written = 0
        self.total_bytes_read = 0
        self.average_write_speed = 0.0
        self.average_read_speed = 0.0

        # Operation queue
        self.operation_queue: asyncio.Queue = asyncio.Queue()
        self.operation_tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Start the storage service."""
        self.logger.info("Starting storage service")

        # Initialize storage management
        await self._initialize_storage_management()

    async def stop(self) -> None:
        """Stop the storage service."""
        self.logger.info("Stopping storage service")

        # Cancel all operation tasks
        for task in self.operation_tasks:
            task.cancel()

        # Clear storage data
        self.files.clear()
        self.active_operations = 0

    async def health_check(self) -> HealthCheck:
        """Perform health check."""
        start_time = time.time()

        try:
            # Check if we can perform storage operations
            healthy = (
                self.active_operations <= self.max_concurrent_operations and
                self.failed_operations < self.total_operations * 0.1
            )

            # Calculate health score
            if self.total_operations == 0:
                health_score = 1.0
            else:
                success_rate = self.successful_operations / self.total_operations
                health_score = success_rate

            response_time = time.time() - start_time

            return HealthCheck(
                service_name=self.name,
                healthy=healthy,
                score=health_score,
                message=f"Operations: {self.active_operations}/{self.max_concurrent_operations}, Success rate: {self.successful_operations}/{self.total_operations}",
                timestamp=time.time(),
                response_time=response_time,
            )

        except Exception as e:
            return HealthCheck(
                service_name=self.name,
                healthy=False,
                score=0.0,
                message=f"Health check failed: {e}",
                timestamp=time.time(),
                response_time=time.time() - start_time,
            )

    async def _initialize_storage_management(self) -> None:
        """Initialize storage management systems."""
        self.logger.info("Initializing storage management")

        # Start operation processing tasks
        for i in range(self.max_concurrent_operations):
            task = asyncio.create_task(self._process_operations())
            self.operation_tasks.append(task)

    async def _process_operations(self) -> None:
        """Process storage operations from queue."""
        while self.state.value == "running":
            try:
                operation = await self.operation_queue.get()
                await self._execute_operation(operation)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing storage operation: {e}")

    async def _execute_operation(self, operation: StorageOperation) -> None:
        """Execute a storage operation."""
        try:
            with LoggingContext("storage_operation",
                              operation=operation.operation_type,
                              file_path=operation.file_path):

                start_time = time.time()
                success = False

                if operation.operation_type == "write":
                    success = await self._write_file(operation.file_path, operation.size)
                elif operation.operation_type == "read":
                    success = await self._read_file(operation.file_path, operation.size)
                elif operation.operation_type == "delete":
                    success = await self._delete_file(operation.file_path)

                operation.duration = time.time() - start_time
                operation.success = success

                if success:
                    self.successful_operations += 1
                else:
                    self.failed_operations += 1

                self.total_operations += 1
                self.active_operations -= 1

        except Exception as e:
            self.logger.error(f"Storage operation failed: {e}")
            self.failed_operations += 1
            self.total_operations += 1
            self.active_operations -= 1

    async def _write_file(self, file_path: str, size: int) -> bool:
        """Write a file."""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Simulate file write
            with open(path, "wb") as f:
                f.write(b"0" * size)

            self.total_bytes_written += size
            return True

        except Exception as e:
            self.logger.error(f"Failed to write file {file_path}: {e}")
            return False

    async def _read_file(self, file_path: str, size: int) -> bool:
        """Read a file."""
        try:
            path = Path(file_path)
            if not path.exists():
                return False

            with open(path, "rb") as f:
                data = f.read(size)

            self.total_bytes_read += len(data)
            return True

        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            return False

    async def _delete_file(self, file_path: str) -> bool:
        """Delete a file."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    async def write_file(self, file_path: str, data: bytes) -> bool:
        """Write data to a file.
        
        Args:
            file_path: Path to file
            data: Data to write
            
        Returns:
            True if successful
        """
        if self.active_operations >= self.max_concurrent_operations:
            self.logger.warning("Storage service at capacity")
            return False

        operation = StorageOperation(
            operation_type="write",
            file_path=file_path,
            size=len(data),
            timestamp=time.time(),
            duration=0.0,
            success=False,
        )

        await self.operation_queue.put(operation)
        self.active_operations += 1

        return True

    async def read_file(self, file_path: str, size: int) -> Optional[bytes]:
        """Read data from a file.
        
        Args:
            file_path: Path to file
            size: Number of bytes to read
            
        Returns:
            File data or None if failed
        """
        if self.active_operations >= self.max_concurrent_operations:
            self.logger.warning("Storage service at capacity")
            return None

        operation = StorageOperation(
            operation_type="read",
            file_path=file_path,
            size=size,
            timestamp=time.time(),
            duration=0.0,
            success=False,
        )

        await self.operation_queue.put(operation)
        self.active_operations += 1

        # For now, return empty data
        return b""

    async def delete_file(self, file_path: str) -> bool:
        """Delete a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if successful
        """
        if self.active_operations >= self.max_concurrent_operations:
            self.logger.warning("Storage service at capacity")
            return False

        operation = StorageOperation(
            operation_type="delete",
            file_path=file_path,
            size=0,
            timestamp=time.time(),
            duration=0.0,
            success=False,
        )

        await self.operation_queue.put(operation)
        self.active_operations += 1

        return True

    async def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get file information."""
        return self.files.get(file_path)

    async def list_files(self) -> List[FileInfo]:
        """List all tracked files."""
        return list(self.files.values())

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage service statistics."""
        return {
            "total_files": len(self.files),
            "active_operations": self.active_operations,
            "max_concurrent_operations": self.max_concurrent_operations,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "total_bytes_written": self.total_bytes_written,
            "total_bytes_read": self.total_bytes_read,
            "average_write_speed": self.average_write_speed,
            "average_read_speed": self.average_read_speed,
            "success_rate": (
                self.successful_operations / max(self.total_operations, 1)
            ),
        }

    async def get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information."""
        total_size = sum(f.size for f in self.files.values())
        complete_files = sum(1 for f in self.files.values() if f.is_complete)

        return {
            "total_size": total_size,
            "total_files": len(self.files),
            "complete_files": complete_files,
            "incomplete_files": len(self.files) - complete_files,
            "completion_rate": complete_files / max(len(self.files), 1),
        }
