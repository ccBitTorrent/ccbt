"""Daemon process management.

from __future__ import annotations

Manages daemon process lifecycle, PID files, and single instance enforcement.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)


class DaemonManager:
    """Manages daemon process lifecycle and single instance enforcement."""

    def __init__(
        self,
        pid_file: str | Path | None = None,
        state_dir: str | Path | None = None,
    ):
        """Initialize daemon manager.

        Args:
            pid_file: Path to PID file (default: ~/.ccbt/daemon/daemon.pid)
            state_dir: State directory (default: ~/.ccbt/daemon)

        """
        if state_dir is None:
            state_dir = Path.home() / ".ccbt" / "daemon"
        elif isinstance(state_dir, str):
            state_dir = Path(state_dir).expanduser()

        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        if pid_file is None:
            pid_file = self.state_dir / "daemon.pid"
        elif isinstance(pid_file, str):
            pid_file = Path(pid_file).expanduser()

        self.pid_file = Path(pid_file)
        # Lock file for atomic daemon detection
        self.lock_file = self.state_dir / "daemon.lock"

        self._shutdown_requested = False
        self._lock_handle: Any = None  # File handle for lock file

    def ensure_single_instance(self) -> bool:
        """Ensure only one daemon instance is running.

        Returns:
            True if single instance is ensured, False if another instance is running

        """
        if self.pid_file.exists():
            try:
                # CRITICAL FIX: Read with retry and validation to handle race conditions
                # Multiple CLI commands might read simultaneously
                pid_text = None
                for attempt in range(3):
                    try:
                        pid_text = self.pid_file.read_text(encoding="utf-8")
                        if pid_text:
                            break
                    except OSError:
                        if attempt < 2:
                            # File might be locked or being written - retry
                            time.sleep(0.1)
                            continue
                        raise

                if not pid_text:
                    # Empty file - remove it
                    logger.warning("PID file is empty, removing")
                    with contextlib.suppress(OSError):
                        self.pid_file.unlink()
                    return True

                # Validate PID format
                pid_text = pid_text.strip()
                if not pid_text or not pid_text.isdigit():
                    logger.warning(
                        "PID file contains invalid data: %r, removing", pid_text[:50]
                    )
                    with contextlib.suppress(OSError):
                        self.pid_file.unlink()
                    return True

                pid = int(pid_text)

                # Validate PID is reasonable (1 to 2^31-1 on most systems)
                if pid <= 0 or pid > 2147483647:
                    logger.warning("PID file contains invalid PID: %d, removing", pid)
                    with contextlib.suppress(OSError):
                        self.pid_file.unlink()
                    return True

                # Check if process is actually running
                # On Windows, os.kill() can raise ProcessLookupError or other exceptions
                try:
                    os.kill(pid, 0)  # Signal 0 just checks if process exists
                    logger.warning("Daemon already running with PID %d", pid)
                    return False
                except (OSError, ProcessLookupError):
                    # Process doesn't exist, remove stale PID file
                    logger.info("Removing stale PID file (process %d not running)", pid)
                    self.pid_file.unlink()
                except Exception:
                    # Handle any other unexpected exceptions (Windows-specific issues)
                    logger.debug(
                        "Error checking process existence for PID %d, removing stale PID file",
                        pid,
                    )
                    self.pid_file.unlink()

            except (ValueError, OSError) as e:
                logger.warning(
                    "Error reading PID file (may be corrupted or locked): %s", e
                )
                # Remove invalid/corrupted PID file
                with contextlib.suppress(OSError):
                    self.pid_file.unlink()

        return True

    def get_pid(self) -> int | None:
        """Get daemon PID from file with validation and retry logic.

        Returns:
            PID or None if not found or invalid

        """
        if not self.pid_file.exists():
            return None

        try:
            # CRITICAL FIX: Read with retry to handle race conditions
            pid_text = None
            for attempt in range(3):
                try:
                    pid_text = self.pid_file.read_text(encoding="utf-8")
                    if pid_text:
                        break
                except OSError as e:
                    if attempt < 2:
                        # File might be locked or being written - retry
                        time.sleep(0.1)
                        continue
                    logger.debug("Error reading PID file after retries: %s", e)
                    return None

            if not pid_text:
                # Empty file - remove it
                logger.debug("PID file is empty, removing")
                with contextlib.suppress(OSError):
                    self.pid_file.unlink()
                return None

            # Validate PID format
            pid_text = pid_text.strip()
            if not pid_text or not pid_text.isdigit():
                logger.warning(
                    "PID file contains invalid data: %r, removing", pid_text[:50]
                )
                with contextlib.suppress(OSError):
                    self.pid_file.unlink()
                return None

            pid = int(pid_text)

            # Validate PID is reasonable
            if pid <= 0 or pid > 2147483647:
                logger.warning("PID file contains invalid PID: %d, removing", pid)
                with contextlib.suppress(OSError):
                    self.pid_file.unlink()
                return None

            # Verify process is actually running
            # On Windows, os.kill() can raise ProcessLookupError or other exceptions
            try:
                os.kill(pid, 0)
                return pid
            except (OSError, ProcessLookupError):
                # Process doesn't exist, remove stale PID file
                self.pid_file.unlink()
                return None
            except Exception:
                # Handle any other unexpected exceptions (Windows-specific issues)
                # On Windows, os.kill() might raise exceptions with "exception set" errors
                logger.debug(
                    "Error checking process existence for PID %d, removing stale PID file",
                    pid,
                )
                self.pid_file.unlink()
                return None

        except (ValueError, OSError) as e:
            logger.debug("Error reading PID file: %s", e)
            return None

    def is_running(self) -> bool:
        """Check if daemon is running.

        Returns:
            True if daemon is running, False otherwise

        """
        try:
            return self.get_pid() is not None
        except Exception:
            # Handle any unexpected exceptions from get_pid()
            # On Windows, this can happen with os.kill() issues
            logger.debug("Error checking if daemon is running", exc_info=True)
            return False

    def acquire_lock(self) -> bool:
        """Acquire lock file for atomic daemon detection.

        Uses cross-platform file locking to prevent race conditions.

        Returns:
            True if lock acquired, False if already locked
        """
        try:
            import sys

            if sys.platform == "win32":
                # Windows: use exclusive file creation
                # CRITICAL FIX: First check if lock file exists and if process is running
                # This handles stale locks from crashed processes
                if self.lock_file.exists():
                    try:
                        lock_pid_text = self.lock_file.read_text(encoding="utf-8").strip()
                        if lock_pid_text.isdigit():
                            lock_pid = int(lock_pid_text)
                            # Check if process is running
                            try:
                                # On Windows, signal 0 doesn't work the same way
                                # Use a different method to check if process exists
                                import subprocess
                                result = subprocess.run(
                                    ["tasklist", "/FI", f"PID eq {lock_pid}", "/FO", "CSV"],
                                    capture_output=True,
                                    timeout=2,
                                )
                                if str(lock_pid) in result.stdout.decode("utf-8", errors="ignore"):
                                    # Process is running - lock is valid
                                    logger.debug(
                                        "Lock file exists and process %d is running", lock_pid
                                    )
                                    return False
                                else:
                                    # Process is dead - remove stale lock
                                    logger.warning(
                                        "Lock file exists but process %d is not running, removing stale lock",
                                        lock_pid,
                                    )
                                    # Try to remove, but if it's locked by another process, continue anyway
                                    try:
                                        self.lock_file.unlink()
                                    except (OSError, PermissionError) as e:
                                        logger.warning(
                                            "Cannot remove stale lock file (may be locked): %s. "
                                            "Will try to create new lock file anyway.",
                                            e,
                                        )
                                        # Continue - we'll try to create a new lock file
                            except Exception as e:
                                logger.debug("Error checking process existence: %s", e)
                                # Assume process is dead - try to remove lock
                                try:
                                    self.lock_file.unlink()
                                except (OSError, PermissionError):
                                    pass  # Ignore - will try to create new lock
                    except Exception as e:
                        logger.debug("Error reading lock file: %s, removing", e)
                        try:
                            self.lock_file.unlink()
                        except (OSError, PermissionError):
                            pass  # Ignore - will try to create new lock

                # Try to create lock file exclusively
                try:
                    # Try to create lock file exclusively (fails if exists)
                    self._lock_handle = open(
                        self.lock_file, "x"
                    )  # 'x' mode = exclusive creation
                    # Write PID to lock file
                    self._lock_handle.write(str(os.getpid()))
                    self._lock_handle.flush()
                    logger.debug("Acquired daemon lock file: %s", self.lock_file)
                    return True
                except FileExistsError:
                    # Lock file was created between check and creation - another process got it
                    logger.debug("Lock file was created by another process")
                    return False
                except (OSError, PermissionError) as e:
                    # File might be locked by another process
                    logger.debug("Cannot create lock file (may be locked): %s", e)
                    return False
            else:
                # Unix: use fcntl for file locking
                try:
                    import fcntl
                except ImportError:
                    # fcntl not available - fall back to simple file existence check
                    if self.lock_file.exists():
                        return False
                    try:
                        self._lock_handle = open(self.lock_file, "w")
                        self._lock_handle.write(str(os.getpid()))
                        self._lock_handle.flush()
                        logger.debug("Acquired daemon lock file: %s", self.lock_file)
                        return True
                    except OSError:
                        return False

                try:
                    self._lock_handle = open(self.lock_file, "w")
                    fcntl.flock(
                        self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )
                    # Write PID to lock file
                    self._lock_handle.write(str(os.getpid()))
                    self._lock_handle.flush()
                    logger.debug("Acquired daemon lock file: %s", self.lock_file)
                    return True
                except (OSError, BlockingIOError):
                    # Lock is held by another process
                    if self._lock_handle:
                        self._lock_handle.close()
                        self._lock_handle = None
                    return False
        except Exception as e:
            logger.debug("Error acquiring lock file: %s", e)
            if self._lock_handle:
                with contextlib.suppress(Exception):
                    self._lock_handle.close()
                self._lock_handle = None
            return False

    def release_lock(self) -> None:
        """Release lock file."""
        if self._lock_handle:
            try:
                import sys

                if sys.platform != "win32":
                    try:
                        import fcntl

                        fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
                    except ImportError:
                        pass  # fcntl not available
                self._lock_handle.close()
                self._lock_handle = None
            except Exception as e:
                logger.debug("Error releasing lock file: %s", e)
            finally:
                self._lock_handle = None

        # Remove lock file
        with contextlib.suppress(OSError):
            if self.lock_file.exists():
                self.lock_file.unlink()
                logger.debug("Released daemon lock file: %s", self.lock_file)

    def write_pid(self, acquire_lock: bool = True) -> None:
        """Write current process PID to file using atomic write.

        Uses atomic write pattern: write to temp file, then rename.
        This prevents corruption if write is interrupted.

        Args:
            acquire_lock: If True, acquire lock before writing (default: True).
                         Set to False if lock is already acquired.
        """
        pid = os.getpid()

        # CRITICAL FIX: Acquire lock before writing PID file (if not already acquired)
        # This ensures atomic daemon detection
        if acquire_lock:
            if not self.acquire_lock():
                raise RuntimeError(
                    "Cannot acquire daemon lock file. Another daemon may be starting."
                )

        # CRITICAL FIX: Use atomic write to prevent corruption
        # Write to temp file first, then rename atomically
        # This ensures PID file is never in a corrupted state
        temp_file = self.pid_file.with_suffix(self.pid_file.suffix + ".tmp")

        try:
            # Write PID to temp file
            temp_file.write_text(str(pid), encoding="utf-8")
            # Atomically replace PID file with temp file
            # On Windows, this requires the target to not exist, so remove it first
            if self.pid_file.exists():
                self.pid_file.unlink()
            temp_file.replace(self.pid_file)
            logger.debug("Wrote PID %d to %s (atomic write)", pid, self.pid_file)
        except Exception as e:
            # Clean up temp file on error
            with contextlib.suppress(OSError):
                temp_file.unlink()
            # Release lock on error
            self.release_lock()
            logger.error("Failed to write PID file: %s", e)
            raise

    def remove_pid(self) -> None:
        """Remove PID file and release lock."""
        if self.pid_file.exists():
            self.pid_file.unlink()
            logger.debug("Removed PID file: %s", self.pid_file)
        # Release lock file
        self.release_lock()

    def start(
        self,
        script_path: str | None = None,
        foreground: bool = False,
    ) -> int:
        """Start daemon process.

        Args:
            script_path: Path to daemon script (if None, uses current Python)
            foreground: Run in foreground (for debugging)

        Returns:
            Process PID

        """
        if not self.ensure_single_instance():
            msg = "Daemon is already running"
            raise RuntimeError(msg)

        if foreground:
            # Run in foreground (for debugging)
            logger.info("Starting daemon in foreground mode")
            # Return current PID (will be set by daemon main)
            return os.getpid()

        # Start daemon process
        if script_path is None:
            # Use current Python interpreter
            script_path = sys.executable
            daemon_module = "ccbt.daemon.main"
            args = [script_path, "-m", daemon_module]
        else:
            args = [script_path]

        # Start process
        try:
            # CRITICAL FIX: Capture stderr to a log file for background mode
            # This allows debugging daemon startup failures
            log_file = self.state_dir / "daemon_startup.log"
            log_fd: int | Any = subprocess.DEVNULL
            try:
                log_fd = open(log_file, "a", encoding="utf-8")
            except Exception:
                # If we can't open log file, fall back to DEVNULL
                log_fd = subprocess.DEVNULL

            process = subprocess.Popen(
                args,
                stdout=log_fd,
                stderr=log_fd,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

            # CRITICAL FIX: Wait longer and check multiple times
            # This gives the daemon time to initialize and write PID file
            # Increased to 60.0s to account for slow startup (NAT discovery can take ~35s, DHT bootstrap ~8s, etc.)
            max_wait_time = 60.0  # Maximum time to wait (NAT discovery + DHT bootstrap + IPC server startup)
            check_interval = 0.5  # Check every 500ms
            waited = 0.0

            while waited < max_wait_time:
                return_code = process.poll()
                if return_code is not None:
                    # Process exited - read log file for error details
                    error_msg = f"Daemon process exited with code {return_code}"
                    if return_code != 0:
                        error_msg += f" (error code: {return_code})"

                    # Try to read last few lines of log file for context
                    log_details = ""
                    if log_file.exists() and log_file.stat().st_size > 0:
                        try:
                            with open(log_file, encoding="utf-8") as f:
                                lines = f.readlines()
                                # Get last 10 lines
                                last_lines = lines[-10:] if len(lines) > 10 else lines
                                log_details = "\n".join(last_lines)
                                if log_details:
                                    error_msg += f"\nLast log entries:\n{log_details}"
                        except Exception:
                            pass

                    logger.error(error_msg)
                    logger.error(
                        "Daemon process failed to start. "
                        "Check %s for detailed error output, or run with --foreground flag: "
                        "btbt daemon start --foreground",
                        log_file,
                    )
                    raise RuntimeError(error_msg)

                # Check if PID file exists (daemon is ready)
                if self.pid_file.exists():
                    logger.info(
                        "Daemon started with PID %d (PID file created)", process.pid
                    )
                    if log_fd != subprocess.DEVNULL:
                        try:
                            log_fd.close()  # type: ignore[union-attr]
                        except Exception:
                            pass
                    return process.pid

                time.sleep(check_interval)
                waited += check_interval

            # If we get here, process is still running but PID file not created yet
            # This might be OK if daemon is still initializing, but log a warning
            logger.warning(
                "Daemon process (PID %d) started but PID file not created after %.1fs. "
                "Daemon may still be initializing. Check %s for details.",
                process.pid,
                max_wait_time,
                log_file,
            )
            logger.info("Daemon started with PID %d", process.pid)
            if log_fd != subprocess.DEVNULL:
                try:
                    log_fd.close()  # type: ignore[union-attr]
                except Exception:
                    pass
            return process.pid

        except Exception:
            logger.exception("Error starting daemon")
            raise

    def stop(self, timeout: float = 30.0, force: bool = False) -> bool:
        """Stop daemon process gracefully.

        Args:
            timeout: Shutdown timeout in seconds
            force: Force kill if graceful shutdown fails

        Returns:
            True if stopped, False otherwise

        """
        pid = self.get_pid()
        if not pid:
            logger.info("Daemon is not running")
            return True

        try:
            # Send SIGTERM for graceful shutdown
            logger.info("Sending SIGTERM to daemon (PID %d)", pid)
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)  # Check if process exists
                    time.sleep(0.1)
                except (OSError, ProcessLookupError):
                    # Process exited
                    logger.info("Daemon stopped gracefully")
                    self.remove_pid()
                    return True

            # Process didn't exit, force kill if requested
            if force:
                logger.warning("Daemon didn't stop gracefully, force killing")
                try:
                    # SIGKILL is not available on Windows, use SIGTERM instead
                    if sys.platform == "win32":
                        # On Windows, use SIGTERM for force kill (Windows doesn't have SIGKILL)
                        os.kill(pid, signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGKILL)
                    time.sleep(0.5)
                    self.remove_pid()
                    return True
                except (OSError, ProcessLookupError):
                    pass

            logger.error("Failed to stop daemon within timeout")
            return False

        except OSError:
            logger.exception("Error stopping daemon")
            # Process might not exist, remove PID file
            self.remove_pid()
            return False

    def restart(self, script_path: str | None = None) -> int:
        """Restart daemon process.

        Args:
            script_path: Path to daemon script

        Returns:
            New process PID

        """
        logger.info("Restarting daemon")
        self.stop(timeout=10.0, force=True)
        time.sleep(1.0)  # Brief pause
        return self.start(script_path=script_path)

    def setup_signal_handlers(self, shutdown_callback: Any) -> None:
        """Set up signal handlers for graceful shutdown.

        Args:
            shutdown_callback: Async callback function for shutdown

        """

        def signal_handler(signum: int, _frame: Any) -> None:
            """Handle shutdown signal."""
            logger.info("Received signal %d, initiating shutdown", signum)
            self._shutdown_requested = True
            # Schedule shutdown callback
            if shutdown_callback:
                _ = asyncio.create_task(shutdown_callback())

        # Register signal handlers
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGHUP, signal_handler)  # Reload signal
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C

    @staticmethod
    def daemonize() -> None:
        """Daemonize current process (Unix only).

        Implements double-fork daemonization pattern.
        """
        if sys.platform == "win32":
            # Windows doesn't support daemonization
            logger.warning(
                "Daemonization not supported on Windows, running in background"
            )
            return

        try:
            # First fork
            pid = os.fork()
            if pid > 0:
                # Parent process, exit
                os._exit(0)

            # Child process
            os.setsid()  # Create new session

            # Second fork
            pid = os.fork()
            if pid > 0:
                # Parent process, exit
                os._exit(0)

            # Daemon process
            # Change working directory
            os.chdir("/")

            # Close file descriptors
            import resource

            maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            if maxfd == resource.RLIM_INFINITY:
                maxfd = 1024

            for fd in range(maxfd):
                with contextlib.suppress(OSError):
                    os.close(fd)

            # Redirect stdio
            os.open("/dev/null", os.O_RDWR)  # stdin
            os.dup2(0, 1)  # stdout
            os.dup2(0, 2)  # stderr

            logger.info("Process daemonized")

        except OSError:
            logger.exception("Error daemonizing process")
            raise
