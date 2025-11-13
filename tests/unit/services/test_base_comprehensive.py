"""Comprehensive tests for ccbt.services.base.

Covers:
- Service base class methods (add_dependency, is_healthy, circuit breaker, health monitoring)
- ServiceManager lifecycle operations (register, unregister, start, stop)
- ServiceManager query operations (get_service, get_service_info, list_services, etc.)
- Global service manager functions
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccbt.services.base import (
    HealthCheck,
    Service,
    ServiceError,
    ServiceInfo,
    ServiceManager,
    ServiceState,
    get_service_manager,
)


# Test service implementation
class MockTestService(Service):
    """Test service implementation for testing."""

    def __init__(self, name: str = "test_service", will_fail_start: bool = False, will_fail_stop: bool = False):
        """Initialize test service."""
        super().__init__(name, version="1.0.0", description="Test service")
        self.will_fail_start = will_fail_start
        self.will_fail_stop = will_fail_stop
        self.health_check_result = True

    async def start(self) -> None:
        """Start the service."""
        if self.will_fail_start:
            raise Exception("Start failed")

    async def stop(self) -> None:
        """Stop the service."""
        if self.will_fail_stop:
            raise Exception("Stop failed")

    async def health_check(self) -> HealthCheck:
        """Perform health check."""
        return HealthCheck(
            service_name=self.name,
            healthy=self.health_check_result,
            score=1.0 if self.health_check_result else 0.3,
            message="OK" if self.health_check_result else "Failed",
            timestamp=time.time(),
            response_time=0.1,
        )


pytestmark = [pytest.mark.unit]


class TestServiceBaseClass:
    """Test Service base class methods."""

    def test_add_dependency_new_dependency(self):
        """Test adding a new dependency (line 124)."""
        service = MockTestService("test")
        assert len(service.dependencies) == 0
        service.add_dependency("dep1")
        assert "dep1" in service.dependencies
        assert len(service.dependencies) == 1

    def test_add_dependency_existing_dependency(self):
        """Test adding existing dependency doesn't duplicate (line 125)."""
        service = MockTestService("test")
        service.add_dependency("dep1")
        service.add_dependency("dep1")  # Try to add again
        assert service.dependencies.count("dep1") == 1

    def test_is_healthy_true_when_healthy(self):
        """Test is_healthy returns True when healthy (line 129)."""
        service = MockTestService("test")
        service.health_score = 0.8
        service.circuit_breaker_open = False
        assert service.is_healthy() is True

    def test_is_healthy_false_when_low_score(self):
        """Test is_healthy returns False when health score is low."""
        service = MockTestService("test")
        service.health_score = 0.3
        service.circuit_breaker_open = False
        assert service.is_healthy() is False

    def test_is_healthy_false_when_circuit_breaker_open(self):
        """Test is_healthy returns False when circuit breaker is open."""
        service = MockTestService("test")
        service.health_score = 0.8
        service.circuit_breaker_open = True
        assert service.is_healthy() is False

    def test_is_circuit_breaker_open_false_when_not_open(self):
        """Test is_circuit_breaker_open returns False when not open (line 133)."""
        service = MockTestService("test")
        service.circuit_breaker_open = False
        assert service.is_circuit_breaker_open() is False

    def test_is_circuit_breaker_open_true_when_open_and_not_timed_out(self):
        """Test is_circuit_breaker_open returns True when open and not timed out (line 146)."""
        service = MockTestService("test")
        service.circuit_breaker_open = True
        service.circuit_breaker_last_failure = time.time() - 10.0  # Recent failure
        service.circuit_breaker_timeout = 60.0
        assert service.is_circuit_breaker_open() is True

    def test_is_circuit_breaker_open_false_when_timed_out(self):
        """Test is_circuit_breaker_open closes breaker when timeout passes (lines 137-144)."""
        service = MockTestService("test")
        service.circuit_breaker_open = True
        service.circuit_breaker_last_failure = time.time() - 70.0  # Old failure
        service.circuit_breaker_timeout = 60.0
        service.circuit_breaker_failures = 3
        assert service.is_circuit_breaker_open() is False
        assert service.circuit_breaker_open is False
        assert service.circuit_breaker_failures == 0

    @pytest.mark.asyncio
    async def test_record_success_increments_count(self):
        """Test record_success increments success count (line 150)."""
        service = MockTestService("test")
        initial_count = service.success_count
        service.record_success()
        assert service.success_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_record_success_increases_health_score(self):
        """Test record_success increases health score capped at 1.0 (line 151)."""
        service = MockTestService("test")
        service.health_score = 0.5
        service.record_success()
        assert service.health_score == 0.6
        service.health_score = 0.95
        service.record_success()
        assert service.health_score == 1.0  # Capped

    @pytest.mark.asyncio
    async def test_record_error_increments_error_count(self):
        """Test record_error increments error count (line 155)."""
        service = MockTestService("test")
        initial_count = service.error_count
        service.record_error(Exception("test"))
        assert service.error_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_record_error_decreases_health_score(self):
        """Test record_error decreases health score floored at 0.0 (line 156)."""
        service = MockTestService("test")
        service.health_score = 0.5
        service.record_error(Exception("test"))
        assert service.health_score == 0.4
        service.health_score = 0.05
        service.record_error(Exception("test"))
        assert service.health_score == 0.0  # Floored

    @pytest.mark.asyncio
    async def test_record_error_opens_circuit_breaker_at_threshold(self):
        """Test record_error opens circuit breaker when threshold reached (lines 159-167)."""
        service = MockTestService("test")
        service.circuit_breaker_threshold = 3
        service.circuit_breaker_failures = 2
        service.record_error(Exception("test"))
        assert service.circuit_breaker_failures == 3
        assert service.circuit_breaker_open is True
        assert service.circuit_breaker_last_failure > 0

    @pytest.mark.asyncio
    async def test_start_health_monitoring_loop(self):
        """Test health monitoring loop runs while service is running (lines 171-189)."""
        service = MockTestService("test")
        service.state = ServiceState.RUNNING
        service.health_check_interval = 0.1

        # Start monitoring task
        monitor_task = asyncio.create_task(service.start_health_monitoring())

        # Let it run a few iterations
        await asyncio.sleep(0.35)

        # Stop monitoring
        service.state = ServiceState.STOPPED
        await asyncio.sleep(0.1)

        # Cancel task
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_health_monitoring_updates_health_score(self):
        """Test health monitoring updates health score (lines 175-177)."""
        service = MockTestService("test")
        service.state = ServiceState.RUNNING
        service.health_check_interval = 0.05
        service.health_check_result = True

        monitor_task = asyncio.create_task(service.start_health_monitoring())
        await asyncio.sleep(0.15)
        service.state = ServiceState.STOPPED
        await asyncio.sleep(0.05)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Health score should have been updated
        assert service.health_score == 1.0

    @pytest.mark.asyncio
    async def test_start_health_monitoring_logs_failure(self):
        """Test health monitoring logs when health check fails (lines 179-184)."""
        service = MockTestService("test")
        service.state = ServiceState.RUNNING
        service.health_check_interval = 0.05
        service.health_check_result = False

        monitor_task = asyncio.create_task(service.start_health_monitoring())
        await asyncio.sleep(0.15)
        service.state = ServiceState.STOPPED
        await asyncio.sleep(0.05)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_health_monitoring_exception_handling(self):
        """Test health monitoring handles exceptions (lines 191-195)."""
        service = MockTestService("test")
        service.state = ServiceState.RUNNING
        service.health_check_interval = 0.05

        # Mock health_check to raise exception
        original_health_check = service.health_check
        call_count = 0

        async def failing_health_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Health check failed")
            return await original_health_check()

        service.health_check = failing_health_check

        monitor_task = asyncio.create_task(service.start_health_monitoring())
        await asyncio.sleep(0.15)
        service.state = ServiceState.STOPPED
        await asyncio.sleep(0.05)

        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_raises_when_open(self):
        """Test call_with_circuit_breaker raises when circuit breaker is open (lines 199-201)."""
        service = MockTestService("test")
        service.circuit_breaker_open = True
        service.circuit_breaker_last_failure = time.time()

        async def test_func():
            return "result"

        with pytest.raises(ServiceError, match="Circuit breaker is open"):
            await service.call_with_circuit_breaker(test_func)

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_success_path(self):
        """Test call_with_circuit_breaker success path (lines 204-205, 210)."""
        service = MockTestService("test")

        async def test_func():
            return "result"

        result = await service.call_with_circuit_breaker(test_func)
        assert result == "result"
        assert service.success_count > 0

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_error_path(self):
        """Test call_with_circuit_breaker error path (lines 206-208)."""
        service = MockTestService("test")

        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await service.call_with_circuit_breaker(failing_func)

        assert service.error_count > 0


