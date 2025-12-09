"""Peers sub-tab screen for Per-Torrent tab.

Displays connected peers for a selected torrent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ccbt.interface.commands.executor import CommandExecutor
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        CommandExecutor = None  # type: ignore[assignment, misc]
        DataProvider = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container
    from textual.widgets import DataTable
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

from ccbt.interface.widgets.reusable_table import ReusableDataTable
from ccbt.i18n import _

logger = logging.getLogger(__name__)


class TorrentPeersScreen(Container):  # type: ignore[misc]
    """Screen for displaying torrent peers."""

    DEFAULT_CSS = """
    TorrentPeersScreen {
        height: 1fr;
        layout: vertical;
    }
    
    #peers-table {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("b", "ban_peer", _("Ban Peer")),
    ]

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        info_hash: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize torrent peers screen.

        Args:
            data_provider: DataProvider instance
            command_executor: CommandExecutor instance
            info_hash: Torrent info hash in hex format
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._info_hash = info_hash
        self._peers_table: DataTable | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the peers screen."""
        yield ReusableDataTable(id="peers-table")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the peers screen."""
        try:
            self._peers_table = self.query_one("#peers-table", DataTable)  # type: ignore[attr-defined]
            
            if self._peers_table:
                self._peers_table.add_columns(
                    _("IP Address"),
                    _("Port"),
                    _("↓ Speed"),
                    _("↑ Speed"),
                    _("Client"),
                    _("Status"),
                )
                self._peers_table.zebra_stripes = True
            
            # Schedule periodic refresh
            self.set_interval(2.0, self.refresh_peers)  # type: ignore[attr-defined]
            # Initial refresh
            self.call_later(self.refresh_peers)  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error mounting peers screen: %s", e)

    async def refresh_peers(self) -> None:  # pragma: no cover
        """Refresh peers table with latest data."""
        if not self._peers_table or not self._data_provider or not self._info_hash:
            return
        
        try:
            peers = await self._data_provider.get_torrent_peers(self._info_hash)
            
            # Clear and repopulate table
            self._peers_table.clear()
            for peer in peers:
                ip = peer.get("ip", "Unknown")
                port = peer.get("port", 0)
                download_rate = peer.get("download_rate", 0.0)
                upload_rate = peer.get("upload_rate", 0.0)
                client = peer.get("client", "?")
                choked = peer.get("choked", False)
                
                # Format speeds
                def format_speed(bps: float) -> str:
                    """Format bytes per second."""
                    if bps >= 1024 * 1024:
                        return f"{bps / (1024 * 1024):.2f} MB/s"
                    elif bps >= 1024:
                        return f"{bps / 1024:.2f} KB/s"
                    return f"{bps:.2f} B/s"
                
                down_str = format_speed(download_rate)
                up_str = format_speed(upload_rate)
                
                # Format status
                status_parts = []
                if choked:
                    status_parts.append(_("Choked"))
                if download_rate > 0:
                    status_parts.append(_("Downloading"))
                if upload_rate > 0:
                    status_parts.append(_("Uploading"))
                status = ", ".join(status_parts) if status_parts else _("Idle")
                
                # Use IP:port as key for row identification
                row_key = f"{ip}:{port}"
                self._peers_table.add_row(
                    ip,
                    str(port),
                    down_str,
                    up_str,
                    client or "?",
                    status,
                    key=row_key,
                )
        except Exception as e:
            logger.debug("Error refreshing peers: %s", e)

    async def action_ban_peer(self) -> None:  # pragma: no cover
        """Ban selected peer (add to blacklist)."""
        if not self._peers_table or not self._command_executor or not self._info_hash:
            return
        
        try:
            # Get selected peer key (IP:port)
            selected_key = self._peers_table.get_selected_key()
            if not selected_key:
                if hasattr(self, "app"):
                    self.app.notify(_("No peer selected"), severity="warning")  # type: ignore[attr-defined]
                return
            
            # Parse IP:port from key
            try:
                ip, port_str = selected_key.rsplit(":", 1)
                port = int(port_str)
            except (ValueError, AttributeError):
                if hasattr(self, "app"):
                    self.app.notify(_("Invalid peer selection"), severity="error")  # type: ignore[attr-defined]
                return
            
            # Use security.ban_peer executor command
            try:
                result = await self._command_executor.execute_command(
                    "security.ban_peer",
                    ip=ip,
                    reason=f"Banned from torrent {self._info_hash[:8]}",
                )
                
                if result and hasattr(result, "success") and result.success:
                    if hasattr(self, "app"):
                        self.app.notify(_("Peer {ip}:{port} banned").format(ip=ip, port=port), severity="success")  # type: ignore[attr-defined]
                    # Refresh peers list
                    await self.refresh_peers()
                else:
                    error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                    if hasattr(self, "app"):
                        self.app.notify(_("Failed to ban peer: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
            except Exception as e:
                # Executor command may not exist - log and show message
                logger.warning("Peer ban command not available: %s", e)
                if hasattr(self, "app"):
                    self.app.notify(  # type: ignore[attr-defined]
                        _("Peer banning not yet implemented. Selected peer: {ip}:{port}").format(ip=ip, port=port),
                        severity="info",
                    )
        except Exception as e:
            logger.debug("Error banning peer: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error banning peer: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]


