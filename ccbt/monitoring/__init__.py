"""Advanced monitoring for ccBitTorrent.

from __future__ import annotations

Provides comprehensive monitoring including:
- Custom metrics collection
- Alert rule engine
- Metric aggregation
- OpenTelemetry support
- Distributed tracing
"""

from __future__ import annotations

from ccbt.monitoring.alert_manager import AlertManager
from ccbt.monitoring.dashboard import DashboardManager
from ccbt.monitoring.metrics_collector import MetricsCollector
from ccbt.monitoring.tracing import TracingManager

__all__ = [
    "AlertManager",
    "DashboardManager",
    "MetricsCollector",
    "TracingManager",
    "get_alert_manager",
    "get_metrics_collector",
    "init_metrics",
    "reset_metrics_collector",
    "shutdown_metrics",
]

# Global alert manager singleton for CLI/UI integration
_GLOBAL_ALERT_MANAGER: AlertManager | None = None

# Global metrics collector singleton for CLI/UI integration
_GLOBAL_METRICS_COLLECTOR: MetricsCollector | None = None


def get_alert_manager() -> AlertManager:
    """Return a process-global AlertManager to share rules/alerts across components."""
    global _GLOBAL_ALERT_MANAGER
    if _GLOBAL_ALERT_MANAGER is None:
        _GLOBAL_ALERT_MANAGER = AlertManager()
    return _GLOBAL_ALERT_MANAGER


def get_metrics_collector() -> MetricsCollector:
    """Return a process-global MetricsCollector to share metrics across components.

    Returns:
        MetricsCollector: Singleton metrics collector instance.

    Note:
        This function creates a new MetricsCollector if one doesn't exist.
        Use init_metrics() to start metrics collection based on configuration.

    """
    global _GLOBAL_METRICS_COLLECTOR
    if _GLOBAL_METRICS_COLLECTOR is None:
        _GLOBAL_METRICS_COLLECTOR = MetricsCollector()
    return _GLOBAL_METRICS_COLLECTOR


async def init_metrics() -> MetricsCollector | None:
    """Initialize and start metrics collection if enabled in configuration.

    This function:
    - Gets or creates the global MetricsCollector singleton
    - Checks config.observability.enable_metrics flag
    - Configures collection interval from config
    - Starts the metrics collection loop
    - Handles errors gracefully (logs warnings, doesn't raise)

    Returns:
        MetricsCollector | None: MetricsCollector instance if enabled and started,
            None if metrics are disabled or initialization failed.

    Example:
        ```python
        metrics = await init_metrics()
        if metrics:
            # Metrics collection is active
            pass
        ```

    """
    import asyncio
    import logging

    from ccbt.utils.logging_config import get_logger

    logger = get_logger(__name__)

    try:
        from ccbt.config.config import get_config

        config = get_config()

        # Check if metrics are enabled
        # Handle AttributeError if config.observability is missing
        # Wrap all observability access in try-except to handle PropertyMock side_effect
        try:
            # First check if observability attribute exists
            # Use try-except to handle AttributeError from PropertyMock or missing attributes
            try:
                observability = config.observability
            except AttributeError:
                logger.warning("Config missing observability attribute")
                return None

            # Also check if enable_metrics attribute exists
            try:
                enable_metrics = observability.enable_metrics
            except AttributeError:
                logger.warning("Config missing enable_metrics attribute")
                return None

            if not enable_metrics:
                logger.debug("Metrics collection disabled in configuration")
                # If singleton exists from previous test/enablement, ensure it's stopped
                # Use a timeout to prevent hanging if stop() is blocked
                global _GLOBAL_METRICS_COLLECTOR  # noqa: PLW0602
                if (
                    _GLOBAL_METRICS_COLLECTOR is not None
                    and _GLOBAL_METRICS_COLLECTOR.running
                ):
                    try:
                        await asyncio.wait_for(
                            _GLOBAL_METRICS_COLLECTOR.stop(), timeout=1.0
                        )
                    except (asyncio.TimeoutError, Exception):
                        # If stop() hangs or fails, just mark as not running
                        _GLOBAL_METRICS_COLLECTOR.running = False
                return None

            # Get or create metrics collector
            metrics_collector = get_metrics_collector()

            # Configure collection interval from config
            # Handle AttributeError if metrics_interval is missing
            try:
                metrics_collector.collection_interval = observability.metrics_interval
            except AttributeError:
                logger.warning(
                    "Config missing metrics_interval attribute, using default"
                )
                # Use default interval if not specified

            # Start metrics collection
            await metrics_collector.start()

            logger.info(
                "Metrics collection started (interval: %.1fs)",
                metrics_collector.collection_interval,
            )
            return metrics_collector
        except AttributeError as e:
            # Catch any AttributeError that might occur during observability access
            # This handles PropertyMock side_effect that might be raised at any point
            logger.warning("Config missing observability-related attribute: %s", e)
            return None
    except (
        RuntimeError
    ) as runtime_error:  # pragma: no cover - Defensive: get_config() exception
        logger.warning(
            "Failed to get configuration for metrics: %s", runtime_error, exc_info=True
        )
        return None
    except (
        Exception
    ) as e:  # pragma: no cover - Defensive: any other exception during initialization
        logger.warning("Failed to initialize metrics collection: %s", e, exc_info=True)
        return None


