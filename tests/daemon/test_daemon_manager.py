"""Tests for daemon manager single instance enforcement.

from __future__ import annotations

Tests single instance enforcement and process lifecycle.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from ccbt.daemon.daemon_manager import DaemonManager


@pytest.fixture
def temp_daemon_dir():
    """Create temporary daemon directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def daemon_manager(temp_daemon_dir):
    """Create daemon manager for testing."""
    pid_file = temp_daemon_dir / "daemon.pid"
    return DaemonManager(pid_file=pid_file, state_dir=temp_daemon_dir)


def test_ensure_single_instance_no_pid_file(daemon_manager):
    """Test single instance check when no PID file exists."""
    assert daemon_manager.ensure_single_instance() is True


def test_ensure_single_instance_stale_pid_file(daemon_manager, temp_daemon_dir):
    """Test single instance check with stale PID file."""
    # Create PID file with non-existent PID
    pid_file = temp_daemon_dir / "daemon.pid"
    pid_file.write_text("99999", encoding="utf-8")

    # Should remove stale PID and return True
    assert daemon_manager.ensure_single_instance() is True
    assert not pid_file.exists()


def test_ensure_single_instance_running_process(daemon_manager, temp_daemon_dir):
    """Test single instance check when process is actually running."""
    # Write current process PID
    pid_file = temp_daemon_dir / "daemon.pid"
    current_pid = os.getpid()
    pid_file.write_text(str(current_pid), encoding="utf-8")

    # Should detect running process and return False
    assert daemon_manager.ensure_single_instance() is False


def test_get_pid(daemon_manager, temp_daemon_dir):
    """Test getting daemon PID."""
    # No PID file
    assert daemon_manager.get_pid() is None

    # Create PID file with current PID
    pid_file = temp_daemon_dir / "daemon.pid"
    current_pid = os.getpid()
    pid_file.write_text(str(current_pid), encoding="utf-8")

    # Should return PID
    pid = daemon_manager.get_pid()
    assert pid == current_pid


def test_is_running(daemon_manager, temp_daemon_dir):
    """Test checking if daemon is running."""
    # Not running
    assert daemon_manager.is_running() is False

    # Create PID file with current PID
    pid_file = temp_daemon_dir / "daemon.pid"
    current_pid = os.getpid()
    pid_file.write_text(str(current_pid), encoding="utf-8")

    # Should be running
    assert daemon_manager.is_running() is True


def test_write_and_remove_pid(daemon_manager, temp_daemon_dir):
    """Test writing and removing PID file."""
    pid_file = temp_daemon_dir / "daemon.pid"

    # Write PID
    daemon_manager.write_pid()
    assert pid_file.exists()
    assert int(pid_file.read_text(encoding="utf-8")) == os.getpid()

    # Remove PID
    daemon_manager.remove_pid()
    assert not pid_file.exists()

