"""System capability detection for conditional configuration.

This module provides functionality to detect system capabilities and features
that can be used to conditionally apply configuration settings.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from typing import Any

import psutil


class SystemCapabilities:
    """Detects system capabilities and features for conditional configuration."""

    def __init__(self, cache_ttl: int = 300):
        """Initialize system capability detector.

        Args:
            cache_ttl: Cache TTL in seconds for detection results
        """
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._platform = platform.system().lower()

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return value
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Set cached value with timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, time.time())

    def detect_io_uring(self) -> bool:
        """Detect Linux io_uring support.

        Returns:
            True if io_uring is supported, False otherwise
        """
        cached = self._get_cached("io_uring")
        if cached is not None:
            return cached

        if self._platform != "linux":
            result = False
        else:
            try:
                # Check if io_uring is available in the kernel
                with open("/proc/version") as f:
                    version = f.read()

                # Check kernel version (io_uring was added in 5.1)
                if (
                    "5.1" in version
                    or "5.2" in version
                    or "5.3" in version
                    or "5.4" in version
                ):
                    result = True
                else:
                    # Try to import io_uring module
                    try:
                        import io_uring  # noqa: F401  # type: ignore[import-untyped]

                        result = True
                    except ImportError:
                        result = False
            except OSError:
                result = False

        self._set_cached("io_uring", result)
        return result

    def detect_mmap(self) -> bool:
        """Detect memory mapping support.

        Returns:
            True if mmap is supported, False otherwise
        """
        cached = self._get_cached("mmap")
        if cached is not None:
            return cached

        try:
            import mmap  # noqa: F401

            result = True
        except ImportError:
            result = False

        self._set_cached("mmap", result)
        return result

    def detect_ipv6(self) -> bool:
        """Detect IPv6 stack availability.

        Returns:
            True if IPv6 is supported, False otherwise
        """
        cached = self._get_cached("ipv6")
        if cached is not None:
            return cached

        try:
            import socket

            # Try to create an IPv6 socket
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.close()
            result = True
        except OSError:
            result = False

        self._set_cached("ipv6", result)
        return result

    def detect_encryption(self) -> bool:
        """Detect crypto library availability.

        Returns:
            True if encryption libraries are available, False otherwise
        """
        cached = self._get_cached("encryption")
        if cached is not None:
            return cached

        try:
            import cryptography  # noqa: F401  # type: ignore[import-untyped]

            result = True
        except ImportError:
            try:
                import ssl  # noqa: F401

                result = True
            except ImportError:
                result = False

        self._set_cached("encryption", result)
        return result

    def detect_cpu_features(self) -> dict[str, bool]:
        """Detect CPU features and SIMD capabilities.

        Returns:
            Dictionary of CPU features and their availability
        """
        cached = self._get_cached("cpu_features")
        if cached is not None:
            return cached

        features = {
            "sse": False,
            "sse2": False,
            "sse3": False,
            "sse4": False,
            "avx": False,
            "avx2": False,
            "avx512": False,
            "neon": False,  # ARM
            "altivec": False,  # PowerPC
        }

        if self._platform == "linux":
            try:
                with open("/proc/cpuinfo") as f:
                    cpuinfo = f.read()

                features["sse"] = "sse" in cpuinfo.lower()
                features["sse2"] = "sse2" in cpuinfo.lower()
                features["sse3"] = "sse3" in cpuinfo.lower()
                features["sse4"] = "sse4" in cpuinfo.lower()
                features["avx"] = "avx" in cpuinfo.lower()
                features["avx2"] = "avx2" in cpuinfo.lower()
                features["avx512"] = "avx512" in cpuinfo.lower()
            except OSError:
                pass
        elif self._platform == "darwin":  # macOS
            try:
                # ruff: noqa: S607
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.features"],
                    check=False,
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    features_str = result.stdout.lower()
                    features["sse"] = "sse" in features_str
                    features["sse2"] = "sse2" in features_str
                    features["sse3"] = "sse3" in features_str
                    features["sse4"] = "sse4" in features_str
                    features["avx"] = "avx" in features_str
                    features["avx2"] = "avx2" in features_str
                    features["avx512"] = "avx512" in features_str
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
                FileNotFoundError,
            ):
                pass
        elif self._platform == "windows":
            try:
                # ruff: noqa: S607
                result = subprocess.run(
                    ["wmic", "cpu", "get", "features"],
                    check=False,
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    features_str = result.stdout.lower()
                    features["sse"] = "sse" in features_str
                    features["sse2"] = "sse2" in features_str
                    features["sse3"] = "sse3" in features_str
                    features["sse4"] = "sse4" in features_str
                    features["avx"] = "avx" in features_str
                    features["avx2"] = "avx2" in features_str
                    features["avx512"] = "avx512" in features_str
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
                FileNotFoundError,
            ):
                pass

        self._set_cached("cpu_features", features)
        return features

    def detect_memory(self) -> dict[str, int | float]:
        """Detect available memory information.

        Returns:
            Dictionary with memory information
        """
        cached = self._get_cached("memory")
        if cached is not None:
            return cached

        try:
            memory = psutil.virtual_memory()
            result = {
                "total_bytes": memory.total,
                "available_bytes": memory.available,
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent_used": memory.percent,
            }
        except Exception:
            result = {
                "total_bytes": 0,
                "available_bytes": 0,
                "total_gb": 0.0,
                "available_gb": 0.0,
                "percent_used": 100.0,
            }

        self._set_cached("memory", result)
        return result

    def detect_disk_space(self, path: str = ".") -> dict[str, int | float]:
        """Detect available disk space.

        Args:
            path: Path to check disk space for

        Returns:
            Dictionary with disk space information
        """
        cache_key = f"disk_space_{path}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            disk_usage = psutil.disk_usage(path)
            result = {
                "total_bytes": disk_usage.total,
                "used_bytes": disk_usage.used,
                "free_bytes": disk_usage.free,
                "total_gb": disk_usage.total / (1024**3),
                "used_gb": disk_usage.used / (1024**3),
                "free_gb": disk_usage.free / (1024**3),
                "percent_used": (disk_usage.used / disk_usage.total) * 100,
            }
        except Exception:
            result = {
                "total_bytes": 0,
                "used_bytes": 0,
                "free_bytes": 0,
                "total_gb": 0.0,
                "used_gb": 0.0,
                "free_gb": 0.0,
                "percent_used": 100.0,
            }

        self._set_cached(cache_key, result)
        return result

    def detect_cpu_count(self) -> int:
        """Detect number of CPU cores.

        Returns:
            Number of CPU cores
        """
        cached = self._get_cached("cpu_count")
        if cached is not None:
            return cached

        try:
            result = psutil.cpu_count()
            if result is None:
                result = 1
        except Exception:
            result = 1

        self._set_cached("cpu_count", result)
        return result

    def detect_network_interfaces(self) -> list[dict[str, Any]]:
        """Detect available network interfaces.

        Returns:
            List of network interface information
        """
        cached = self._get_cached("network_interfaces")
        if cached is not None:
            return cached

        try:
            interfaces = psutil.net_if_addrs()
            result = []
            for name, addrs in interfaces.items():
                interface_info = {
                    "name": name,
                    "addresses": [],
                    "is_loopback": False,
                    "is_wireless": False,
                }

                for addr in addrs:
                    addr_info = {
                        "family": addr.family.name
                        if hasattr(addr.family, "name")
                        else str(addr.family),
                        "address": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast,
                    }
                    addresses = interface_info.get("addresses", [])
                    if isinstance(addresses, list):
                        addresses.append(addr_info)

                    if addr.family == psutil.AF_LINK:  # MAC address
                        interface_info["mac_address"] = addr.address
                    elif addr.family == 2:  # AF_INET (IPv4)
                        interface_info["ipv4_address"] = addr.address
                    elif addr.family == 23:  # AF_INET6 (IPv6)
                        interface_info["ipv6_address"] = addr.address

                # Check if it's a loopback interface
                if name.lower() in ["lo", "loopback", "lo0"]:
                    interface_info["is_loopback"] = True

                # Check if it's a wireless interface (heuristic)
                if any(
                    keyword in name.lower()
                    for keyword in ["wlan", "wifi", "wireless", "wlp"]
                ):
                    interface_info["is_wireless"] = True

                result.append(interface_info)
        except Exception:
            result = []

        self._set_cached("network_interfaces", result)
        return result

    def detect_platform_specific(self) -> dict[str, Any]:
        """Detect platform-specific capabilities.

        Returns:
            Dictionary with platform-specific information
        """
        cached = self._get_cached("platform_specific")
        if cached is not None:
            return cached

        result = {
            "platform": self._platform,
            "architecture": platform.machine(),
            "python_version": sys.version,
            "python_implementation": platform.python_implementation(),
        }

        if self._platform == "linux":
            try:
                with open("/etc/os-release") as f:
                    os_release = f.read()
                result["os_release"] = os_release
            except OSError:
                result["os_release"] = "unknown"
        elif self._platform == "darwin":
            try:
                result["macos_version"] = platform.mac_ver()[0]
            except Exception:
                result["macos_version"] = "unknown"
        elif self._platform == "windows":
            try:
                result["windows_version"] = platform.win32_ver()[0]
            except Exception:
                result["windows_version"] = "unknown"

        self._set_cached("platform_specific", result)
        return result

    def get_all_capabilities(self) -> dict[str, Any]:
        """Get all detected system capabilities.

        Returns:
            Dictionary with all capability information
        """
        return {
            "io_uring": self.detect_io_uring(),
            "mmap": self.detect_mmap(),
            "ipv6": self.detect_ipv6(),
            "encryption": self.detect_encryption(),
            "cpu_features": self.detect_cpu_features(),
            "memory": self.detect_memory(),
            "disk_space": self.detect_disk_space(),
            "cpu_count": self.detect_cpu_count(),
            "network_interfaces": self.detect_network_interfaces(),
            "platform_specific": self.detect_platform_specific(),
        }

    def clear_cache(self) -> None:
        """Clear all cached detection results."""
        self._cache.clear()

    def is_capability_supported(self, capability: str) -> bool:
        """Check if a specific capability is supported.

        Args:
            capability: Capability name to check

        Returns:
            True if capability is supported, False otherwise
        """
        capabilities = self.get_all_capabilities()
        return capabilities.get(capability, False)

    def get_capability_summary(self) -> dict[str, bool]:
        """Get a summary of key capabilities.

        Returns:
            Dictionary with key capabilities and their support status
        """
        return {
            "io_uring": self.detect_io_uring(),
            "mmap": self.detect_mmap(),
            "ipv6": self.detect_ipv6(),
            "encryption": self.detect_encryption(),
            "sse": self.detect_cpu_features().get("sse", False),
            "avx": self.detect_cpu_features().get("avx", False),
            "avx2": self.detect_cpu_features().get("avx2", False),
        }