async def shutdown_metrics() -> None:
    """Gracefully shutdown metrics collection.

    This function:
    - Gets the global MetricsCollector singleton
    - Stops the metrics collection loop if running
    - Handles errors gracefully (logs warnings, doesn't raise)

    Note:
        This function is safe to call multiple times or when metrics
        are not running. It will perform a no-op in those cases.

    Example:
        ```python
        await shutdown_metrics()
        ```

    """
    import logging

    from ccbt.utils.logging_config import get_logger

    logger = get_logger(__name__)

    try:
        global _GLOBAL_METRICS_COLLECTOR  # noqa: PLW0602

        if _GLOBAL_METRICS_COLLECTOR is None:
            logger.debug("Metrics collector not initialized, skipping shutdown")
            return

        # Check if running before stopping
        if not _GLOBAL_METRICS_COLLECTOR.running:
            logger.debug("Metrics collector not running, skipping shutdown")
            return

        # Stop metrics collection
        try:
            await _GLOBAL_METRICS_COLLECTOR.stop()
            logger.info("Metrics collection stopped")
        except (
            Exception
        ) as stop_error:  # pragma: no cover - Defensive: stop() exception handling
            logger.warning(
                "Error during metrics shutdown: %s", stop_error, exc_info=True
            )

        # Optional: Reset singleton for clean shutdown
        # _GLOBAL_METRICS_COLLECTOR = None

    except Exception as e:  # pragma: no cover - Defensive: shutdown exception handler
        logger.warning("Failed to shutdown metrics collection: %s", e, exc_info=True)


def reset_metrics_collector() -> None:
    """Reset global metrics collector (for testing)."""
    global _GLOBAL_METRICS_COLLECTOR
    if _GLOBAL_METRICS_COLLECTOR is not None:
        # Stop is async, but this is for testing cleanup
        # In practice, tests should call shutdown_metrics() first
        import asyncio

        # Try to stop synchronously if possible
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                # Loop exists but not running, can use run_until_complete
                try:
                    loop.run_until_complete(_GLOBAL_METRICS_COLLECTOR.stop())
                except RuntimeError:
                    # Loop might be closed, create new one
                    new_loop = asyncio.new_event_loop()
                    try:
                        new_loop.run_until_complete(_GLOBAL_METRICS_COLLECTOR.stop())
                    finally:
                        new_loop.close()
            else:
                # Loop is running, schedule stop but don't wait
                # The fixture should handle this properly
                pass
        except RuntimeError:
            # No event loop available, create temporary one
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(_GLOBAL_METRICS_COLLECTOR.stop())
                finally:
                    new_loop.close()
            except Exception:
                # Best effort - if we can't stop cleanly, just reset
                pass
        except Exception:
            # Any other error, just reset
            pass

        _GLOBAL_METRICS_COLLECTOR = None
