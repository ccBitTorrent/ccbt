"""Conditional configuration based on system capabilities.

This module provides functionality to apply configuration settings conditionally
based on detected system capabilities and auto-tune settings for optimal performance.
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any

from ccbt.config_capabilities import SystemCapabilities

if TYPE_CHECKING:
    from ccbt.models import Config

logger = logging.getLogger(__name__)


class ConditionalConfig:
    """Applies conditional configuration based on system capabilities."""

    def __init__(self, capabilities: SystemCapabilities | None = None):
        """Initialize conditional configuration.

        Args:
            capabilities: System capabilities detector (creates new if None)
        """
        self.capabilities = capabilities or SystemCapabilities()

    def apply_conditional_config(self, config: Config) -> tuple[Config, list[str]]:
        """Apply conditional configuration based on system capabilities.

        Args:
            config: Base configuration to modify

        Returns:
            Tuple of (modified_config, warnings)
        """
        warnings = []
        modified_config = copy.deepcopy(config)

        # Apply conditional settings based on capabilities
        warnings.extend(self._apply_io_optimizations(modified_config))
        warnings.extend(self._apply_memory_optimizations(modified_config))
        warnings.extend(self._apply_network_optimizations(modified_config))
        warnings.extend(self._apply_cpu_optimizations(modified_config))
        warnings.extend(self._apply_security_optimizations(modified_config))
        warnings.extend(self._apply_disk_optimizations(modified_config))

        return modified_config, warnings

    def _apply_io_optimizations(self, config: Config) -> list[str]:
        """Apply I/O optimizations based on system capabilities.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []

        # Enable io_uring if available
        if self.capabilities.detect_io_uring():
            if not config.disk.enable_io_uring:
                config.disk.enable_io_uring = True
                logger.info("Enabled io_uring for improved I/O performance")
        elif config.disk.enable_io_uring:
            config.disk.enable_io_uring = False
            warnings.append("io_uring not supported on this system, disabled")

        # Enable memory mapping if available
        if self.capabilities.detect_mmap():
            if not config.disk.use_mmap:
                config.disk.use_mmap = True
                logger.info("Enabled memory mapping for improved I/O performance")
        elif config.disk.use_mmap:
            config.disk.use_mmap = False
            warnings.append("Memory mapping not supported on this system, disabled")

        return warnings

    def _apply_memory_optimizations(self, config: Config) -> list[str]:
        """Apply memory optimizations based on available memory.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []
        memory_info = self.capabilities.detect_memory()
        total_gb = memory_info["total_gb"]

        # Adjust read-ahead buffer based on available memory
        if total_gb >= 16:
            # High memory system - can use larger buffers
            if config.disk.read_ahead_kib < 1024:
                config.disk.read_ahead_kib = 1024
                logger.info("Increased read-ahead buffer for high-memory system")
        elif total_gb >= 8:
            # Medium memory system - moderate buffers
            if config.disk.read_ahead_kib > 512:
                config.disk.read_ahead_kib = 512
                logger.info("Adjusted read-ahead buffer for medium-memory system")
        # Low memory system - conservative buffers
        elif config.disk.read_ahead_kib > 256:
            config.disk.read_ahead_kib = 256
            warnings.append("Reduced read-ahead buffer for low-memory system")

        # Adjust cache size based on available memory
        if total_gb >= 16:
            # High memory system - can cache more pieces
            if config.disk.cache_size_mb < 1024:
                config.disk.cache_size_mb = 1024
                logger.info("Increased cache size for high-memory system")
        elif total_gb >= 8:
            # Medium memory system - moderate cache
            if config.disk.cache_size_mb > 512:
                config.disk.cache_size_mb = 512
                logger.info("Adjusted cache size for medium-memory system")
        # Low memory system - conservative cache
        elif config.disk.cache_size_mb > 128:
            config.disk.cache_size_mb = 128
            warnings.append("Reduced cache size for low-memory system")

        return warnings

    def _apply_network_optimizations(self, config: Config) -> list[str]:
        """Apply network optimizations based on system capabilities.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []

        # Disable IPv6 if not supported
        if not self.capabilities.detect_ipv6() and config.network.enable_ipv6:
            config.network.enable_ipv6 = False
            warnings.append("IPv6 not supported on this system, disabled")

        # Adjust connection limits based on network interfaces
        interfaces = self.capabilities.detect_network_interfaces()
        active_interfaces = [iface for iface in interfaces if not iface["is_loopback"]]

        if len(active_interfaces) == 0:
            # No active interfaces - reduce connection limits
            if config.network.max_global_peers > 50:
                config.network.max_global_peers = 50
                warnings.append(
                    "Reduced connection limit due to no active network interfaces"
                )
        elif len(active_interfaces) == 1:
            # Single interface - moderate connection limits
            if config.network.max_global_peers > 200:
                config.network.max_global_peers = 200
                logger.info("Adjusted connection limit for single network interface")
        # Multiple interfaces - can use higher connection limits
        elif config.network.max_global_peers < 300:
            config.network.max_global_peers = 300
            logger.info("Increased connection limit for multiple network interfaces")

        return warnings

    def _apply_cpu_optimizations(self, config: Config) -> list[str]:
        """Apply CPU optimizations based on CPU capabilities.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []
        cpu_count = self.capabilities.detect_cpu_count()
        cpu_features = self.capabilities.detect_cpu_features()

        # Adjust worker counts based on CPU cores
        if cpu_count >= 8:
            # High core count - can use more workers
            if config.disk.hash_workers < 8:
                config.disk.hash_workers = min(8, cpu_count)
                logger.info("Increased hash workers for high-core system")
            if config.disk.disk_workers < 4:
                config.disk.disk_workers = min(4, cpu_count // 2)
                logger.info("Increased disk workers for high-core system")
        elif cpu_count >= 4:
            # Medium core count - moderate workers
            if config.disk.hash_workers > 4:
                config.disk.hash_workers = min(4, cpu_count)
                logger.info("Adjusted hash workers for medium-core system")
            if config.disk.disk_workers > 2:
                config.disk.disk_workers = min(2, cpu_count // 2)
                logger.info("Adjusted disk workers for medium-core system")
        else:
            # Low core count - conservative workers
            if config.disk.hash_workers > 2:
                config.disk.hash_workers = min(2, cpu_count)
                warnings.append("Reduced hash workers for low-core system")
            if config.disk.disk_workers > 1:
                config.disk.disk_workers = min(1, cpu_count)
                warnings.append("Reduced disk workers for low-core system")

        # Enable SIMD optimizations if available
        if cpu_features.get("avx2", False):
            logger.info(
                "AVX2 support detected - hash verification will use SIMD optimizations"
            )
        elif cpu_features.get("avx", False):
            logger.info(
                "AVX support detected - hash verification will use SIMD optimizations"
            )
        elif cpu_features.get("sse4", False):
            logger.info(
                "SSE4 support detected - hash verification will use SIMD optimizations"
            )

        return warnings

    def _apply_security_optimizations(self, config: Config) -> list[str]:
        """Apply security optimizations based on system capabilities.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []

        # Disable encryption if not supported
        if (
            not self.capabilities.detect_encryption()
            and config.security.enable_encryption
        ):
            config.security.enable_encryption = False
            warnings.append("Encryption not supported on this system, disabled")

        return warnings

    def _apply_disk_optimizations(self, config: Config) -> list[str]:
        """Apply disk optimizations based on available disk space.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []
        disk_info = self.capabilities.detect_disk_space()
        free_gb = disk_info["free_gb"]

        # Adjust disk usage based on available space
        if free_gb < 1:
            # Very low disk space - disable disk-intensive features
            if config.disk.cache_size_mb > 64:
                config.disk.cache_size_mb = 64
                warnings.append("Reduced cache size due to low disk space")
        elif free_gb < 5:
            # Low disk space - conservative settings
            if config.disk.cache_size_mb > 128:
                config.disk.cache_size_mb = 128
                warnings.append("Reduced cache size due to limited disk space")
        elif free_gb > 100 and config.disk.cache_size_mb < 512:
            # High disk space - can use more aggressive settings
            config.disk.cache_size_mb = 512
            logger.info("Increased cache size for high-disk-space system")

        return warnings

    def adjust_for_system(self, config: Config) -> tuple[Config, list[str]]:
        """Auto-tune configuration settings for the current system.

        Args:
            config: Base configuration to tune

        Returns:
            Tuple of (tuned_config, warnings)
        """
        warnings = []
        tuned_config = copy.deepcopy(config)

        # Apply system-specific optimizations
        warnings.extend(self._apply_io_optimizations(tuned_config))
        warnings.extend(self._apply_memory_optimizations(tuned_config))
        warnings.extend(self._apply_network_optimizations(tuned_config))
        warnings.extend(self._apply_cpu_optimizations(tuned_config))
        warnings.extend(self._apply_security_optimizations(tuned_config))
        warnings.extend(self._apply_disk_optimizations(tuned_config))

        # Apply additional auto-tuning rules
        warnings.extend(self._auto_tune_peer_limits(tuned_config))
        warnings.extend(self._auto_tune_timeouts(tuned_config))
        warnings.extend(self._auto_tune_buffers(tuned_config))

        return tuned_config, warnings

    def _auto_tune_peer_limits(self, config: Config) -> list[str]:
        """Auto-tune peer connection limits based on system resources.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []
        memory_info = self.capabilities.detect_memory()
        cpu_count = self.capabilities.detect_cpu_count()
        total_gb = memory_info["total_gb"]

        # Calculate optimal peer limits based on system resources
        if total_gb >= 16 and cpu_count >= 8:
            # High-end system
            optimal_max_peers = min(500, total_gb * 20)
            optimal_max_peers_per_torrent = min(50, optimal_max_peers // 10)
        elif total_gb >= 8 and cpu_count >= 4:
            # Mid-range system
            optimal_max_peers = min(200, total_gb * 15)
            optimal_max_peers_per_torrent = min(30, optimal_max_peers // 8)
        else:
            # Low-end system
            optimal_max_peers = min(100, total_gb * 10)
            optimal_max_peers_per_torrent = min(20, optimal_max_peers // 6)

        # Apply optimal limits if they're better than current
        if config.network.max_global_peers != optimal_max_peers:
            config.network.max_global_peers = optimal_max_peers
            logger.info("Auto-tuned max global peers to %s", optimal_max_peers)

        if config.network.max_peers_per_torrent != optimal_max_peers_per_torrent:
            config.network.max_peers_per_torrent = optimal_max_peers_per_torrent
            logger.info(
                "Auto-tuned max peers per torrent to %s", optimal_max_peers_per_torrent
            )

        return warnings

    def _auto_tune_timeouts(self, config: Config) -> list[str]:
        """Auto-tune timeout values based on system performance.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []
        cpu_count = self.capabilities.detect_cpu_count()

        # Adjust timeouts based on CPU performance
        if cpu_count >= 8:
            # High-performance system - can use shorter timeouts
            if config.network.peer_timeout > 30:
                config.network.peer_timeout = 30
                logger.info("Reduced peer timeout for high-performance system")
        elif cpu_count >= 4:
            # Medium-performance system - moderate timeouts
            if config.network.peer_timeout > 60:
                config.network.peer_timeout = 60
                logger.info("Adjusted peer timeout for medium-performance system")
        # Low-performance system - longer timeouts
        elif config.network.peer_timeout < 90:
            config.network.peer_timeout = 90
            logger.info("Increased peer timeout for low-performance system")

        return warnings

    def _auto_tune_buffers(self, config: Config) -> list[str]:
        """Auto-tune buffer sizes based on system capabilities.

        Args:
            config: Configuration to modify

        Returns:
            List of warnings
        """
        warnings = []
        memory_info = self.capabilities.detect_memory()
        total_gb = memory_info["total_gb"]

        # Adjust buffer sizes based on available memory
        if total_gb >= 16:
            # High memory system - larger buffers
            if config.network.socket_sndbuf_kib < 1024:
                config.network.socket_sndbuf_kib = 1024
                logger.info("Increased send buffer for high-memory system")
            if config.network.socket_rcvbuf_kib < 1024:
                config.network.socket_rcvbuf_kib = 1024
                logger.info("Increased receive buffer for high-memory system")
        elif total_gb >= 8:
            # Medium memory system - moderate buffers
            if config.network.socket_sndbuf_kib > 512:
                config.network.socket_sndbuf_kib = 512
                logger.info("Adjusted send buffer for medium-memory system")
            if config.network.socket_rcvbuf_kib > 512:
                config.network.socket_rcvbuf_kib = 512
                logger.info("Adjusted receive buffer for medium-memory system")
        else:
            # Low memory system - smaller buffers
            if config.network.socket_sndbuf_kib > 256:
                config.network.socket_sndbuf_kib = 256
                warnings.append("Reduced send buffer for low-memory system")
            if config.network.socket_rcvbuf_kib > 256:
                config.network.socket_rcvbuf_kib = 256
                warnings.append("Reduced receive buffer for low-memory system")

        return warnings

    def validate_against_system(self, config: Config) -> tuple[bool, list[str]]:
        """Validate configuration against system capabilities.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, warnings)
        """
        warnings = []
        is_valid = True

        # Check I/O capabilities
        if config.disk.enable_io_uring and not self.capabilities.detect_io_uring():
            warnings.append("io_uring is enabled but not supported on this system")
            is_valid = False

        if config.disk.use_mmap and not self.capabilities.detect_mmap():
            warnings.append(
                "Memory mapping is enabled but not supported on this system"
            )
            is_valid = False

        # Check network capabilities
        if config.network.enable_ipv6 and not self.capabilities.detect_ipv6():
            warnings.append("IPv6 is enabled but not supported on this system")
            is_valid = False

        # Check security capabilities
        if (
            config.security.enable_encryption
            and not self.capabilities.detect_encryption()
        ):
            warnings.append("Encryption is enabled but not supported on this system")
            is_valid = False

        # Check resource requirements
        memory_info = self.capabilities.detect_memory()
        total_gb = memory_info["total_gb"]

        # Check if cache is too large for available memory
        cache_size_mb = config.disk.cache_size_mb
        if cache_size_mb > total_gb * 1024 * 0.1:  # More than 10% of total memory
            warnings.append(
                f"Cache size ({cache_size_mb}MB) may be too large for available memory ({total_gb:.1f}GB)"
            )

        # Check CPU requirements
        cpu_count = self.capabilities.detect_cpu_count()
        if config.disk.hash_workers > cpu_count * 2:
            warnings.append(
                f"Hash workers ({config.disk.hash_workers}) exceeds recommended limit (CPU cores * 2 = {cpu_count * 2})"
            )

        if config.disk.disk_workers > cpu_count:
            warnings.append(
                f"Disk workers ({config.disk.disk_workers}) exceeds recommended limit (CPU cores = {cpu_count})"
            )

        return is_valid, warnings

    def get_system_recommendations(self) -> dict[str, Any]:
        """Get system-specific configuration recommendations.

        Returns:
            Dictionary with recommendations
        """
        capabilities = self.capabilities.get_all_capabilities()
        return {
            "io_optimizations": {
                "use_io_uring": capabilities["io_uring"],
                "use_mmap": capabilities["mmap"],
            },
            "network_optimizations": {
                "enable_ipv6": capabilities["ipv6"],
                "max_connections": self._recommend_max_connections(),
            },
            "cpu_optimizations": {
                "hash_workers": self._recommend_hash_workers(),
                "disk_workers": self._recommend_disk_workers(),
            },
            "memory_optimizations": {
                "cache_size_mb": self._recommend_cache_size(),
                "read_ahead_kib": self._recommend_read_ahead(),
            },
            "security_optimizations": {
                "enable_encryption": capabilities["encryption"],
            },
        }

    def _recommend_max_connections(self) -> int:
        """Recommend maximum connections based on system resources."""
        memory_info = self.capabilities.detect_memory()
        cpu_count = self.capabilities.detect_cpu_count()
        total_gb = memory_info["total_gb"]

        if total_gb >= 16 and cpu_count >= 8:
            return min(500, total_gb * 20)
        if total_gb >= 8 and cpu_count >= 4:
            return min(200, total_gb * 15)
        return min(100, total_gb * 10)

    def _recommend_hash_workers(self) -> int:
        """Recommend hash workers based on CPU cores."""
        cpu_count = self.capabilities.detect_cpu_count()
        return min(8, cpu_count)

    def _recommend_disk_workers(self) -> int:
        """Recommend disk workers based on CPU cores."""
        cpu_count = self.capabilities.detect_cpu_count()
        return min(4, cpu_count // 2)

    def _recommend_cache_size(self) -> int:
        """Recommend cache size based on available memory."""
        memory_info = self.capabilities.detect_memory()
        total_gb = memory_info["total_gb"]

        if total_gb >= 16:
            return 1024
        if total_gb >= 8:
            return 512
        return 128

    def _recommend_read_ahead(self) -> int:
        """Recommend read-ahead buffer size based on available memory."""
        memory_info = self.capabilities.detect_memory()
        total_gb = memory_info["total_gb"]

        if total_gb >= 16:
            return 1024
        if total_gb >= 8:
            return 512
        return 256