class TestServiceManager:
    """Test ServiceManager operations."""

    @pytest.mark.asyncio
    async def test_register_service_success(self):
        """Test registering a service (lines 233-235)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        assert "test_service" in manager.services
        assert "test_service" in manager.service_info

    @pytest.mark.asyncio
    async def test_register_service_already_registered(self):
        """Test registering duplicate service raises error (lines 229-231)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        with pytest.raises(ServiceError, match="already registered"):
            await manager.register_service(service)

    @pytest.mark.asyncio
    async def test_unregister_service_success(self):
        """Test unregistering a service (lines 243-259)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        await manager.unregister_service("test_service")
        assert "test_service" not in manager.services
        assert "test_service" not in manager.service_info

    @pytest.mark.asyncio
    async def test_unregister_service_not_registered(self):
        """Test unregistering non-existent service raises error (lines 243-245)."""
        manager = ServiceManager()
        with pytest.raises(ServiceError, match="not registered"):
            await manager.unregister_service("nonexistent")

    @pytest.mark.asyncio
    async def test_unregister_service_stops_if_running(self):
        """Test unregistering stops service if running (lines 247-249)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        await manager.start_service("test_service")
        assert service.state == ServiceState.RUNNING
        await manager.unregister_service("test_service")
        assert service.state == ServiceState.STOPPED

    @pytest.mark.asyncio
    async def test_unregister_service_cancels_health_task(self):
        """Test unregistering cancels health check task (lines 251-254)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        await manager.start_service("test_service")
        assert "test_service" in manager.health_check_tasks
        task = manager.health_check_tasks["test_service"]
        # Wait a bit for task to be running
        await asyncio.sleep(0.1)
        await manager.unregister_service("test_service")
        assert "test_service" not in manager.health_check_tasks
        # Verify task was cancelled (lines 253-254)
        # Give it a moment to process cancellation
        await asyncio.sleep(0.05)
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_start_service_success(self):
        """Test starting a service (lines 277-286)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        await manager.start_service("test_service")
        assert service.state == ServiceState.RUNNING
        assert "test_service" in manager.health_check_tasks

    @pytest.mark.asyncio
    async def test_start_service_not_registered(self):
        """Test starting non-existent service raises error (lines 267-269)."""
        manager = ServiceManager()
        with pytest.raises(ServiceError, match="not registered"):
            await manager.start_service("nonexistent")

    @pytest.mark.asyncio
    async def test_start_service_not_stopped_state(self):
        """Test starting service in wrong state raises error (lines 273-275)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        await manager.start_service("test_service")
        # Try to start again
        with pytest.raises(ServiceError, match="not in stopped state"):
            await manager.start_service("test_service")

    @pytest.mark.asyncio
    async def test_start_service_failure_handling(self):
        """Test starting service handles failures (lines 288-292)."""
        manager = ServiceManager()
        service = MockTestService("test_service", will_fail_start=True)
        await manager.register_service(service)
        with pytest.raises(ServiceError, match="Failed to start"):
            await manager.start_service("test_service")
        assert service.state == ServiceState.ERROR

    @pytest.mark.asyncio
    async def test_stop_service_success(self):
        """Test stopping a service (lines 310-320)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        await manager.start_service("test_service")
        await manager.stop_service("test_service")
        assert service.state == ServiceState.STOPPED
        assert "test_service" not in manager.health_check_tasks

    @pytest.mark.asyncio
    async def test_stop_service_not_registered(self):
        """Test stopping non-existent service raises error (lines 300-302)."""
        manager = ServiceManager()
        with pytest.raises(ServiceError, match="not registered"):
            await manager.stop_service("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_service_not_running(self):
        """Test stopping service in wrong state raises error (lines 306-308)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        await manager.register_service(service)
        with pytest.raises(ServiceError, match="not running"):
            await manager.stop_service("test_service")

    @pytest.mark.asyncio
    async def test_stop_service_failure_handling(self):
        """Test stopping service handles failures (lines 322-326)."""
        manager = ServiceManager()
        service = MockTestService("test_service", will_fail_stop=True)
        await manager.register_service(service)
        await manager.start_service("test_service")
        with pytest.raises(ServiceError, match="Failed to stop"):
            await manager.stop_service("test_service")
        assert service.state == ServiceState.ERROR

    def test_get_service_exists(self):
        """Test getting existing service (line 330)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        # Note: Must use asyncio.run for async register in sync test
        asyncio.run(manager.register_service(service))
        result = manager.get_service("test_service")
        assert result == service

    def test_get_service_not_exists(self):
        """Test getting non-existent service returns None (line 330)."""
        manager = ServiceManager()
        result = manager.get_service("nonexistent")
        assert result is None

    def test_get_service_info_exists(self):
        """Test getting existing service info (line 334)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        asyncio.run(manager.register_service(service))
        info = manager.get_service_info("test_service")
        assert info is not None
        assert info.name == "test_service"

    def test_get_service_info_not_exists(self):
        """Test getting non-existent service info returns None (line 334)."""
        manager = ServiceManager()
        info = manager.get_service_info("nonexistent")
        assert info is None

    def test_list_services(self):
        """Test listing all services (line 338)."""
        manager = ServiceManager()
        service1 = MockTestService("service1")
        service2 = MockTestService("service2")
        asyncio.run(manager.register_service(service1))
        asyncio.run(manager.register_service(service2))
        services = manager.list_services()
        assert len(services) == 2
        assert {s.name for s in services} == {"service1", "service2"}

    def test_get_healthy_services(self):
        """Test getting healthy services (line 342)."""
        manager = ServiceManager()
        service1 = MockTestService("service1")
        service2 = MockTestService("service2")
        asyncio.run(manager.register_service(service1))
        asyncio.run(manager.register_service(service2))
        # Set health scores and update service info
        service1.health_score = 0.8  # Healthy
        service2.health_score = 0.3  # Unhealthy
        manager.service_info["service1"] = service1.get_info()
        manager.service_info["service2"] = service2.get_info()
        healthy = manager.get_healthy_services()
        assert len(healthy) == 1
        assert healthy[0].name == "service1"

    def test_get_service_dependencies_exists(self):
        """Test getting service dependencies when service exists (lines 346-347)."""
        manager = ServiceManager()
        service = MockTestService("test_service")
        service.add_dependency("dep1")
        service.add_dependency("dep2")
        asyncio.run(manager.register_service(service))
        deps = manager.get_service_dependencies("test_service")
        assert len(deps) == 2
        assert "dep1" in deps
        assert "dep2" in deps

    def test_get_service_dependencies_not_exists(self):
        """Test getting dependencies for non-existent service (line 348)."""
        manager = ServiceManager()
        deps = manager.get_service_dependencies("nonexistent")
        assert deps == []

    @pytest.mark.asyncio
    async def test_shutdown_stops_all_running_services(self):
        """Test shutdown stops all running services (lines 354-358)."""
        manager = ServiceManager()
        service1 = MockTestService("service1")
        service2 = MockTestService("service2")
        await manager.register_service(service1)
        await manager.register_service(service2)
        await manager.start_service("service1")
        await manager.start_service("service2")
        assert service1.state == ServiceState.RUNNING
        assert service2.state == ServiceState.RUNNING
        await manager.shutdown()
        assert service1.state == ServiceState.STOPPED
        assert service2.state == ServiceState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_handles_exceptions(self):
        """Test shutdown handles exceptions during stop (lines 359-363)."""
        manager = ServiceManager()
        service = MockTestService("service1", will_fail_stop=True)
        await manager.register_service(service)
        await manager.start_service("service1")
        # Shutdown should handle exception gracefully
        await manager.shutdown()
        # Service should be in error state
        assert service.state == ServiceState.ERROR


class TestGlobalServiceManager:
    """Test global service manager functions."""

    def test_get_service_manager_singleton(self):
        """Test get_service_manager returns singleton (lines 375-377)."""
        # Reset global state by importing fresh
        import ccbt.services.base as base_module
        base_module._service_manager = None

        manager1 = get_service_manager()
        manager2 = get_service_manager()
        assert manager1 is manager2
        assert isinstance(manager1, ServiceManager)

