from __future__ import annotations

import asyncio
import socket
from typing import Any

from rich.console import Console

from ccbt.config.config import ConfigManager
from ccbt.daemon.daemon_manager import DaemonManager
from ccbt.i18n import _
from ccbt.session.session import AsyncSessionManager


def run_diagnostics(config_manager: ConfigManager, console: Console) -> None:
    """Run diagnostic checks for network connectivity and configuration."""
    # CRITICAL FIX: Check for daemon PID file BEFORE creating local session
    # If PID file exists, we MUST prevent local session to avoid port conflicts
    daemon_manager = DaemonManager()
    pid_file_exists = daemon_manager.pid_file.exists()

    if pid_file_exists:
        console.print(
            _("[yellow]Warning: Daemon is running. Diagnostics will test local session which may cause port conflicts.[/yellow]\n"
            "[dim]Consider stopping the daemon first: 'btbt daemon exit'[/dim]\n")
        )
        # For diagnostics, we'll allow it but warn the user
        # The user can decide if they want to proceed

    config = config_manager.config
    console.print(_("[cyan]Running diagnostic checks...[/cyan]\n"))

    console.print(_("[yellow]1. Network Connectivity[/yellow]"))
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.bind(("0.0.0.0", 0))  # nosec B104 - Test socket binding for diagnostics, ephemeral port (0)
        test_port = test_socket.getsockname()[1]
        test_socket.close()
        console.print(_("  [green]✓[/green] Can bind to port {port}").format(port=test_port))
    except Exception as e:
        console.print(_("  [red]✗[/red] Cannot bind to port: {e}").format(e=e))

    console.print(_("\n[yellow]2. DHT Status[/yellow]"))
    console.print(
        _("  DHT Enabled: {status}").format(status="[green]Yes[/green]" if config.discovery.enable_dht else "[red]No[/red]")
    )
    console.print(_("  DHT Port: {port}").format(port=config.discovery.dht_port))

    console.print(_("\n[yellow]3. Tracker Configuration[/yellow]"))
    console.print(
        _("  HTTP Trackers: {status}").format(status="[green]Enabled[/green]" if config.discovery.enable_http_trackers else "[red]Disabled[/red]")
    )
    console.print(
        _("  UDP Trackers: {status}").format(status="[green]Enabled[/green]" if config.discovery.enable_udp_trackers else "[red]Disabled[/red]")
    )

    console.print(_("\n[yellow]4. NAT Configuration[/yellow]"))
    console.print(
        _("  Auto Map Ports: {status}").format(status="[green]Yes[/green]" if config.nat.auto_map_ports else "[red]No[/red]")
    )
    console.print(
        _("  UPnP: {status}").format(status="[green]Enabled[/green]" if config.nat.enable_upnp else "[red]Disabled[/red]")
    )
    console.print(
        _("  NAT-PMP: {status}").format(status="[green]Enabled[/green]" if config.nat.enable_nat_pmp else "[red]Disabled[/red]")
    )

    console.print(_("\n[yellow]5. Listen Port[/yellow]"))
    console.print(_("  TCP Port: {port}").format(port=config.network.listen_port))
    console.print(
        _("  TCP Enabled: {status}").format(status="[green]Yes[/green]" if config.network.enable_tcp else "[red]No[/red]")
    )
    console.print(
        _("  uTP Enabled: {status}").format(status="[green]Yes[/green]" if config.network.enable_utp else "[red]No[/red]")
    )

    console.print(_("\n[yellow]6. Session Initialization Test[/yellow]"))
    try:
        # CRITICAL FIX: Use safe local session creation helper
        from ccbt.cli.main import _ensure_local_session_safe

        session = asyncio.run(_ensure_local_session_safe(force_local=True))
        console.print(_("  [green]✓[/green] Session initialized successfully"))
        if hasattr(session, "dht_client") and session.dht_client:
            routing_table_size = len(session.dht_client.routing_table.nodes)
            console.print(_("  DHT Routing Table: {size} nodes").format(size=routing_table_size))
        else:
            console.print(_("  [yellow]⚠[/yellow] DHT client not initialized"))
        if hasattr(session, "tcp_server") and session.tcp_server:
            console.print(_("  [green]✓[/green] TCP server initialized"))
        else:
            console.print(_("  [yellow]⚠[/yellow] TCP server not initialized"))
        asyncio.run(session.stop())
    except Exception as e:
        console.print(_("  [red]✗[/red] Session initialization failed: {e}").format(e=e))

    console.print(_("\n[green]Diagnostic complete![/green]"))


