"""Base service architecture for ccBitTorrent.

from __future__ import annotations

Provides the foundation for service-oriented components with health checks,
circuit breakers, and service discovery.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ccbt.exceptions import CCBTError
from ccbt.logging_config import get_logger


class ServiceState(Enum):
    """Service lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    DEGRADED = "degraded"


class ServiceError(CCBTError):
    """Exception raised for service-related errors."""


@dataclass
class ServiceInfo:
    """Information about a service."""

    name: str
    version: str
    description: str
    state: ServiceState
    health_score: float = 1.0
    last_health_check: float = 0.0
    error_count: int = 0
    success_count: int = 0
    dependencies: list[str] = field(default_factory=list)


@dataclass
class HealthCheck:
    """Health check result."""

    service_name: str
    healthy: bool
    score: float
    message: str
    timestamp: float
    response_time: float


class Service(ABC):
    """Base class for all services."""

    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        """Initialize service.

        Args:
            name: Service name
            version: Service version
            description: Service description
        """
        self.name = name
        self.version = version
        self.description = description
        self.state = ServiceState.STOPPED
        self.health_score = 1.0
        self.error_count = 0
        self.success_count = 0
        self.dependencies: list[str] = []
        self.logger = get_logger(f"service.{name}")

        # Health check settings
        self.health_check_interval = 30.0
        self.health_check_timeout = 5.0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60.0

        # Circuit breaker state
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure = 0.0
        self.circuit_breaker_open = False

    @abstractmethod
    async def start(self) -> None:
        """Start the service."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service."""

    @abstractmethod
    async def health_check(self) -> HealthCheck:
        """Perform health check."""

    def get_info(self) -> ServiceInfo:
        """Get service information."""
        return ServiceInfo(
            name=self.name,
            version=self.version,
            description=self.description,
            state=self.state,
            health_score=self.health_score,
            last_health_check=time.time(),
            error_count=self.error_count,
            success_count=self.success_count,
            dependencies=self.dependencies,
        )

    def add_dependency(self, service_name: str) -> None:
        """Add a service dependency."""
        if service_name not in self.dependencies:
            self.dependencies.append(service_name)

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.health_score > 0.5 and not self.circuit_breaker_open

    def is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self.circuit_breaker_open:
            return False

        # Check if timeout has passed
        if (
            time.time() - self.circuit_breaker_last_failure
            > self.circuit_breaker_timeout
        ):
            self.circuit_breaker_open = False
            self.circuit_breaker_failures = 0
            self.logger.info("Circuit breaker closed for service '%s'", self.name)
            return False

        return True

    def record_success(self) -> None:
        """Record a successful operation."""
        self.success_count += 1
        self.health_score = min(1.0, self.health_score + 0.1)

    def record_error(self, _error: Exception) -> None:
        """Record an error."""
        self.error_count += 1
        self.health_score = max(0.0, self.health_score - 0.1)

        # Check circuit breaker
        self.circuit_breaker_failures += 1
        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            self.circuit_breaker_last_failure = time.time()
            self.logger.warning(
                "Circuit breaker opened for service '%s' after %s failures",
                self.name,
                self.circuit_breaker_failures,
            )

    async def start_health_monitoring(self) -> None:
        """Start health monitoring task."""
        while self.state == ServiceState.RUNNING:
            try:
                await asyncio.sleep(self.health_check_interval)

                if self.state == ServiceState.RUNNING:
                    health_check = await self.health_check()
                    self.health_score = health_check.score

                    if not health_check.healthy:
                        self.logger.warning(
                            "Health check failed for service '%s': %s",
                            self.name,
                            health_check.message,
                        )
                    else:
                        self.logger.debug(
                            "Health check passed for service '%s'",
                            self.name,
                        )

            except Exception:
                self.logger.exception(
                    "Health monitoring error for service '%s'",
                    self.name,
                )

    async def call_with_circuit_breaker(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function with circuit breaker protection."""
        if self.is_circuit_breaker_open():
            msg = f"Circuit breaker is open for service '{self.name}'"
            raise ServiceError(msg)

        try:
            result = await func(*args, **kwargs)
            self.record_success()
        except Exception as e:
            self.record_error(e)
            raise
        else:
            return result


class ServiceManager:
    """Manages service lifecycle and communication."""

    def __init__(self):
        """Initialize service manager."""
        self.services: dict[str, Service] = {}
        self.service_info: dict[str, ServiceInfo] = {}
        self.health_check_tasks: dict[str, asyncio.Task] = {}
        self.logger = get_logger(__name__)

    async def register_service(self, service: Service) -> None:
        """Register a service.

        Args:
            service: Service instance
        """
        if service.name in self.services:
            msg = f"Service '{service.name}' is already registered"
            raise ServiceError(msg)

        self.services[service.name] = service
        self.service_info[service.name] = service.get_info()
        self.logger.info("Registered service: %s", service.name)

    async def unregister_service(self, service_name: str) -> None:
        """Unregister a service.

        Args:
            service_name: Name of service to unregister
        """
        if service_name not in self.services:
            msg = f"Service '{service_name}' is not registered"
            raise ServiceError(msg)

        # Stop service if running
        if self.services[service_name].state == ServiceState.RUNNING:
            await self.stop_service(service_name)

        # Cancel health check task
        if service_name in self.health_check_tasks:
            self.health_check_tasks[service_name].cancel()
            del self.health_check_tasks[service_name]

        # Remove service
        del self.services[service_name]
        del self.service_info[service_name]
        self.logger.info("Unregistered service: %s", service_name)

    async def start_service(self, service_name: str) -> None:
        """Start a service.

        Args:
            service_name: Name of service to start
        """
        if service_name not in self.services:
            msg = f"Service '{service_name}' is not registered"
            raise ServiceError(msg)

        service = self.services[service_name]

        if service.state != ServiceState.STOPPED:
            msg = f"Service '{service_name}' is not in stopped state"
            raise ServiceError(msg)

        try:
            service.state = ServiceState.STARTING
            await service.start()
            service.state = ServiceState.RUNNING

            # Start health monitoring
            health_task = asyncio.create_task(service.start_health_monitoring())
            self.health_check_tasks[service_name] = health_task

            self.logger.info("Started service: %s", service_name)

        except Exception as e:
            service.state = ServiceState.ERROR
            self.logger.exception("Failed to start service '%s'", service_name)
            msg = f"Failed to start service '{service_name}': {e}"
            raise ServiceError(msg) from e

    async def stop_service(self, service_name: str) -> None:
        """Stop a service.

        Args:
            service_name: Name of service to stop
        """
        if service_name not in self.services:
            msg = f"Service '{service_name}' is not registered"
            raise ServiceError(msg)

        service = self.services[service_name]

        if service.state != ServiceState.RUNNING:
            msg = f"Service '{service_name}' is not running"
            raise ServiceError(msg)

        try:
            service.state = ServiceState.STOPPING
            await service.stop()
            service.state = ServiceState.STOPPED

            # Cancel health check task
            if service_name in self.health_check_tasks:
                self.health_check_tasks[service_name].cancel()
                del self.health_check_tasks[service_name]

            self.logger.info("Stopped service: %s", service_name)

        except Exception as e:
            service.state = ServiceState.ERROR
            self.logger.exception("Failed to stop service '%s'", service_name)
            msg = f"Failed to stop service '{service_name}': {e}"
            raise ServiceError(msg) from e

    def get_service(self, service_name: str) -> Service | None:
        """Get a service by name."""
        return self.services.get(service_name)

    def get_service_info(self, service_name: str) -> ServiceInfo | None:
        """Get service information."""
        return self.service_info.get(service_name)

    def list_services(self) -> list[ServiceInfo]:
        """List all registered services."""
        return list(self.service_info.values())

    def get_healthy_services(self) -> list[ServiceInfo]:
        """Get all healthy services."""
        return [info for info in self.service_info.values() if info.health_score > 0.5]

    def get_service_dependencies(self, service_name: str) -> list[str]:
        """Get service dependencies."""
        if service_name in self.service_info:
            return self.service_info[service_name].dependencies
        return []

    async def shutdown(self) -> None:
        """Shutdown all services."""
        self.logger.info("Shutting down service manager")

        # Stop all running services
        for service_name in list(self.services.keys()):
            try:
                if self.services[service_name].state == ServiceState.RUNNING:
                    await self.stop_service(service_name)
            except Exception:
                self.logger.exception(
                    "Error shutting down service '%s'",
                    service_name,
                )

        self.logger.info("Service manager shutdown complete")


# Global service manager instance
_service_manager: ServiceManager | None = None


def get_service_manager() -> ServiceManager:
    """Get the global service manager."""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
