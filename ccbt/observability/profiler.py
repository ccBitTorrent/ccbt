"""Performance Profiler for ccBitTorrent.

Provides comprehensive performance profiling including:
- Function-level profiling
- Async operation profiling
- Memory usage profiling
- I/O operation profiling
- Performance bottleneck detection
"""

import asyncio
import cProfile
import functools
import io
import pstats
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..events import Event, EventType, emit_event


class ProfileType(Enum):
    """Profile types."""
    FUNCTION = "function"
    ASYNC = "async"
    MEMORY = "memory"
    IO = "io"
    CUSTOM = "custom"


@dataclass
class ProfileEntry:
    """Profile entry."""
    function_name: str
    module_name: str
    start_time: float
    end_time: float
    duration: float
    memory_usage: int
    call_count: int
    profile_type: ProfileType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileReport:
    """Profile report."""
    total_duration: float
    total_memory: int
    function_count: int
    entries: List[ProfileEntry]
    bottlenecks: List[ProfileEntry]
    recommendations: List[str]


class Profiler:
    """Performance profiler."""

    def __init__(self):
        self.profile_entries: deque = deque(maxlen=10000)
        self.active_profiles: Dict[str, ProfileEntry] = {}
        self.profile_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Configuration
        self.enabled = False
        self.min_duration = 0.001  # 1ms minimum
        self.max_entries = 10000

        # Statistics
        self.stats = {
            "profiles_started": 0,
            "profiles_completed": 0,
            "total_duration": 0.0,
            "total_memory": 0,
            "bottlenecks_detected": 0,
        }

        # Thread-local storage
        self._local = threading.local()

    def start(self) -> None:
        """Start profiling."""
        self.enabled = True

        # Emit profiling started event
        asyncio.create_task(emit_event(Event(
            event_type=EventType.PROFILING_STARTED.value,
            data={
                "timestamp": time.time(),
            },
        )))

    def stop(self) -> None:
        """Stop profiling."""
        self.enabled = False

        # Complete all active profiles
        for profile_id in list(self.active_profiles.keys()):
            self.end_profile(profile_id)

        # Emit profiling stopped event
        asyncio.create_task(emit_event(Event(
            event_type=EventType.PROFILING_STOPPED.value,
            data={
                "timestamp": time.time(),
            },
        )))

    def start_profile(self, function_name: str, module_name: str = "",
                     profile_type: ProfileType = ProfileType.FUNCTION,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start profiling a function."""
        if not self.enabled:
            return ""

        profile_id = f"{function_name}_{int(time.time() * 1000000)}"

        # Get memory usage
        memory_usage = self._get_memory_usage()

        # Create profile entry
        entry = ProfileEntry(
            function_name=function_name,
            module_name=module_name,
            start_time=time.time(),
            end_time=0.0,
            duration=0.0,
            memory_usage=memory_usage,
            call_count=1,
            profile_type=profile_type,
            metadata=metadata or {},
        )

        self.active_profiles[profile_id] = entry
        self.stats["profiles_started"] += 1

        return profile_id

    def end_profile(self, profile_id: str) -> Optional[ProfileEntry]:
        """End profiling a function."""
        if profile_id not in self.active_profiles:
            return None

        entry = self.active_profiles[profile_id]
        entry.end_time = time.time()
        entry.duration = entry.end_time - entry.start_time

        # Only keep profiles above minimum duration
        if entry.duration >= self.min_duration:
            self.profile_entries.append(entry)

            # Update statistics
            self.stats["profiles_completed"] += 1
            self.stats["total_duration"] += entry.duration
            self.stats["total_memory"] += entry.memory_usage

            # Check for bottlenecks
            if self._is_bottleneck(entry):
                self.stats["bottlenecks_detected"] += 1

                # Emit bottleneck detected event
                asyncio.create_task(emit_event(Event(
                    event_type=EventType.BOTTLENECK_DETECTED.value,
                    data={
                        "function_name": entry.function_name,
                        "module_name": entry.module_name,
                        "duration": entry.duration,
                        "memory_usage": entry.memory_usage,
                        "timestamp": entry.end_time,
                    },
                )))

        del self.active_profiles[profile_id]
        return entry

    def profile_function(self, function_name: Optional[str] = None,
                        module_name: Optional[str] = None,
                        profile_type: ProfileType = ProfileType.FUNCTION):
        """Decorator for profiling functions."""
        def decorator(func):
            name = function_name or func.__name__
            module = module_name or func.__module__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                profile_id = self.start_profile(name, module, profile_type)
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    if profile_id:
                        self.end_profile(profile_id)

            return wrapper
        return decorator

    def profile_async_function(self, function_name: Optional[str] = None,
                              module_name: Optional[str] = None,
                              profile_type: ProfileType = ProfileType.ASYNC):
        """Decorator for profiling async functions."""
        def decorator(func):
            name = function_name or func.__name__
            module = module_name or func.__module__

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                profile_id = self.start_profile(name, module, profile_type)
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    if profile_id:
                        self.end_profile(profile_id)

            return wrapper
        return decorator

    def get_profile_report(self, limit: int = 100) -> ProfileReport:
        """Get profile report."""
        # Get recent entries
        recent_entries = list(self.profile_entries)[-limit:]

        # Calculate totals
        total_duration = sum(entry.duration for entry in recent_entries)
        total_memory = sum(entry.memory_usage for entry in recent_entries)
        function_count = len(set(entry.function_name for entry in recent_entries))

        # Find bottlenecks (top 10% by duration)
        sorted_entries = sorted(recent_entries, key=lambda x: x.duration, reverse=True)
        bottleneck_count = max(1, len(sorted_entries) // 10)
        bottlenecks = sorted_entries[:bottleneck_count]

        # Generate recommendations
        recommendations = self._generate_recommendations(recent_entries, bottlenecks)

        return ProfileReport(
            total_duration=total_duration,
            total_memory=total_memory,
            function_count=function_count,
            entries=recent_entries,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
        )

    def get_function_stats(self, function_name: str) -> Dict[str, Any]:
        """Get statistics for a specific function."""
        function_entries = [entry for entry in self.profile_entries
                           if entry.function_name == function_name]

        if not function_entries:
            return {}

        durations = [entry.duration for entry in function_entries]
        memory_usage = [entry.memory_usage for entry in function_entries]

        return {
            "function_name": function_name,
            "call_count": len(function_entries),
            "total_duration": sum(durations),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "total_memory": sum(memory_usage),
            "avg_memory": sum(memory_usage) / len(memory_usage),
            "min_memory": min(memory_usage),
            "max_memory": max(memory_usage),
        }

    def get_top_functions(self, limit: int = 10, sort_by: str = "duration") -> List[Dict[str, Any]]:
        """Get top functions by specified metric."""
        function_stats = defaultdict(lambda: {
            "function_name": "",
            "call_count": 0,
            "total_duration": 0.0,
            "total_memory": 0,
        })

        # Aggregate stats by function
        for entry in self.profile_entries:
            stats = function_stats[entry.function_name]
            stats["function_name"] = entry.function_name
            stats["call_count"] += 1
            stats["total_duration"] += entry.duration
            stats["total_memory"] += entry.memory_usage

        # Sort by specified metric
        sorted_functions = sorted(
            function_stats.values(),
            key=lambda x: x.get(sort_by, 0),
            reverse=True,
        )

        return sorted_functions[:limit]

    def get_profiler_statistics(self) -> Dict[str, Any]:
        """Get profiler statistics."""
        return {
            "enabled": self.enabled,
            "profiles_started": self.stats["profiles_started"],
            "profiles_completed": self.stats["profiles_completed"],
            "total_duration": self.stats["total_duration"],
            "total_memory": self.stats["total_memory"],
            "bottlenecks_detected": self.stats["bottlenecks_detected"],
            "active_profiles": len(self.active_profiles),
            "profile_entries": len(self.profile_entries),
            "min_duration": self.min_duration,
        }

    def cleanup_old_entries(self, max_age_seconds: int = 3600) -> None:
        """Clean up old profile entries."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Remove old entries
        while self.profile_entries and self.profile_entries[0].start_time < cutoff_time:
            self.profile_entries.popleft()

    def _get_memory_usage(self) -> int:
        """Get current memory usage."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return 0

    def _is_bottleneck(self, entry: ProfileEntry) -> bool:
        """Check if entry represents a bottleneck."""
        # Simple bottleneck detection based on duration
        # In production, this would be more sophisticated
        return entry.duration > 1.0  # 1 second threshold

    def _generate_recommendations(self, entries: List[ProfileEntry],
                                bottlenecks: List[ProfileEntry]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []

        if not entries:
            return recommendations

        # Analyze duration patterns
        durations = [entry.duration for entry in entries]
        avg_duration = sum(durations) / len(durations)

        if avg_duration > 0.1:  # 100ms average
            recommendations.append("Consider optimizing slow functions")

        # Analyze memory usage
        memory_usage = [entry.memory_usage for entry in entries]
        avg_memory = sum(memory_usage) / len(memory_usage)

        if avg_memory > 10 * 1024 * 1024:  # 10MB average
            recommendations.append("Consider optimizing memory usage")

        # Analyze bottlenecks
        if bottlenecks:
            bottleneck_functions = [b.function_name for b in bottlenecks]
            recommendations.append(f"Focus on optimizing: {', '.join(bottleneck_functions)}")

        return recommendations


class CPROfiler:
    """cProfile-based profiler."""

    def __init__(self):
        self.profiler = cProfile.Profile()
        self.enabled = False

    def start(self) -> None:
        """Start cProfile profiling."""
        self.profiler.enable()
        self.enabled = True

    def stop(self) -> None:
        """Stop cProfile profiling."""
        self.profiler.disable()
        self.enabled = False

    def get_stats(self) -> str:
        """Get profiling statistics."""
        if not self.enabled:
            return ""

        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s)
        ps.sort_stats("cumulative")
        ps.print_stats()

        return s.getvalue()

    def get_stats_dict(self) -> Dict[str, Any]:
        """Get profiling statistics as dictionary."""
        if not self.enabled:
            return {}

        stats = pstats.Stats(self.profiler)
        return {
            "total_calls": stats.total_calls,
            "primitive_calls": stats.prim_calls,
            "total_time": stats.total_tt,
            "cumulative_time": stats.total_cumtime,
        }