async def diagnose_connections(session: AsyncSessionManager) -> dict[str, Any]:
    """Diagnose connection issues for all active torrent sessions.

    Args:
        session: AsyncSessionManager instance

    Returns:
        Dictionary with connection diagnostics

    """
    diagnostics = {
        "total_sessions": 0,
        "sessions_with_peers": 0,
        "total_connections": 0,
        "connection_issues": [],
        "nat_status": {},
        "tcp_server_status": {},
    }

    # Check NAT status
    if hasattr(session, "nat_manager") and session.nat_manager:
        nat_status = await session.nat_manager.get_status()
        diagnostics["nat_status"] = {
            "active_protocol": nat_status.get("active_protocol"),
            "external_ip": nat_status.get("external_ip"),
            "mappings": len(nat_status.get("mappings", [])),
        }
    else:
        diagnostics["nat_status"] = {"status": "not_initialized"}

    # Check TCP server status
    if hasattr(session, "tcp_server") and session.tcp_server:
        diagnostics["tcp_server_status"] = {
            "running": getattr(session.tcp_server, "_running", False),
            "is_serving": (
                session.tcp_server.server.is_serving()
                if hasattr(session.tcp_server, "server") and session.tcp_server.server
                else False
            ),
        }
    else:
        diagnostics["tcp_server_status"] = {"status": "not_initialized"}

    # Check all active sessions
    if hasattr(session, "torrents") and isinstance(session.torrents, dict):
        sessions_dict: dict[Any, Any] = session.torrents
        for info_hash, torrent_session in sessions_dict.items():
            # Type guard: ensure info_hash has hex method (bytes)
            if not hasattr(info_hash, "hex") or not callable(
                getattr(info_hash, "hex", None)
            ):
                continue

            # Type guard: info_hash is bytes-like
            info_hash_hex_str: str
            try:
                hex_method = info_hash.hex
                if callable(hex_method):
                    hex_result = hex_method()
                    if isinstance(hex_result, str):
                        info_hash_hex_str = hex_result[:16] + "..."
                    else:
                        continue
                else:
                    continue
            except (AttributeError, TypeError):
                continue

            total_sessions = diagnostics.get("total_sessions", 0)
            if isinstance(total_sessions, int):
                diagnostics["total_sessions"] = total_sessions + 1

            issues_list: list[str] = []
            session_diag: dict[str, Any] = {
                "info_hash": info_hash_hex_str,
                "name": getattr(torrent_session, "info", {}).get("name", "Unknown"),
                "status": getattr(torrent_session, "info", {}).get("status", "unknown"),
                "connections": 0,
                "peer_manager_ready": False,
                "issues": issues_list,
            }

            # Check peer manager
            peer_manager = getattr(
                getattr(torrent_session, "download_manager", None), "peer_manager", None
            ) or getattr(torrent_session, "peer_manager", None)

            if peer_manager:
                session_diag["peer_manager_ready"] = True
                if hasattr(peer_manager, "connections"):
                    connections = peer_manager.connections
                    if hasattr(connections, "__len__"):
                        conn_count = len(connections)
                        session_diag["connections"] = conn_count

                        if conn_count > 0:
                            sessions_with_peers = diagnostics.get(
                                "sessions_with_peers", 0
                            )
                            total_connections = diagnostics.get("total_connections", 0)
                            if isinstance(sessions_with_peers, int):
                                diagnostics["sessions_with_peers"] = (
                                    sessions_with_peers + 1
                                )
                            if isinstance(total_connections, int):
                                diagnostics["total_connections"] = (
                                    total_connections + conn_count
                                )
                        else:
                            issues_list.append("No active peer connections")
                else:
                    issues_list.append("Peer manager has no connections attribute")
            else:
                issues_list.append("Peer manager not initialized")

            # Check for queued peers
            queued_peers = getattr(torrent_session, "_queued_peers", None)
            if queued_peers and hasattr(queued_peers, "__len__"):
                queued_count = len(queued_peers)
                session_diag["queued_peers"] = queued_count
                issues_list.append(
                    f"{queued_count} peer(s) queued (peer manager may not be ready)"
                )

            # Check DHT callback status
            dht_invocations = getattr(
                torrent_session, "_dht_callback_invocation_count", None
            )
            if dht_invocations is not None:
                session_diag["dht_callback_invocations"] = dht_invocations
                if dht_invocations == 0:
                    issues_list.append(
                        "DHT callback never invoked (DHT may not be working)"
                    )

            if issues_list:
                connection_issues = diagnostics.get("connection_issues", [])
                if isinstance(connection_issues, list):
                    connection_issues.append(session_diag)
                    diagnostics["connection_issues"] = connection_issues

    return diagnostics


