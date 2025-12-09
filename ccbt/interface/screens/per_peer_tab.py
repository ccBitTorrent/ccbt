"""Per-Peer tab content for terminal dashboard.

Displays global peer metrics across all torrents with detailed peer information.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from ccbt.i18n import _

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ccbt.interface.data_provider import DataProvider
    from ccbt.interface.commands.executor import CommandExecutor
else:
    try:
        from ccbt.interface.data_provider import DataProvider
        from ccbt.interface.commands.executor import CommandExecutor
    except ImportError:
        # Fallback for when modules are not available
        class DataProvider:  # type: ignore[no-redef]
            pass

        class CommandExecutor:  # type: ignore[no-redef]
            pass

try:
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import DataTable, Static
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass


class PerPeerTabContent(Container):  # type: ignore[misc]
    """Per-peer tab content with global peers table and detailed peer information."""

    DEFAULT_CSS = """
    PerPeerTabContent {
        layout: vertical;
        height: 1fr;
    }
    
    #peer-summary {
        height: 3;
        border: solid $primary;
        padding: 1;
    }
    
    #peer-tables-container {
        height: 1fr;
        layout: horizontal;
    }
    
    #global-peers-table-container {
        width: 1fr;
        border: solid $primary;
        padding: 1;
    }
    
    #peer-detail-container {
        width: 1fr;
        border: solid $primary;
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
    }
    """

    def __init__(
        self,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize per-peer tab content.

        Args:
            data_provider: DataProvider for fetching peer metrics
            command_executor: CommandExecutor for executing commands
        """
        super().__init__(*args, **kwargs)
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._global_peers_table: DataTable | None = None
        self._peer_detail_table: DataTable | None = None
        self._summary_widget: Static | None = None
        self._selected_peer_key: str | None = None
        self._update_task: Any | None = None

    def compose(self) -> Any:  # pragma: no cover
        """Compose the per-peer tab content."""
        # Summary widget
        yield Static(_("Loading peer metrics..."), id="peer-summary")
        
        # Tables container
        with Container(id="peer-tables-container"):
            # Global peers table
            with Container(id="global-peers-table-container"):
                yield Static(_("Global Connected Peers"), id="global-peers-title")
                yield DataTable(id="global-peers-table")
            
            # Peer detail container
            with Container(id="peer-detail-container"):
                yield Static(_("Peer Details"), id="peer-detail-title")
                yield DataTable(id="peer-detail-table")

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the per-peer tab content."""
        try:
            self._summary_widget = self.query_one("#peer-summary", Static)  # type: ignore[attr-defined]
            self._global_peers_table = self.query_one("#global-peers-table", DataTable)  # type: ignore[attr-defined]
            self._peer_detail_table = self.query_one("#peer-detail-table", DataTable)  # type: ignore[attr-defined]
            
            # Initialize tables
            if self._global_peers_table:
                self._global_peers_table.add_columns(
                    _("IP:Port"),
                    _("Client"),
                    _("Download Rate"),
                    _("Upload Rate"),
                    _("Torrents"),
                    _("Duration"),
                )
                # Enable row selection
                self._global_peers_table.cursor_type = "row"  # type: ignore[attr-defined]
            
            if self._peer_detail_table:
                self._peer_detail_table.add_columns(
                    _("Metric"),
                    _("Value"),
                )
            
            # Start update loop
            self._start_updates()
        except Exception as e:
            logger.error("Error mounting per-peer tab: %s", e, exc_info=True)

    def _start_updates(self) -> None:  # pragma: no cover
        """Start the update loop."""
        try:
            if self._update_task:
                self._update_task.cancel()
            
            async def update_loop() -> None:
                # CRITICAL FIX: Use app's event loop for task creation
                loop = None
                try:
                    if hasattr(self.app, "loop"):
                        loop = self.app.loop  # type: ignore[attr-defined]
                    else:
                        loop = asyncio.get_event_loop()
                except Exception:
                    loop = asyncio.get_event_loop()
                
                while True:
                    try:
                        # CRITICAL FIX: Only update if widget is visible and attached
                        if self.is_attached and self.display:  # type: ignore[attr-defined]
                            await self._update_peer_data()
                        await asyncio.sleep(1.0)  # CRITICAL FIX: Reduced from 2.0s to 1.0s for tighter updates
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error("Error in peer update loop: %s", e, exc_info=True)
                        await asyncio.sleep(2.0)
            
            # CRITICAL FIX: Use app's event loop for task creation
            try:
                if hasattr(self.app, "loop"):
                    self._update_task = self.app.loop.create_task(update_loop())  # type: ignore[attr-defined]
                else:
                    self._update_task = asyncio.create_task(update_loop())
            except Exception:
                self._update_task = asyncio.create_task(update_loop())
        except Exception as e:
            logger.error("Error starting peer update loop: %s", e, exc_info=True)

    async def _update_peer_data(self) -> None:  # pragma: no cover
        """Update peer data from data provider."""
        if not self._data_provider:
            logger.warning("PerPeerTabContent: Missing data provider, cannot update peer data")
            return
        
        # CRITICAL FIX: Ensure widget is visible and attached before updating
        if not self.is_attached or not self.display:  # type: ignore[attr-defined]
            logger.debug("PerPeerTabContent: Widget not attached or not visible, skipping update")
            return
        
        try:
            logger.debug("PerPeerTabContent: Fetching peer metrics from data provider...")
            metrics = await self._data_provider.get_peer_metrics()
            logger.debug("PerPeerTabContent: Retrieved peer metrics: total_peers=%d, active_peers=%d, peers_count=%d",
                        metrics.get("total_peers", 0),
                        metrics.get("active_peers", 0),
                        len(metrics.get("peers", [])))
            
            # Update summary
            if self._summary_widget:
                total_peers = metrics.get("total_peers", 0)
                active_peers = metrics.get("active_peers", 0)
                summary_text = _("Total Peers: {total} | Active Peers: {active}").format(
                    total=total_peers,
                    active=active_peers,
                )
                self._summary_widget.update(summary_text)  # type: ignore[attr-defined]
            
            # Update global peers table
            if self._global_peers_table:
                # CRITICAL FIX: Ensure table is visible and attached before populating
                if not self._global_peers_table.is_attached or not self._global_peers_table.display:  # type: ignore[attr-defined]
                    logger.debug("PerPeerTabContent: Table not attached or not visible, skipping population")
                    return
                
                self._global_peers_table.clear()  # type: ignore[attr-defined]
                # CRITICAL FIX: Ensure columns exist (clear() might remove them)
                if not self._global_peers_table.columns:  # type: ignore[attr-defined]
                    self._global_peers_table.add_columns(
                        _("IP:Port"),
                        _("Client"),
                        _("Download Rate"),
                        _("Upload Rate"),
                        _("Torrents"),
                        _("Duration"),
                    )
                
                peers = metrics.get("peers", [])
                logger.debug("PerPeerTabContent: Processing %d peers for table", len(peers))
                for peer in peers:
                    peer_key = peer.get("peer_key", "unknown")
                    ip = peer.get("ip", "unknown")
                    port = peer.get("port", 0)
                    client = peer.get("client") or "?"
                    download_rate = peer.get("total_download_rate", 0.0)
                    upload_rate = peer.get("total_upload_rate", 0.0)
                    info_hashes = peer.get("info_hashes", [])
                    connection_duration = peer.get("connection_duration", 0.0)
                    
                    # Format rates
                    def format_rate(rate: float) -> str:
                        if rate >= 1024 * 1024:
                            return f"{rate / (1024 * 1024):.1f} MB/s"
                        elif rate >= 1024:
                            return f"{rate / 1024:.1f} KB/s"
                        else:
                            return f"{rate:.1f} B/s"
                    
                    # Format duration
                    def format_duration(seconds: float) -> str:
                        if seconds < 60:
                            return f"{seconds:.0f}s"
                        elif seconds < 3600:
                            return f"{seconds / 60:.1f}m"
                        else:
                            return f"{seconds / 3600:.1f}h"
                    
                    self._global_peers_table.add_row(  # type: ignore[attr-defined]
                        f"{ip}:{port}",
                        client,
                        format_rate(download_rate),
                        format_rate(upload_rate),
                        str(len(info_hashes)),
                        format_duration(connection_duration),
                        key=peer_key,
                    )
                
                logger.debug("PerPeerTabContent: Added peer %s:%d to table", ip, port)
            
            logger.debug("PerPeerTabContent: Added %d peers to table", len(peers))
            
            # CRITICAL FIX: Force table refresh and ensure visibility
            if hasattr(self._global_peers_table, "refresh"):
                self._global_peers_table.refresh()  # type: ignore[attr-defined]
            self._global_peers_table.display = True  # type: ignore[attr-defined]
            
            # Update peer detail if a peer is selected
            if self._selected_peer_key and self._peer_detail_table:
                await self._update_peer_detail(self._selected_peer_key, metrics)
        except Exception as e:
            logger.error("Error updating peer data: %s", e, exc_info=True)
            # Update summary with error message
            if self._summary_widget:
                self._summary_widget.update(_("Error loading peer data: {error}").format(error=str(e)))  # type: ignore[attr-defined]

    async def _update_peer_detail(self, peer_key: str, metrics: dict[str, Any]) -> None:  # pragma: no cover
        """Update peer detail table for selected peer."""
        if not self._peer_detail_table:
            return
        
        try:
            peers = metrics.get("peers", [])
            peer_data = None
            for peer in peers:
                if peer.get("peer_key") == peer_key:
                    peer_data = peer
                    break
            
            if not peer_data:
                self._peer_detail_table.clear()  # type: ignore[attr-defined]
                self._peer_detail_table.add_row(_("Peer not found"), "")  # type: ignore[attr-defined]
                return
            
            self._peer_detail_table.clear()  # type: ignore[attr-defined]
            
            # Add peer details
            self._peer_detail_table.add_row(_("IP Address"), peer_data.get("ip", "unknown"))  # type: ignore[attr-defined]
            self._peer_detail_table.add_row(_("Port"), str(peer_data.get("port", 0)))  # type: ignore[attr-defined]
            self._peer_detail_table.add_row(_("Client"), peer_data.get("client") or "?")  # type: ignore[attr-defined]
            self._peer_detail_table.add_row(_("Choked"), "Yes" if peer_data.get("choked") else "No")  # type: ignore[attr-defined]
            
            # Format rates
            def format_rate(rate: float) -> str:
                if rate >= 1024 * 1024:
                    return f"{rate / (1024 * 1024):.2f} MB/s"
                elif rate >= 1024:
                    return f"{rate / 1024:.2f} KB/s"
                else:
                    return f"{rate:.2f} B/s"
            
            self._peer_detail_table.add_row(_("Download Rate"), format_rate(peer_data.get("total_download_rate", 0.0)))  # type: ignore[attr-defined]
            self._peer_detail_table.add_row(_("Upload Rate"), format_rate(peer_data.get("total_upload_rate", 0.0)))  # type: ignore[attr-defined]
            
            # Format bytes
            def format_bytes(bytes_val: int) -> str:
                if bytes_val >= 1024 * 1024 * 1024:
                    return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"
                elif bytes_val >= 1024 * 1024:
                    return f"{bytes_val / (1024 * 1024):.2f} MB"
                elif bytes_val >= 1024:
                    return f"{bytes_val / 1024:.2f} KB"
                else:
                    return f"{bytes_val} B"
            
            self._peer_detail_table.add_row(_("Bytes Downloaded"), format_bytes(peer_data.get("total_bytes_downloaded", 0)))  # type: ignore[attr-defined]
            self._peer_detail_table.add_row(_("Bytes Uploaded"), format_bytes(peer_data.get("total_bytes_uploaded", 0)))  # type: ignore[attr-defined]
            
            # Format duration
            duration = peer_data.get("connection_duration", 0.0)
            if duration < 60:
                duration_str = f"{duration:.0f} seconds"
            elif duration < 3600:
                duration_str = f"{duration / 60:.1f} minutes"
            else:
                duration_str = f"{duration / 3600:.1f} hours"
            self._peer_detail_table.add_row(_("Connection Duration"), duration_str)  # type: ignore[attr-defined]
            
            # Pieces info
            self._peer_detail_table.add_row(_("Pieces Received"), str(peer_data.get("pieces_received", 0)))  # type: ignore[attr-defined]
            self._peer_detail_table.add_row(_("Pieces Served"), str(peer_data.get("pieces_served", 0)))  # type: ignore[attr-defined]
            
            # Latency
            latency = peer_data.get("request_latency", 0.0)
            if latency > 0.0:
                self._peer_detail_table.add_row(_("Request Latency"), f"{latency * 1000:.1f} ms")  # type: ignore[attr-defined]
            
            # Torrents
            info_hashes = peer_data.get("info_hashes", [])
            self._peer_detail_table.add_row(_("Connected Torrents"), str(len(info_hashes)))  # type: ignore[attr-defined]
            if info_hashes:
                # Show first few info hashes
                hashes_str = ", ".join(info_hashes[:3])
                if len(info_hashes) > 3:
                    hashes_str += f" ... (+{len(info_hashes) - 3} more)"
                self._peer_detail_table.add_row(_("Info Hashes"), hashes_str)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Error updating peer detail: %s", e, exc_info=True)

    def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle row selection in global peers table."""
        try:
            if event.data_table.id == "global-peers-table":  # type: ignore[attr-defined]
                row_key = event.data_table.get_row_key(event.cursor_row)  # type: ignore[attr-defined]
                if row_key:
                    self._selected_peer_key = str(row_key)
                    # Trigger update to show peer detail
                    asyncio.create_task(self._update_peer_data())
        except Exception as e:
            logger.debug("Error handling row selection: %s", e)

    def on_unmount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Unmount the per-peer tab content."""
        if self._update_task:
            self._update_task.cancel()
            self._update_task = None

