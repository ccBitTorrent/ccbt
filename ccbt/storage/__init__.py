"""Storage and disk I/O components.

This module handles file assembly, disk I/O, checkpointing, and buffer management.
"""

from __future__ import annotations

from ccbt.storage.buffers import get_buffer_manager
from ccbt.storage.checkpoint import CheckpointManager
from ccbt.storage.disk_io import DiskIOManager
from ccbt.storage.disk_io_init import (
    get_disk_io_manager,
    init_disk_io,
    shutdown_disk_io,
)
from ccbt.storage.file_assembler import AsyncDownloadManager, DownloadManager
from ccbt.storage.resume_data import FastResumeData

__all__ = [
    "AsyncDiskIO",
    "AsyncDownloadManager",
    "CheckpointManager",
    "DiskIO",
    "DiskIOManager",
    "DownloadManager",
    "FastResumeData",
    "get_buffer_manager",
    "get_disk_io_manager",
    "init_disk_io",
    "shutdown_disk_io",
]
