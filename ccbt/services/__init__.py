"""Service-oriented components for ccBitTorrent.

from __future__ import annotations

Provides microservices-style components for peer management,
tracker communication, and storage operations.
"""

from ccbt.services.base import (
    Service,
    ServiceError,
    ServiceManager,
    get_service_manager,
)
from ccbt.services.peer_service import PeerService
from ccbt.services.storage_service import StorageService
from ccbt.services.tracker_service import TrackerService

__all__ = [
    "PeerService",
    "Service",
    "ServiceError",
    "ServiceManager",
    "StorageService",
    "TrackerService",
    "get_service_manager",
]
