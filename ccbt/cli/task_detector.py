"""Task detection system for identifying long-running CLI commands.

Detects commands that typically take a long time and should show splash screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TaskInfo:
    """Information about a CLI task."""
    
    command_name: str
    expected_duration: float  # Expected duration in seconds
    min_duration: float = 2.0  # Minimum duration to be considered "long-running"
    description: str = ""
    show_splash: bool = True  # Whether to show splash screen


class TaskDetector:
    """Detects long-running tasks and determines if splash screen should be shown."""
    
    # Known long-running commands with expected durations
    LONG_RUNNING_COMMANDS: dict[str, TaskInfo] = {
        "daemon.start": TaskInfo(
            command_name="daemon.start",
            expected_duration=60.0,  # NAT discovery ~35s, DHT bootstrap ~8s, IPC startup
            min_duration=5.0,
            description="Starting daemon (NAT discovery, DHT bootstrap, IPC server)",
            show_splash=True,
        ),
        "download": TaskInfo(
            command_name="download",
            expected_duration=30.0,  # Initial connection, metadata exchange
            min_duration=3.0,
            description="Downloading torrent (connecting to peers, metadata exchange)",
            show_splash=True,
        ),
        "resume": TaskInfo(
            command_name="resume",
            expected_duration=10.0,  # Checkpoint loading
            min_duration=2.0,
            description="Resuming downloads (loading checkpoints)",
            show_splash=True,
        ),
        "status": TaskInfo(
            command_name="status",
            expected_duration=5.0,  # Status aggregation for many torrents
            min_duration=2.0,
            description="Checking status (aggregating torrent information)",
            show_splash=False,  # Usually fast, only show if many torrents
        ),
    }
    
    def __init__(self, threshold: float = 2.0) -> None:
        """Initialize task detector.
        
        Args:
            threshold: Minimum duration in seconds to be considered "long-running"
        """
        self.threshold = threshold
    
    def is_long_running(self, command_name: str) -> bool:
        """Check if a command is typically long-running.
        
        Args:
            command_name: Command name (e.g., "daemon.start", "download")
            
        Returns:
            True if command is long-running
        """
        task_info = self.LONG_RUNNING_COMMANDS.get(command_name)
        if task_info:
            return task_info.expected_duration >= self.threshold
        return False
    
    def get_task_info(self, command_name: str) -> TaskInfo | None:
        """Get task information for a command.
        
        Args:
            command_name: Command name
            
        Returns:
            TaskInfo instance or None if not found
        """
        return self.LONG_RUNNING_COMMANDS.get(command_name)
    
    def should_show_splash(self, command_name: str) -> bool:
        """Check if splash screen should be shown for a command.
        
        Args:
            command_name: Command name
            
        Returns:
            True if splash should be shown
        """
        task_info = self.get_task_info(command_name)
        if task_info:
            return task_info.show_splash and self.is_long_running(command_name)
        return False
    
    def get_expected_duration(self, command_name: str) -> float:
        """Get expected duration for a command.
        
        Args:
            command_name: Command name
            
        Returns:
            Expected duration in seconds (default: 90.0)
        """
        task_info = self.get_task_info(command_name)
        if task_info:
            return task_info.expected_duration
        return 90.0  # Default splash duration
    
    def register_command(
        self,
        command_name: str,
        expected_duration: float,
        min_duration: float = 2.0,
        description: str = "",
        show_splash: bool = True,
    ) -> None:
        """Register a command as potentially long-running.
        
        Args:
            command_name: Command name
            expected_duration: Expected duration in seconds
            min_duration: Minimum duration to be considered long-running
            description: Task description
            show_splash: Whether to show splash screen
        """
        self.LONG_RUNNING_COMMANDS[command_name] = TaskInfo(
            command_name=command_name,
            expected_duration=expected_duration,
            min_duration=min_duration,
            description=description,
            show_splash=show_splash,
        )
    
    @staticmethod
    def from_command(ctx: dict[str, Any] | None = None) -> TaskDetector:
        """Create TaskDetector from Click context.
        
        Args:
            ctx: Click context object
            
        Returns:
            TaskDetector instance
        """
        detector = TaskDetector()
        
        # Extract command name from context if available
        if ctx:
            # Try to get command name from context
            command_path = ctx.get("command_path", "")
            if command_path:
                # Convert "btbt daemon start" -> "daemon.start"
                parts = command_path.split()
                if len(parts) >= 2:
                    command_name = ".".join(parts[1:])  # Skip "btbt"
                    if detector.is_long_running(command_name):
                        return detector
        
        return detector


# Global task detector instance
_detector = TaskDetector()


def get_detector() -> TaskDetector:
    """Get the global task detector instance.
    
    Returns:
        TaskDetector instance
    """
    return _detector


def is_long_running_command(command_name: str) -> bool:
    """Check if a command is long-running.
    
    Args:
        command_name: Command name
        
    Returns:
        True if command is long-running
    """
    return _detector.is_long_running(command_name)


def should_show_splash_for_command(command_name: str) -> bool:
    """Check if splash should be shown for a command.
    
    Args:
        command_name: Command name
        
    Returns:
        True if splash should be shown
    """
    return _detector.should_show_splash(command_name)


def get_expected_duration_for_command(command_name: str) -> float:
    """Get expected duration for a command.
    
    Args:
        command_name: Command name
        
    Returns:
        Expected duration in seconds
    """
    return _detector.get_expected_duration(command_name)