def print_connection_diagnostics(diagnostics: dict[str, Any], console: Console) -> None:
    """Print connection diagnostics in a formatted table.

    Args:
        diagnostics: Diagnostics dictionary from diagnose_connections
        console: Rich console for output

    """
    from rich.table import Table

    console.print(_("\n[cyan]Connection Diagnostics[/cyan]\n"))

    # NAT Status
    console.print(_("[yellow]NAT Status[/yellow]"))
    nat_status = diagnostics.get("nat_status", {})
    if nat_status.get("status") == "not_initialized":
        console.print(_("  [red]✗[/red] NAT manager not initialized"))
    else:
        console.print(_("  Protocol: {protocol}").format(protocol=nat_status.get("active_protocol", "None")))
        console.print(_("  External IP: {ip}").format(ip=nat_status.get("external_ip", "Unknown")))
        console.print(_("  Active Mappings: {mappings}").format(mappings=nat_status.get("mappings", 0)))

    # TCP Server Status
    console.print(_("\n[yellow]TCP Server Status[/yellow]"))
    tcp_status = diagnostics.get("tcp_server_status", {})
    if tcp_status.get("status") == "not_initialized":
        console.print(_("  [red]✗[/red] TCP server not initialized"))
    else:
        running = tcp_status.get("running", False)
        serving = tcp_status.get("is_serving", False)
        console.print(
            _("  Running: {status}").format(status="[green]Yes[/green]" if running else "[red]No[/red]")
        )
        console.print(
            _("  Serving: {status}").format(status="[green]Yes[/green]" if serving else "[red]No[/red]")
        )

    # Session Summary
    console.print(_("\n[yellow]Session Summary[/yellow]"))
    console.print(_("  Total Sessions: {count}").format(count=diagnostics.get("total_sessions", 0)))
    console.print(_("  Sessions with Peers: {count}").format(count=diagnostics.get("sessions_with_peers", 0)))
    console.print(_("  Total Connections: {count}").format(count=diagnostics.get("total_connections", 0)))

    # Connection Issues
    issues = diagnostics.get("connection_issues", [])
    if issues:
        console.print(_("\n[yellow]Connection Issues[/yellow]"))
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Torrent")
        table.add_column("Status")
        table.add_column("Connections")
        table.add_column("Issues")

        for issue in issues:
            issues_str = "; ".join(issue.get("issues", []))
            table.add_row(
                issue.get("name", "Unknown"),
                issue.get("status", "unknown"),
                str(issue.get("connections", 0)),
                issues_str if issues_str else "[green]None[/green]",
            )

        console.print(table)
    else:
        console.print(_("\n[green]✓[/green] No connection issues detected"))
