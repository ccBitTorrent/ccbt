"""Tests for observability profiler."""

import pytest
import time
import threading
from unittest.mock import AsyncMock, MagicMock, patch

from ccbt.observability.profiler import (
    CPROfiler,
    ProfileEntry,
    ProfileReport,
    ProfileType,
    Profiler,
)


class TestProfiler:
    """Test cases for Profiler."""

    @pytest.fixture
    def profiler(self):
        """Create a Profiler instance."""
        return Profiler()

    def test_profiler_initialization(self, profiler):
        """Test profiler initialization."""
        assert not profiler.enabled
        assert profiler.min_duration == 0.001
        assert profiler.max_entries == 10000
        assert len(profiler.profile_entries) == 0
        assert len(profiler.active_profiles) == 0

    @pytest.mark.asyncio
    async def test_start_profiling(self, profiler):
        """Test starting profiling."""
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            profiler.start()
        
        assert profiler.enabled

    @pytest.mark.asyncio
    async def test_stop_profiling(self, profiler):
        """Test stopping profiling."""
        profiler.enabled = True
        
        # Add an active profile
        profile_id = profiler.start_profile("test_function")
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            profiler.stop()
        
        assert not profiler.enabled
        assert len(profiler.active_profiles) == 0

    def test_start_profile_disabled(self, profiler):
        """Test starting profile when disabled."""
        profile_id = profiler.start_profile("test_function")
        assert profile_id == ""

    def test_start_profile_enabled(self, profiler):
        """Test starting profile when enabled."""
        profiler.enabled = True
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            profile_id = profiler.start_profile("test_function")
        
        assert profile_id != ""
        assert profile_id.startswith("test_function_")
        assert len(profiler.active_profiles) == 1
        assert profiler.stats["profiles_started"] == 1

    def test_start_profile_with_metadata(self, profiler):
        """Test starting profile with metadata."""
        profiler.enabled = True
        
        metadata = {"test": "value", "count": 42}
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            profile_id = profiler.start_profile(
                "test_function",
                module_name="test_module",
                profile_type=ProfileType.ASYNC,
                metadata=metadata,
            )
        
        entry = profiler.active_profiles[profile_id]
        assert entry.function_name == "test_function"
        assert entry.module_name == "test_module"
        assert entry.profile_type == ProfileType.ASYNC
        assert entry.metadata == metadata

    def test_end_profile_nonexistent(self, profiler):
        """Test ending non-existent profile."""
        result = profiler.end_profile("nonexistent")
        assert result is None

    def test_end_profile_existing(self, profiler):
        """Test ending existing profile."""
        profiler.enabled = True
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            profile_id = profiler.start_profile("test_function")
        
        # Sleep to ensure duration > min_duration
        time.sleep(0.002)
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            entry = profiler.end_profile(profile_id)
        
        assert entry is not None
        assert entry.function_name == "test_function"
        assert entry.duration >= 0.002
        assert len(profiler.active_profiles) == 0
        assert profiler.stats["profiles_completed"] == 1

    def test_end_profile_short_duration(self, profiler):
        """Test ending profile with short duration."""
        profiler.enabled = True
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            profile_id = profiler.start_profile("test_function")
        
        # Don't sleep - duration will be < min_duration
        
        entry = profiler.end_profile(profile_id)
        
        assert entry is not None
        assert len(profiler.profile_entries) == 0  # Should not be added
        assert profiler.stats["profiles_completed"] == 0

    @pytest.mark.asyncio
    async def test_end_profile_bottleneck(self, profiler):
        """Test ending profile that is a bottleneck."""
        profiler.enabled = True
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            profile_id = profiler.start_profile("slow_function")
        
        # Ensure the profile has sufficient duration by sleeping
        import time
        time.sleep(0.002)  # Longer than min_duration (0.001)
        
        # Mock bottleneck detection
        with patch.object(profiler, '_is_bottleneck', return_value=True), \
             patch('ccbt.events.emit_event', new_callable=AsyncMock):
            
            entry = profiler.end_profile(profile_id)
        
        assert profiler.stats["bottlenecks_detected"] == 1

    @pytest.mark.asyncio
    async def test_profile_function_decorator(self, profiler):
        """Test function profiling decorator."""
        profiler.enabled = True
        
        @profiler.profile_function("test_func", "test_module", ProfileType.FUNCTION)
        def test_function():
            import time
            time.sleep(0.002)  # Ensure sufficient duration
            return "test_result"
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024), \
             patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = test_function()
        
        assert result == "test_result"
        assert profiler.stats["profiles_started"] == 1
        assert profiler.stats["profiles_completed"] == 1

    def test_profile_function_decorator_defaults(self, profiler):
        """Test function profiling decorator with defaults."""
        profiler.enabled = True
        
        @profiler.profile_function()
        def test_function():
            return "test_result"
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            result = test_function()
        
        assert result == "test_result"

    @pytest.mark.asyncio
    async def test_profile_async_function_decorator(self, profiler):
        """Test async function profiling decorator."""
        profiler.enabled = True
        
        @profiler.profile_async_function("test_async_func", "test_module", ProfileType.ASYNC)
        async def test_async_function():
            import asyncio
            await asyncio.sleep(0.002)  # Ensure sufficient duration
            return "test_result"
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024), \
             patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = await test_async_function()
        
        assert result == "test_result"
        assert profiler.stats["profiles_started"] == 1
        assert profiler.stats["profiles_completed"] == 1

    @pytest.mark.asyncio
    async def test_profile_async_function_decorator_defaults(self, profiler):
        """Test async function profiling decorator with defaults."""
        profiler.enabled = True
        
        @profiler.profile_async_function()
        async def test_async_function():
            return "test_result"
        
        with patch.object(profiler, '_get_memory_usage', return_value=1024):
            result = await test_async_function()
        
        assert result == "test_result"

    def test_get_profile_report_empty(self, profiler):
        """Test getting profile report with no entries."""
        report = profiler.get_profile_report()
        
        assert isinstance(report, ProfileReport)
        assert report.total_duration == 0.0
        assert report.total_memory == 0
        assert report.function_count == 0
        assert len(report.entries) == 0
        assert len(report.bottlenecks) == 0
        assert len(report.recommendations) == 0

    def test_get_profile_report_with_entries(self, profiler):
        """Test getting profile report with entries."""
        # Add some profile entries
        entry1 = ProfileEntry(
            function_name="func1",
            module_name="module1",
            start_time=time.time() - 2.0,
            end_time=time.time() - 1.0,
            duration=1.0,
            memory_usage=1024,
            call_count=1,
            profile_type=ProfileType.FUNCTION,
        )
        
        entry2 = ProfileEntry(
            function_name="func2",
            module_name="module2",
            start_time=time.time() - 1.0,
            end_time=time.time(),
            duration=1.0,
            memory_usage=2048,
            call_count=1,
            profile_type=ProfileType.FUNCTION,
        )
        
        profiler.profile_entries.append(entry1)
        profiler.profile_entries.append(entry2)
        
        report = profiler.get_profile_report()
        
        assert report.total_duration == 2.0
        assert report.total_memory == 3072
        assert report.function_count == 2
        assert len(report.entries) == 2
        assert len(report.bottlenecks) == 1  # Top 10% = 1 entry

    def test_get_profile_report_with_limit(self, profiler):
        """Test getting profile report with limit."""
        # Add multiple entries
        for i in range(5):
            entry = ProfileEntry(
                function_name=f"func{i}",
                module_name=f"module{i}",
                start_time=time.time() - 1.0,
                end_time=time.time(),
                duration=1.0,
                memory_usage=1024,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
            profiler.profile_entries.append(entry)
        
        report = profiler.get_profile_report(limit=3)
        
        assert len(report.entries) == 3

    def test_get_function_stats_existing(self, profiler):
        """Test getting function stats for existing function."""
        # Add entries for a function
        for i in range(3):
            entry = ProfileEntry(
                function_name="test_func",
                module_name="test_module",
                start_time=time.time() - 1.0,
                end_time=time.time(),
                duration=1.0 + i * 0.1,
                memory_usage=1000 + i * 100,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
            profiler.profile_entries.append(entry)
        
        stats = profiler.get_function_stats("test_func")
        
        assert stats["function_name"] == "test_func"
        assert stats["call_count"] == 3
        assert stats["total_duration"] == 3.3
        assert stats["avg_duration"] == pytest.approx(1.1, rel=1e-10)
        assert stats["min_duration"] == 1.0
        assert stats["max_duration"] == 1.2
        assert stats["total_memory"] == 3300
        assert stats["avg_memory"] == 1100

    def test_get_function_stats_nonexistent(self, profiler):
        """Test getting function stats for non-existent function."""
        stats = profiler.get_function_stats("nonexistent")
        assert stats == {}

    def test_get_top_functions_by_duration(self, profiler):
        """Test getting top functions by duration."""
        # Add entries for different functions
        functions = [
            ("func1", 3.0, 1000),
            ("func2", 2.0, 2000),
            ("func3", 1.0, 3000),
        ]
        
        for func_name, duration, memory in functions:
            entry = ProfileEntry(
                function_name=func_name,
                module_name="test_module",
                start_time=time.time() - duration,
                end_time=time.time(),
                duration=duration,
                memory_usage=memory,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
            profiler.profile_entries.append(entry)
        
        top_functions = profiler.get_top_functions(limit=2, sort_by="total_duration")
        
        assert len(top_functions) == 2
        assert top_functions[0]["function_name"] == "func1"
        assert top_functions[0]["total_duration"] == 3.0
        assert top_functions[1]["function_name"] == "func2"
        assert top_functions[1]["total_duration"] == 2.0

    def test_get_top_functions_by_memory(self, profiler):
        """Test getting top functions by memory."""
        # Add entries for different functions
        functions = [
            ("func1", 1.0, 1000),
            ("func2", 2.0, 2000),
            ("func3", 3.0, 3000),
        ]
        
        for func_name, duration, memory in functions:
            entry = ProfileEntry(
                function_name=func_name,
                module_name="test_module",
                start_time=time.time() - duration,
                end_time=time.time(),
                duration=duration,
                memory_usage=memory,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
            profiler.profile_entries.append(entry)
        
        top_functions = profiler.get_top_functions(limit=2, sort_by="total_memory")
        
        assert len(top_functions) == 2
        assert top_functions[0]["function_name"] == "func3"
        assert top_functions[0]["total_memory"] == 3000
        assert top_functions[1]["function_name"] == "func2"
        assert top_functions[1]["total_memory"] == 2000

    def test_get_profiler_statistics(self, profiler):
        """Test getting profiler statistics."""
        profiler.enabled = True
        profiler.stats["profiles_started"] = 10
        profiler.stats["profiles_completed"] = 8
        profiler.stats["total_duration"] = 5.0
        profiler.stats["total_memory"] = 10240
        profiler.stats["bottlenecks_detected"] = 2
        
        stats = profiler.get_profiler_statistics()
        
        assert stats["enabled"] is True
        assert stats["profiles_started"] == 10
        assert stats["profiles_completed"] == 8
        assert stats["total_duration"] == 5.0
        assert stats["total_memory"] == 10240
        assert stats["bottlenecks_detected"] == 2
        assert stats["active_profiles"] == 0
        assert stats["profile_entries"] == 0
        assert stats["min_duration"] == 0.001

    def test_cleanup_old_entries(self, profiler):
        """Test cleanup of old entries."""
        current_time = time.time()
        old_time = current_time - 4000  # 4000 seconds ago
        
        # Add old entry
        old_entry = ProfileEntry(
            function_name="old_func",
            module_name="old_module",
            start_time=old_time,
            end_time=old_time + 1.0,
            duration=1.0,
            memory_usage=1024,
            call_count=1,
            profile_type=ProfileType.FUNCTION,
        )
        profiler.profile_entries.append(old_entry)
        
        # Add recent entry
        recent_entry = ProfileEntry(
            function_name="recent_func",
            module_name="recent_module",
            start_time=current_time - 1.0,
            end_time=current_time,
            duration=1.0,
            memory_usage=1024,
            call_count=1,
            profile_type=ProfileType.FUNCTION,
        )
        profiler.profile_entries.append(recent_entry)
        
        # Cleanup entries older than 1 hour
        profiler.cleanup_old_entries(max_age_seconds=3600)
        
        # Only recent entry should remain
        assert len(profiler.profile_entries) == 1
        assert profiler.profile_entries[0].function_name == "recent_func"

    def test_get_memory_usage_with_psutil(self, profiler):
        """Test getting memory usage with psutil."""
        with patch('psutil.Process') as mock_process:
            mock_memory_info = MagicMock()
            mock_memory_info.rss = 1024000
            mock_process.return_value.memory_info.return_value = mock_memory_info
            
            memory_usage = profiler._get_memory_usage()
            
            assert memory_usage == 1024000

    def test_get_memory_usage_without_psutil(self, profiler):
        """Test getting memory usage without psutil."""
        with patch('psutil.Process', side_effect=ImportError):
            memory_usage = profiler._get_memory_usage()
            
            assert memory_usage == 0

    def test_is_bottleneck_true(self, profiler):
        """Test bottleneck detection for slow function."""
        entry = ProfileEntry(
            function_name="slow_func",
            module_name="test_module",
            start_time=time.time() - 2.0,
            end_time=time.time(),
            duration=2.0,  # > 1.0 second threshold
            memory_usage=1024,
            call_count=1,
            profile_type=ProfileType.FUNCTION,
        )
        
        is_bottleneck = profiler._is_bottleneck(entry)
        assert is_bottleneck is True

    def test_is_bottleneck_false(self, profiler):
        """Test bottleneck detection for fast function."""
        entry = ProfileEntry(
            function_name="fast_func",
            module_name="test_module",
            start_time=time.time() - 0.5,
            end_time=time.time(),
            duration=0.5,  # < 1.0 second threshold
            memory_usage=1024,
            call_count=1,
            profile_type=ProfileType.FUNCTION,
        )
        
        is_bottleneck = profiler._is_bottleneck(entry)
        assert is_bottleneck is False

    def test_generate_recommendations_empty(self, profiler):
        """Test generating recommendations with no entries."""
        recommendations = profiler._generate_recommendations([], [])
        assert recommendations == []

    def test_generate_recommendations_slow_functions(self, profiler):
        """Test generating recommendations for slow functions."""
        entries = [
            ProfileEntry(
                function_name="slow_func",
                module_name="test_module",
                start_time=time.time() - 0.2,
                end_time=time.time(),
                duration=0.2,  # > 0.1 second average
                memory_usage=1024,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
        ]
        
        recommendations = profiler._generate_recommendations(entries, [])
        
        assert "Consider optimizing slow functions" in recommendations

    def test_generate_recommendations_high_memory(self, profiler):
        """Test generating recommendations for high memory usage."""
        entries = [
            ProfileEntry(
                function_name="memory_func",
                module_name="test_module",
                start_time=time.time() - 0.1,
                end_time=time.time(),
                duration=0.1,
                memory_usage=20 * 1024 * 1024,  # > 10MB average
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
        ]
        
        recommendations = profiler._generate_recommendations(entries, [])
        
        assert "Consider optimizing memory usage" in recommendations

    def test_generate_recommendations_bottlenecks(self, profiler):
        """Test generating recommendations for bottlenecks."""
        entries = [
            ProfileEntry(
                function_name="func1",
                module_name="test_module",
                start_time=time.time() - 0.1,
                end_time=time.time(),
                duration=0.1,
                memory_usage=1024,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
        ]
        
        bottlenecks = [
            ProfileEntry(
                function_name="bottleneck_func",
                module_name="test_module",
                start_time=time.time() - 2.0,
                end_time=time.time(),
                duration=2.0,
                memory_usage=1024,
                call_count=1,
                profile_type=ProfileType.FUNCTION,
            )
        ]
        
        recommendations = profiler._generate_recommendations(entries, bottlenecks)
        
        assert any("Focus on optimizing: bottleneck_func" in rec for rec in recommendations)


class TestCPROfiler:
    """Test cases for CPROfiler."""

    @pytest.fixture
    def cprofiler(self):
        """Create a CPROfiler instance."""
        return CPROfiler()

    def test_cprofiler_initialization(self, cprofiler):
        """Test cprofiler initialization."""
        assert not cprofiler.enabled
        assert cprofiler.profiler is not None

    def test_start_cprofiler(self, cprofiler):
        """Test starting cprofiler."""
        cprofiler.start()
        assert cprofiler.enabled
        
        # Clean up
        cprofiler.stop()

    def test_stop_cprofiler(self, cprofiler):
        """Test stopping cprofiler."""
        cprofiler.enabled = True
        cprofiler.stop()
        assert not cprofiler.enabled

    def test_get_stats_disabled(self, cprofiler):
        """Test getting stats when disabled."""
        stats = cprofiler.get_stats()
        assert stats == ""

    def test_get_stats_enabled(self, cprofiler):
        """Test getting stats when enabled."""
        cprofiler.start()
        
        # Run some code to profile
        def test_function():
            return sum(range(1000))
        
        test_function()
        
        stats = cprofiler.get_stats()
        assert isinstance(stats, str)
        assert len(stats) > 0
        
        # Clean up
        cprofiler.stop()

    def test_get_stats_dict_disabled(self, cprofiler):
        """Test getting stats dict when disabled."""
        stats = cprofiler.get_stats_dict()
        assert stats == {}

    def test_get_stats_dict_enabled(self, cprofiler):
        """Test getting stats dict when enabled."""
        cprofiler.start()
        
        # Run some code to profile
        def test_function():
            return sum(range(1000))
        
        test_function()
        
        stats = cprofiler.get_stats_dict()
        assert isinstance(stats, dict)
        assert "total_calls" in stats
        assert "primitive_calls" in stats
        assert "total_time" in stats
        assert "cumulative_time" in stats
        
        # Clean up
        cprofiler.stop()
