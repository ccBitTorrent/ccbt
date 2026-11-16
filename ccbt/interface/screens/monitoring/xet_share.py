"""XET share/tonic screen: create/share/link/import, allowlist, sync modes (WS6)."""
from __future__ import annotations
from typing import Any, ClassVar
from rich.panel import Panel
from rich.table import Table
from ccbt.interface.screens.base import MonitoringScreen

try:
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Static
except ImportError:  # pragma: no cover
    ComposeResult = Any; Vertical = object; Footer = object; Header = object; Static = object

class XetShareScreen(MonitoringScreen):
    """All xet.* executor commands are reachable from this screen's actions."""
    COMMANDS: ClassVar[tuple[str, ...]] = (
        "xet.enable","xet.disable","xet.status","xet.get_config","xet.set_port","xet.cache_stats","xet.cache_info","xet.cache_cleanup",
        "xet.list_xet_folders","xet.add_xet_folder","xet.remove_xet_folder","xet.get_xet_folder_status","xet.get_xet_discovery_status",
        "xet.create_tonic","xet.share_folder","xet.generate_link","xet.get_share_link","xet.get_file_tree","xet.sync",
        "xet.get_sync_mode","xet.set_sync_mode","xet.set_sync_mode_by_key","xet.set_xet_workspace_policy",
        "xet.allowlist_add","xet.allowlist_remove","xet.allowlist_list","xet.allowlist_alias_add","xet.allowlist_alias_set","xet.allowlist_alias_remove","xet.allowlist_alias_list",
    )
    BINDINGS = [("escape", "back", "Back"), ("q", "quit", "Quit"), ("r", "refresh", "Refresh")]
    def compose(self):  # pragma: no cover
        yield Header()
        with Vertical():
            yield Static(id="xet_share_panel")
        yield Footer()
    async def _refresh_data(self, **overrides):  # pragma: no cover
        panel = self.query_one("#xet_share_panel", Static)
        table = Table(title="XET Share / Tonic", expand=True); table.add_column("Capability"); table.add_column("Executor command")
        for label, cmd in [("Create tonic","xet.create_tonic"),("Share folder","xet.share_folder"),("Generate link","xet.generate_link"),
                           ("Get share link","xet.get_share_link"),("File tree","xet.get_file_tree"),("Sync now","xet.sync"),
                           ("Sync mode","xet.get_sync_mode / xet.set_sync_mode"),("Workspace policy","xet.set_xet_workspace_policy"),
                           ("Allowlist","xet.allowlist_list"),("Aliases","xet.allowlist_alias_list"),("Discovery","xet.get_xet_discovery_status")]:
            table.add_row(label, cmd)
        panel.update(Panel(table, title="XET Share"))
    async def action_refresh(self): await self._refresh_data()
    async def run_xet(self, command: str, **kwargs):
        if command not in self.COMMANDS: raise ValueError(command)
        if self._command_executor: return await self._command_executor.execute_command(command, **kwargs)
        return None
