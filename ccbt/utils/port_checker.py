"""Port availability checking utilities."""

from __future__ import annotations

import socket
import sys
from typing import Tuple


def is_port_available(
    host: str, port: int, protocol: str = "tcp"
) -> Tuple[bool, str | None]:
    """Check if a port is available for binding.

    Args:
        host: Host address to check (e.g., "127.0.0.1", "0.0.0.0")
        port: Port number to check
        protocol: Protocol type ("tcp" or "udp")

    Returns:
        Tuple of (is_available, error_message)
        - is_available: True if port is available, False otherwise
        - error_message: None if available, otherwise error description

    """
    if protocol.lower() == "tcp":
        sock_type = socket.SOCK_STREAM
    elif protocol.lower() == "udp":
        sock_type = socket.SOCK_DGRAM
    else:
        return (False, f"Unsupported protocol: {protocol}")

    try:
        test_sock = socket.socket(socket.AF_INET, sock_type)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # On Windows, SO_REUSEPORT may not be available
        if hasattr(socket, "SO_REUSEPORT") and sys.platform != "win32":
            try:
                test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (OSError, AttributeError):
                pass  # SO_REUSEPORT not available on this system

        test_sock.settimeout(0.1)

        try:
            test_sock.bind((host, port))
            test_sock.close()
            return (True, None)
        except OSError as e:
            test_sock.close()
            error_code = e.errno if hasattr(e, "errno") else None

            # Windows error codes
            if sys.platform == "win32":
                if error_code == 10048:  # WSAEADDRINUSE
                    return (False, f"Port {port} is already in use")
                if error_code == 10013:  # WSAEACCES
                    return (False, f"Permission denied binding to {host}:{port}")
            # Unix error codes
            elif error_code == 98:  # EADDRINUSE
                return (False, f"Port {port} is already in use")
            elif error_code == 13:  # EACCES
                return (False, f"Permission denied binding to {host}:{port}")

            return (False, f"Failed to bind to {host}:{port}: {e}")
    except Exception as e:
        return (False, f"Error checking port availability: {e}")


def get_port_conflict_resolution(port: int, protocol: str = "tcp") -> str:
    """Get resolution steps for port conflicts.

    CRITICAL FIX: Enhanced to check for daemon usage and provide better error messages.

    Args:
        port: Port number that's in conflict
        protocol: Protocol type ("tcp" or "udp")

    Returns:
        Formatted string with resolution steps

    """
    # CRITICAL FIX: Check if daemon might be using this port
    from pathlib import Path
    
    daemon_pid_file = Path.home() / ".ccbt" / "daemon" / "daemon.pid"
    daemon_might_be_running = daemon_pid_file.exists()
    
    if sys.platform == "win32":
        check_cmd = f"netstat -ano | findstr :{port}"
        kill_help = (
            "To find and stop the process:\n"
            f"  1. Run: {check_cmd}\n"
            "  2. Note the PID from the last column\n"
            "  3. Run: taskkill /PID <PID> /F"
        )
    else:
        check_cmd = f"lsof -i :{port} || netstat -tulpn | grep :{port}"
        kill_help = (
            "To find and stop the process:\n"
            f"  1. Run: {check_cmd}\n"
            "  2. Note the PID from the output\n"
            "  3. Run: kill <PID>"
        )

    resolution = f"Resolution options:\n"
    
    # CRITICAL FIX: Prioritize daemon check if PID file exists
    if daemon_might_be_running:
        resolution += (
            f"  1. Check if ccBitTorrent daemon is running and using this port:\n"
            f"     Run: btbt daemon status\n"
            f"     If daemon is running, use daemon commands instead of local session:\n"
            f"     - Use: btbt magnet <magnet_link> (routes to daemon automatically)\n"
            f"     - Or stop daemon first: btbt daemon stop\n"
            f"  2. Stop the process using port {port}:\n"
            f"     {kill_help}\n"
        )
    else:
        resolution += (
            f"  1. Stop the process using port {port}:\n"
            f"     {kill_help}\n"
            f"  2. Check if another ccBitTorrent daemon is running:\n"
            f"     Run: btbt daemon status\n"
            f"     If daemon is running, stop it: btbt daemon stop\n"
        )
    
    resolution += (
        f"  3. Change the port in your configuration:\n"
        f"     - Edit ccbt.toml and set the appropriate port (network.listen_port_tcp, network.tracker_udp_port, etc.)\n"
        f"     - Or set the corresponding CCBT_* environment variable\n"
    )
    
    return resolution


def get_permission_error_resolution(
    port: int, protocol: str = "tcp", config_key: str | None = None
) -> str:
    """Get resolution steps for permission denied errors.

    Args:
        port: Port number that failed to bind
        protocol: Protocol type ("tcp" or "udp")
        config_key: Optional configuration key name (e.g., "network.tracker_udp_port")

    Returns:
        Formatted string with resolution steps

    """
    if config_key is None:
        # Default to generic port configuration
        config_key = "network.listen_port"
        env_var = "CCBT_NETWORK_LISTEN_PORT"
    else:
        # Convert config key to environment variable format
        env_var = "CCBT_" + config_key.upper().replace(".", "_")

    if sys.platform == "win32":
        return (
            f"Permission denied binding to port {port} ({protocol.upper()}).\n"
            f"Resolution options:\n"
            f"  1. Run with administrator privileges:\n"
            f"     - Right-click Command Prompt/PowerShell and select 'Run as administrator'\n"
            f"     - Or run: btbt daemon start (as administrator)\n"
            f"  2. Change to a port >= 1024 (non-privileged port):\n"
            f"     - Edit ccbt.toml and set {config_key} to a value >= 1024\n"
            f"     - Or set {env_var} environment variable\n"
            f"  3. Check Windows Firewall settings:\n"
            f"     - Windows Firewall may be blocking the port\n"
            f"     - Add an exception for ccBitTorrent in Windows Firewall\n"
        )
    else:
        return (
            f"Permission denied binding to port {port} ({protocol.upper()}).\n"
            f"Resolution options:\n"
            f"  1. Run with root privileges (for ports < 1024):\n"
            f"     - Run: sudo btbt daemon start\n"
            f"  2. Change to a port >= 1024 (non-privileged port):\n"
            f"     - Edit ccbt.toml and set {config_key} to a value >= 1024\n"
            f"     - Or set {env_var} environment variable\n"
            f"  3. Check if SELinux or AppArmor is blocking the port\n"
        )