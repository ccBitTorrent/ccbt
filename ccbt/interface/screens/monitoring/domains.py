"""Queue / Security / Checkpoints / Session / CAS-Hub management screens (WS7).

Each screen lists its executor commands in COMMANDS (inventory-reachable) and
executes them through CommandExecutor; list commands refresh the table.
"""
from __future__ import annotations
from typing import Any, ClassVar
from rich.panel import Panel
from rich.table import Table
from ccbt.interface.screens.base import MonitoringScreen

try:
    from textual.app import ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Button, Footer, Header, Static
except ImportError:  # pragma: no cover
    ComposeResult = Any; Vertical = object; Button = object; Footer = object; Header = object; Static = object

class DomainScreen(MonitoringScreen):
    TITLE = "Domain"
    COMMANDS: ClassVar[tuple[str, ...]] = ()
    LIST_COMMAND: ClassVar[str] = ""
    BINDINGS = [("escape", "back", "Back"), ("q", "quit", "Quit"), ("r", "refresh", "Refresh")]
    def compose(self):  # pragma: no cover
        yield Header()
        with Vertical():
            yield Static(id="domain_panel")
            yield Static(id="domain_help")
        yield Footer()
    async def _refresh_data(self, **overrides):  # pragma: no cover
        panel = self.query_one("#domain_panel", Static); helpw = self.query_one("#domain_help", Static)
        table = Table(title=self.TITLE, expand=True); table.add_column("Command"); table.add_column("Status")
        result_text = ""
        if self.LIST_COMMAND and self._command_executor:
            try:
                r = await self._command_executor.execute_command(self.LIST_COMMAND)
                result_text = str(getattr(r, "data", "") or getattr(r, "error", "") or "")[:400]
            except Exception as e: result_text = str(e)
        for c in self.COMMANDS: table.add_row(c, "available via executor / actions below")
        panel.update(Panel(table, title=self.TITLE))
        helpw.update(Panel(f"Commands: {', '.join(self.COMMANDS)}\n{result_text}", title="Executor"))
    async def action_refresh(self): await self._refresh_data()
    async def run_domain_command(self, command: str, **kwargs):  # pragma: no cover
        if command not in self.COMMANDS: raise ValueError(command)
        if self._command_executor: return await self._command_executor.execute_command(command, **kwargs)
        return None

class QueueManagementScreen(DomainScreen):
    TITLE = "Queue Management"
    LIST_COMMAND = "queue.list"
    COMMANDS = ("queue.list","queue.add","queue.remove","queue.move","queue.pause","queue.resume","queue.clear")

class SecurityManagementScreen(DomainScreen):
    TITLE = "Security / IP Filter"
    LIST_COMMAND = "security.get_ip_filter_stats"
    COMMANDS = ("security.get_ip_filter_stats","security.get_blacklist","security.get_whitelist","security.add_to_blacklist","security.add_to_whitelist","security.remove_from_blacklist","security.remove_from_whitelist","security.load_ip_filter","security.ban_peer")

class CheckpointsManagementScreen(DomainScreen):
    TITLE = "Checkpoints"
    COMMANDS = ("torrent.save_checkpoint","torrent.resume_from_checkpoint","torrent.export_session_state","torrent.import_session_state","checkpoint.backup","checkpoint.restore")

class SessionManagementScreen(DomainScreen):
    TITLE = "Session / Daemon"
    LIST_COMMAND = "session.get_global_stats"
    COMMANDS = ("session.get_global_stats","session.restart_service","torrent.global_pause_all","torrent.global_resume_all","torrent.global_force_start_all","torrent.global_set_rate_limits","torrent.batch_pause","torrent.batch_resume","torrent.batch_remove","torrent.batch_restart")

class TorrentAdvancedScreen(DomainScreen):
    TITLE = "Torrent Advanced / NAT / Peer Limits"
    COMMANDS = ("torrent.cancel","torrent.force_start","torrent.restart","torrent.status","torrent.list","torrent.get_config","torrent.get_option","torrent.set_option","torrent.reset_options","torrent.get_metadata_status","torrent.get_peers","file.list","peer.set_rate_limit","peer.get_rate_limit","peer.set_all_rate_limits","nat.status","nat.discover","nat.map","nat.unmap","nat.refresh","nat.get_external_ip","nat.get_external_port","protocol.get_ipfs","protocol.get_xet")

class PeerDiagnosticsScreen(DomainScreen):
    """Read-only peer/speed diagnostics (same data as `btbt diagnose`)."""
    TITLE = "Peer Diagnostics"
    COMMANDS = ()
    async def _refresh_data(self, **overrides):  # pragma: no cover
        panel = self.query_one("#domain_panel", Static)
        helpw = self.query_one("#domain_help", Static)
        lines: list[str] = []
        try:
            from ccbt.daemon.diagnostics import collect_diagnostics, summarize_torrent
            client = (
                getattr(self.session, "_ipc_client", None)
                or getattr(self.session, "ipc_client", None)
                or getattr(getattr(self.session, "adapter", None), "ipc_client", None)
            )
            if client is not None and hasattr(client, "list_torrents"):
                report = await collect_diagnostics(client)
            elif self._data_provider is not None and hasattr(self._data_provider, "list_torrents"):
                torrents = await self._data_provider.list_torrents()
                report = {"torrents": [{"torrent": t} for t in torrents], "daemon": {}, "nat": {}}
            else:
                report = {"torrents": [], "daemon": {"error": "no IPC client or data provider"}, "nat": {}}
            daemon = report.get("daemon") or {}
            lines.append(f"Daemon: {daemon.get('status', daemon.get('error', '?'))} pid={daemon.get('pid', '?')}")
            lines.append(f"NAT: {report.get('nat')}")
            for entry in report.get("torrents", []):
                s = summarize_torrent(entry)
                lines.append(
                    f"{s['name']}: connected={s['connected_peers']} active={s['active_peers']} "
                    f"productive={s['productive_peers']} requestable={s['requestable_peers']} "
                    f"seeds={s['seeds_connected']} rows={s['peer_rows']} choked={s['choked_peers']} "
                    f"down={s['download_rate']} up={s['upload_rate']}"
                )
        except Exception as e:
            lines.append(f"Diagnostics unavailable: {e}")
        table = Table(title=self.TITLE, expand=True); table.add_column("Daemon-true peer state")
        for line in lines or ["No torrents"]:
            table.add_row(line)
        panel.update(Panel(table, title=self.TITLE))
        helpw.update(Panel("Read-only. Same data as `btbt diagnose`. Press r to refresh, Esc to go back.", title="Info"))

class CasHubManagementScreen(DomainScreen):
    TITLE = "CAS / Hub"
    COMMANDS = ("cas.serve","hub.serve","xet.get_file_tree",)
    async def _refresh_data(self, **overrides):  # pragma: no cover
        # CAS/Hub are served processes (ccbt cas serve / ccbt hub serve), not executor
        # commands; show their CLI entry points + git-xet availability honestly.
        import shutil
        panel = self.query_one("#domain_panel", Static)
        table = Table(title=self.TITLE, expand=True); table.add_column("Service"); table.add_column("State / Command")
        table.add_row("CAS server", "ccbt cas serve (ccbt/cas_server)")
        table.add_row("Hub server", "ccbt hub serve (ccbt/hub/api.py)")
        table.add_row("git-xet", shutil.which("git-xet") or "not on PATH (ccbt/cli/git_xet.py)")
        panel.update(Panel(table, title=self.TITLE))
        helpw = self.query_one("#domain_help", Static); helpw.update(Panel("Start servers from CLI; this panel reports availability.", title="Info"))
