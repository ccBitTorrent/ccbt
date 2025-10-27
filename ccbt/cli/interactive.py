"""Interactive CLI for ccBitTorrent.

Provides rich interactive interface with:
- Real-time statistics
- Live progress updates
- Interactive commands
- Tab completion
- Help system
"""

import asyncio
from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

from ..config import ConfigManager, reload_config
from ..models import TorrentInfo
from ..session import AsyncSessionManager
from .progress import ProgressManager


class InteractiveCLI:
    """Interactive CLI interface."""
    
    def __init__(self, session: AsyncSessionManager, console: Console):
        self.session = session
        self.console = console
        self.running = False
        self.current_torrent: Optional[Dict[str, Any]] = None
        self.layout = Layout()
        self.live_display: Optional[Live] = None
        
        # Statistics
        self.stats = {
            "download_speed": 0,
            "upload_speed": 0,
            "peers_connected": 0,
            "pieces_completed": 0,
            "pieces_total": 0,
        }

        # Track current torrent info-hash (hex) for control commands
        self.current_info_hash_hex: Optional[str] = None
        self._last_peers: List[Dict[str, Any]] = []

        # Download progress widgets
        self._download_progress: Optional[Progress] = None
        self._download_task: Optional[int] = None
        self.progress_manager = ProgressManager(self.console)
        
        # Commands
        self.commands = {
            "help": self.cmd_help,
            "status": self.cmd_status,
            "peers": self.cmd_peers,
            "files": self.cmd_files,
            "pause": self.cmd_pause,
            "resume": self.cmd_resume,
            "stop": self.cmd_stop,
            "quit": self.cmd_quit,
            "clear": self.cmd_clear,
            "config": self.cmd_config,
            "limits": self.cmd_limits,
            "strategy": self.cmd_strategy,
            "discovery": self.cmd_discovery,
            "disk": self.cmd_disk,
            "network": self.cmd_network,
            "checkpoint": self.cmd_checkpoint,
            "metrics": self.cmd_metrics,
            "alerts": self.cmd_alerts,
            "export": self.cmd_export,
            "import": self.cmd_import,
            "backup": self.cmd_backup,
            "restore": self.cmd_restore,
        }
    
    async def run(self) -> None:
        """Run interactive CLI."""
        self.running = True
        
        # Setup layout
        self.setup_layout()
        
        # Start live display
        with Live(self.layout, console=self.console, refresh_per_second=2) as live:
            self.live_display = live
            
            # Show welcome message
            self.show_welcome()
            
            # Main loop
            while self.running:
                try:
                    await self.update_display()
                    await asyncio.sleep(0.5)
                except KeyboardInterrupt:
                    break
    
    async def download_torrent(self, torrent_data: Dict[str, Any], resume: bool = False) -> None:
        """Download a torrent interactively."""
        self.current_torrent = torrent_data
        
        # Add torrent to session with resume option
        info_hash_hex = await self.session.add_torrent(torrent_data, resume=resume)
        self.current_info_hash_hex = info_hash_hex
        
        # Show download interface
        self.show_download_interface()
        
        # Wait for completion
        while self.running:
            torrent_status = await self.session.get_torrent_status(info_hash_hex)
            if not torrent_status:
                break
                
            if torrent_status.get("status") == "seeding":
                torrent_name = torrent_data.get("name", "Unknown")
                self.console.print(f"[green]Download completed: {torrent_name}[/green]")
                break
                
            await self.update_download_stats()
            await asyncio.sleep(1)
    
    def setup_layout(self) -> None:
        """Setup the layout."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )
        
        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
    
    def show_welcome(self) -> None:
        """Show welcome message."""
        welcome_text = Text("ccBitTorrent Interactive CLI", style="bold blue")
        self.layout["header"].update(Panel(welcome_text, title="Welcome"))
    
    def show_download_interface(self) -> None:
        """Show download interface."""
        if not self.current_torrent:
            return
        
        # Create download panel with live progress and info
        download_render = self.create_download_panel()
        self.layout["left"].update(download_render)
        
        # Create peers panel
        peers_panel = self.create_peers_panel()
        self.layout["right"].update(peers_panel)
        
        # Create status panel
        status_panel = self.create_status_panel()
        self.layout["footer"].update(status_panel)
    
    def create_download_panel(self) -> Panel:
        """Create download information panel."""
        if not self.current_torrent:
            return Panel("No torrent active", title="Download")
        
        torrent = self.current_torrent or {}
        name = torrent.get("name") or getattr(torrent, "name", "Unknown")
        
        # Ensure a reusable Progress exists
        if self._download_progress is None or self._download_task is None:
            # Use shared ProgressManager for consistent formatting
            self._download_progress = self.progress_manager.create_download_progress(torrent)  # type: ignore[arg-type]
            self._download_task = self._download_progress.add_task(
                f"Downloading {name}", total=100, completed=0, downloaded="-", speed="-"
        )
        
        # Create info table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        total_size = torrent.get("total_size") or getattr(torrent, "total_size", 0) or torrent.get("total_length") or getattr(torrent, "total_length", 0)
        downloaded_bytes = torrent.get("downloaded_bytes") or getattr(torrent, "downloaded_bytes", 0)
        # Progress percentage (best-effort; updated live in update_download_stats)
        progress_val = 0.0
        table.add_row("Name", str(name))
        table.add_row("Size", f"{(total_size or 0) / (1024*1024*1024):.2f} GB")
        table.add_row("Progress", f"{progress_val:.1f}%")
        table.add_row("Downloaded", f"{(downloaded_bytes or 0) / (1024*1024):.2f} MB")
        table.add_row("Download Speed", f"{self.stats['download_speed'] / 1024:.2f} KB/s")
        table.add_row("Upload Speed", f"{self.stats['upload_speed'] / 1024:.2f} KB/s")
        # ETA calculation (best-effort)
        def _fmt_eta(sec: float) -> str:
            sec = int(max(0, sec))
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"
        eta_str = "-"
        try:
            rate = float(self.stats.get("download_speed", 0.0))
            if rate > 0 and total_size and downloaded_bytes is not None:
                remaining = max(0.0, float(total_size) - float(downloaded_bytes))
                eta_str = _fmt_eta(remaining / rate)
        except Exception:
            eta_str = "-"
        table.add_row("ETA", eta_str)
        table.add_row("Peers", str(self.stats["peers_connected"]))
        table.add_row("Pieces", f"{self.stats['pieces_completed']}/{self.stats['pieces_total']}")
        
        # Stack progress and details
        group = Group(self._download_progress, table)
        return Panel(group, title="Download")
    
    def create_peers_panel(self) -> Panel:
        """Create peers information panel."""
        if not self.current_torrent:
            return Panel("No torrent active", title="Peers")
        
        peers = self._last_peers
        if not peers:
            return Panel("No peers connected", title="Peers")
        
        # Create peers table
        table = Table(title="Connected Peers")
        table.add_column("IP", style="cyan")
        table.add_column("Port", style="white")
        table.add_column("Download", style="green")
        table.add_column("Upload", style="yellow")
        table.add_column("Progress", style="blue")
        
        peers_list = list(peers) if isinstance(peers, list) else []
        for peer in peers_list[:10]:  # Show top 10 peers
            ip = str(peer.get("ip", "-"))
            port = str(peer.get("port", "-"))
            d = float(peer.get("download_rate", 0.0)) / 1024.0
            u = float(peer.get("upload_rate", 0.0)) / 1024.0
            table.add_row(ip, port, f"{d:.1f} KB/s", f"{u:.1f} KB/s", "-")
        
        return Panel(table, title="Peers")
    
    def create_status_panel(self) -> Panel:
        """Create status panel."""
        status_text = Text()
        status_text.append("Status: ", style="bold")
        status_text.append("Running", style="green")
        status_text.append(" | ")
        status_text.append("Commands: ", style="bold")
        status_text.append(
            "help, status, peers, files, pause, resume, stop, config, limits, strategy, discovery, checkpoint, metrics, alerts, export, import, backup, restore",
            style="white",
        )
        
        return Panel(status_text, title="Status")
    
    async def update_display(self) -> None:
        """Update the display."""
        if self.current_torrent:
            await self.update_download_stats()
            self.show_download_interface()
    
    async def update_download_stats(self) -> None:
        """Update download statistics."""
        if not self.current_torrent:
            return
        
        # Prefer session-derived status if available
        try:
            st = None
            if self.current_info_hash_hex:
                st = await self.session.get_torrent_status(self.current_info_hash_hex)
            if st:
                self.stats["download_speed"] = float(st.get("download_rate", 0.0))
                self.stats["upload_speed"] = float(st.get("upload_rate", 0.0))
                self.stats["pieces_completed"] = int(st.get("pieces_completed", 0))
                self.stats["pieces_total"] = int(st.get("pieces_total", 0))
                # Peers count
                try:
                    peers = await self.session.get_peers_for_torrent(self.current_info_hash_hex) if self.current_info_hash_hex else []  # type: ignore[arg-type]
                except Exception:
                    peers = []
                self._last_peers = peers or []
                self.stats["peers_connected"] = len(self._last_peers)

                # Update live progress
                if self._download_progress is not None and self._download_task is not None:
                    prog_frac = float(st.get("progress", 0.0))
                    completed = max(0, min(100, int(prog_frac * 100)))
                    def _fmt_bytes(n: float) -> str:
                        units = ["B", "KB", "MB", "GB", "TB"]
                        i = 0
                        while n >= 1024 and i < len(units) - 1:
                            n /= 1024.0
                            i += 1
                        return f"{n:.1f} {units[i]}"
                    self._download_progress.update(
                        self._download_task,
                        completed=completed,
                        downloaded=_fmt_bytes(float(st.get("downloaded_bytes", 0.0))),
                        speed=f"{self.stats['download_speed']/1024:.1f} KB/s",
                        refresh=True,
                    )
            else:
                torrent = self.current_torrent or {}
                self.stats["download_speed"] = getattr(torrent, "download_speed", 0) or torrent.get("download_speed", 0)
                self.stats["upload_speed"] = getattr(torrent, "upload_speed", 0) or torrent.get("upload_speed", 0)
                self.stats["pieces_completed"] = getattr(torrent, "completed_pieces", 0) or torrent.get("completed_pieces", 0)
                self.stats["pieces_total"] = getattr(torrent, "total_pieces", 0) or torrent.get("total_pieces", 0)
        except Exception:
            pass
    
    async def cmd_help(self, args: List[str]) -> None:
        """Show help."""
        help_text = """
Available Commands:
  help          - Show this help message
  status        - Show current status
  peers         - Show connected peers
  files         - Show file information
  pause         - Pause download
  resume        - Resume download
  stop          - Stop download
  quit          - Quit application
  clear         - Clear screen
        """
        
        self.console.print(Panel(help_text, title="Help"))
    
    async def cmd_status(self, args: List[str]) -> None:
        """Show status."""
        if not self.current_torrent:
            self.console.print("No torrent active")
            return
        
        torrent = self.current_torrent or {}
        
        # Create status table
        table = Table(title="Torrent Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        name = torrent.get("name") or getattr(torrent, "name", "Unknown")
        total_size = torrent.get("total_size") or getattr(torrent, "total_size", 0)
        progress_val = 0
        if hasattr(torrent, "progress_percentage"):
            try:
                progress_val = int(getattr(torrent, "progress_percentage")())
            except Exception:
                progress_val = 0
        table.add_row("Name", str(name))
        table.add_row("Size", f"{(total_size or 0) / (1024*1024*1024):.2f} GB")
        table.add_row("Progress", f"{progress_val:.1f}%")
        downloaded_bytes = torrent.get('downloaded_bytes') if isinstance(torrent, dict) else getattr(torrent, 'downloaded_bytes', 0)
        table.add_row("Downloaded", f"{(downloaded_bytes or 0) / (1024*1024):.2f} MB")
        table.add_row("Download Speed", f"{self.stats['download_speed'] / 1024:.2f} KB/s")
        table.add_row("Upload Speed", f"{self.stats['upload_speed'] / 1024:.2f} KB/s")
        table.add_row("Peers", str(self.stats["peers_connected"]))
        table.add_row("Pieces", f"{self.stats['pieces_completed']}/{self.stats['pieces_total']}")
        
        self.console.print(table)
    
    async def cmd_peers(self, args: List[str]) -> None:
        """Show peers."""
        if not self.current_torrent:
            self.console.print("No torrent active")
            return
        
        peers = []
        if hasattr(self.session, "get_peers_for_torrent") and self.current_info_hash_hex:
            try:
                peers = await self.session.get_peers_for_torrent(self.current_info_hash_hex)  # type: ignore[attr-defined]
            except Exception:
                peers = []
        
        if not peers:
            self.console.print("No peers connected")
            return
        
        # Create peers table
        table = Table(title="Connected Peers")
        table.add_column("IP", style="cyan")
        table.add_column("Port", style="white")
        table.add_column("Download", style="green")
        table.add_column("Upload", style="yellow")
        table.add_column("Progress", style="blue")
        
        for peer in (peers if isinstance(peers, list) else []):
            ip = getattr(peer, "ip", None)
            port = getattr(peer, "port", None)
            d = getattr(peer, "download_speed", None)
            u = getattr(peer, "upload_speed", None)
            prog = getattr(peer, "progress_percentage", None)
            if isinstance(peer, dict):
                ip = peer.get("ip", ip)
                port = peer.get("port", port)
                d = peer.get("download_rate", d)
                u = peer.get("upload_rate", u)
            dkb = (float(d) / 1024.0) if isinstance(d, (int, float)) else 0.0
            ukb = (float(u) / 1024.0) if isinstance(u, (int, float)) else 0.0
            prog_val = 0.0
            if callable(prog):
                try:
                    prog_val = float(prog())
                except Exception:
                    prog_val = 0.0
            table.add_row(str(ip or "-"), str(port or "-"), f"{dkb:.1f} KB/s", f"{ukb:.1f} KB/s", f"{prog_val:.1f}%")
        
        self.console.print(table)
    
    async def cmd_files(self, args: List[str]) -> None:
        """Show files."""
        if not self.current_torrent:
            self.console.print("No torrent active")
            return
        
        torrent = self.current_torrent or {}
        
        # Create files table
        table = Table(title="Files")
        table.add_column("Name", style="cyan")
        table.add_column("Size", style="white")
        table.add_column("Progress", style="green")
        table.add_column("Priority", style="yellow")
        
        for file_info in (getattr(torrent, "files", None) or torrent.get("files", [])):
            name_f = getattr(file_info, "name", None) or getattr(file_info, "path", "?")
            length_f = getattr(file_info, "length", 0)
            prog = getattr(file_info, "progress_percentage", None)
            prog_val = 0.0
            if callable(prog):
                try:
                    prog_val = float(prog())
                except Exception:
                    prog_val = 0.0
            priority_name = getattr(getattr(file_info, "priority", None), "name", "-")
            table.add_row(str(name_f), f"{length_f / (1024*1024):.2f} MB", f"{prog_val:.1f}%", str(priority_name))
        
        self.console.print(table)
    
    async def cmd_pause(self, args: List[str]) -> None:
        """Pause download."""
        if not self.current_torrent:
            self.console.print("No torrent active")
            return
        
        if hasattr(self.session, "pause_torrent") and self.current_info_hash_hex:
            await self.session.pause_torrent(self.current_info_hash_hex)
        self.console.print("Download paused")
    
    async def cmd_resume(self, args: List[str]) -> None:
        """Resume download."""
        if not self.current_torrent:
            self.console.print("No torrent active")
            return
        
        if hasattr(self.session, "resume_torrent") and self.current_info_hash_hex:
            await self.session.resume_torrent(self.current_info_hash_hex)
        self.console.print("Download resumed")
    
    async def cmd_stop(self, args: List[str]) -> None:
        """Stop download."""
        if not self.current_torrent:
            self.console.print("No torrent active")
            return
        
        # Use remove() to stop and remove torrent from session
        if not hasattr(self.session, "remove") or not self.current_info_hash_hex:
            self.console.print("Operation not supported")
            return
        await self.session.remove(self.current_info_hash_hex)  # type: ignore[arg-type]
        self.console.print("Download stopped")
    
    async def cmd_quit(self, args: List[str]) -> None:
        """Quit application."""
        if Confirm.ask("Are you sure you want to quit?"):
            self.running = False
    
    async def cmd_clear(self, args: List[str]) -> None:
        """Clear screen."""
        self.console.clear()
    
    async def cmd_limits(self, args: List[str]) -> None:
        """Show or set per-torrent rate limits.

        Usage:
          limits show <info_hash>
          limits set <info_hash> <down_kib> <up_kib>
        """
        if len(args) < 2:
            self.console.print("Usage: limits [show|set] <info_hash> [down up]")
            return
        action, info_hash = args[0], args[1]
        if action == "show":
            st = await self.session.get_torrent_status(info_hash)
            if not st:
                self.console.print("Torrent not found")
                return
            self.console.print(st)
        elif action == "set":
            if len(args) < 4:
                self.console.print("Usage: limits set <info_hash> <down_kib> <up_kib>")
                return
            down, up = int(args[2]), int(args[3])
            if hasattr(self.session, "set_rate_limits"):
                ok = await self.session.set_rate_limits(info_hash, down, up)  # type: ignore[attr-defined]
                self.console.print("OK" if ok else "Failed")
            else:
                self.console.print("Not supported")
        else:
            self.console.print("Unknown subcommand")

    async def cmd_strategy(self, args: List[str]) -> None:
        """Show/set strategy configuration.

        Usage:
          strategy show
          strategy piece_selection <round_robin|rarest_first|sequential>
        """
        from ..config import get_config
        cfg = get_config()
        if not args or args[0] == "show":
            self.console.print({"piece_selection": cfg.strategy.piece_selection, "endgame_threshold": cfg.strategy.endgame_threshold})
            return
        if args[0] == "piece_selection" and len(args) > 1:
            try:
                cfg.strategy.piece_selection = args[1]  # type: ignore[assignment]
                self.console.print("OK")
            except Exception as e:
                self.console.print(f"[red]{e}[/red]")

    async def cmd_discovery(self, args: List[str]) -> None:
        from ..config import get_config
        cfg = get_config()
        if not args or args[0] == "show":
            self.console.print({"enable_dht": cfg.discovery.enable_dht, "enable_pex": cfg.discovery.enable_pex})
            return
        if args[0] == "dht":
            cfg.discovery.enable_dht = not cfg.discovery.enable_dht
            self.console.print(f"enable_dht={cfg.discovery.enable_dht}")
        elif args[0] == "pex":
            cfg.discovery.enable_pex = not cfg.discovery.enable_pex
            self.console.print(f"enable_pex={cfg.discovery.enable_pex}")

    async def cmd_disk(self, args: List[str]) -> None:
        from ..config import get_config
        cfg = get_config()
        self.console.print({
            "preallocate": cfg.disk.preallocate,
            "write_batch_kib": cfg.disk.write_batch_kib,
            "use_mmap": cfg.disk.use_mmap,
        })

    async def cmd_network(self, args: List[str]) -> None:
        from ..config import get_config
        cfg = get_config()
        self.console.print({
            "listen_port": cfg.network.listen_port,
            "pipeline_depth": cfg.network.pipeline_depth,
            "block_size_kib": cfg.network.block_size_kib,
        })

    async def cmd_checkpoint(self, args: List[str]) -> None:
        """List checkpoints (basic).

        Usage:
          checkpoint list
        """
        if not args or args[0] != "list":
            self.console.print("Usage: checkpoint list")
            return
        from ..checkpoint import CheckpointManager
        from ..config import get_config
        cm = CheckpointManager(get_config().disk)
        items = await cm.list_checkpoints()
        lines = [f"{it.info_hash.hex()} {it.format.value} {it.size}B" for it in items]
        self.console.print("\n".join(lines) if lines else "No checkpoints")

    async def cmd_metrics(self, args: List[str]) -> None:
        """Show metrics snapshot or export.

        Usage:
          metrics show [system|performance|all]
          metrics export [json|prometheus] [output]
        """
        from ..monitoring import MetricsCollector
        import json
        if not args or args[0] == "show":
            scope = args[1] if len(args) > 1 else "all"
            mc = MetricsCollector()
            try:
                await mc._collect_system_metrics()  # type: ignore[attr-defined]
                await mc._collect_performance_metrics()  # type: ignore[attr-defined]
            except Exception:
                pass
            payload: Dict[str, Any] = {}
            if scope in ("all", "system"):
                try:
                    payload["system"] = mc.get_system_metrics()
                except Exception:
                    pass
            if scope in ("all", "performance"):
                try:
                    payload["performance"] = mc.get_performance_metrics()
                except Exception:
                    pass
            self.console.print_json(data=payload)
            return
        if args[0] == "export":
            fmt = args[1] if len(args) > 1 else "json"
            out = args[2] if len(args) > 2 else None
            mc = MetricsCollector()
            try:
                await mc._collect_system_metrics()  # type: ignore[attr-defined]
                await mc._collect_performance_metrics()  # type: ignore[attr-defined]
                await mc._collect_custom_metrics()  # type: ignore[attr-defined]
            except Exception:
                pass
            if fmt == "prometheus":
                content = mc._export_prometheus_format()  # type: ignore[attr-defined]
            else:
                content = json.dumps({"metrics": mc.get_all_metrics()}, indent=2)
            if out:
                from pathlib import Path
                Path(out).write_text(content, encoding="utf-8")
                self.console.print(f"[green]Wrote metrics to {out}[/green]")
            else:
                # Print raw for Prometheus, pretty JSON otherwise
                if fmt == "prometheus":
                    print(content)
                else:
                    self.console.print(content)
            return
        self.console.print("Usage: metrics show [system|performance|all] | metrics export [json|prometheus] [output]")

    async def cmd_alerts(self, args: List[str]) -> None:
        """Manage alerts interactively.

        Usage:
          alerts list
          alerts list-active
          alerts add <name> <metric> <condition> [severity]
          alerts remove <name>
          alerts clear
          alerts load <path>
          alerts save <path>
          alerts test <name> <value>
        """
        from ..monitoring import get_alert_manager
        am = get_alert_manager()
        if not args or args[0] == "list":
            rules = getattr(am, "alert_rules", {})
            if not rules:
                self.console.print("No alert rules")
                return
            table = Table(title="Alert Rules")
            table.add_column("Name", style="cyan")
            table.add_column("Metric")
            table.add_column("Condition")
            table.add_column("Severity")
            for rn, rule in rules.items():
                sev = getattr(rule.severity, "value", str(rule.severity))
                table.add_row(rn, rule.metric_name, rule.condition, sev)
            self.console.print(table)
            return
        cmd = args[0]
        if cmd == "list-active":
            act = getattr(am, "active_alerts", {})
            if not act:
                self.console.print("No active alerts")
                return
            table = Table(title="Active Alerts")
            table.add_column("ID", style="cyan")
            table.add_column("Rule")
            table.add_column("Severity")
            table.add_column("Value")
            for aid, alert in act.items():
                sev = getattr(alert.severity, "value", str(alert.severity))
                table.add_row(aid, alert.rule_name, sev, str(alert.value))
            self.console.print(table)
            return
        if cmd == "add" and len(args) >= 4:
            from ccbt.monitoring.alert_manager import AlertRule, AlertSeverity
            name, metric, condition = args[1], args[2], args[3]
            sev_str = args[4] if len(args) > 4 else "warning"
            try:
                sev = AlertSeverity(sev_str)
            except Exception:
                sev = AlertSeverity.WARNING
            am.add_alert_rule(AlertRule(name=name, metric_name=metric, condition=condition, severity=sev, description=f"Rule {name}"))
            self.console.print("[green]Rule added[/green]")
            return
        if cmd == "remove" and len(args) >= 2:
            am.remove_alert_rule(args[1])
            self.console.print("[green]Rule removed[/green]")
            return
        if cmd == "clear":
            import asyncio as _asyncio
            for aid in list(getattr(am, "active_alerts", {}).keys()):
                await am.resolve_alert(aid)
            self.console.print("[green]Cleared active alerts[/green]")
            return
        if cmd == "load" and len(args) >= 2:
            from pathlib import Path
            count = am.load_rules_from_file(Path(args[1]))  # type: ignore[attr-defined]
            self.console.print(f"[green]Loaded {count} rules[/green]")
            return
        if cmd == "save" and len(args) >= 2:
            from pathlib import Path
            am.save_rules_to_file(Path(args[1]))  # type: ignore[attr-defined]
            self.console.print("[green]Saved rules[/green]")
            return
        if cmd == "test" and len(args) >= 3:
            name, value = args[1], args[2]
            rule = getattr(am, "alert_rules", {}).get(name)
            if not rule:
                self.console.print(f"Rule not found: {name}")
                return
            try:
                v_any: Any = float(value) if value.replace('.', '', 1).isdigit() else value
            except Exception:
                v_any = value
            await am.process_alert(rule.metric_name, v_any)
            self.console.print("[green]Rule evaluated[/green]")
            return
        self.console.print("Usage: alerts list|list-active|add|remove|clear|load|save|test ...")

    async def cmd_export(self, args: List[str]) -> None:
        """Export session state to file.

        Usage:
          export <path>
        """
        if len(args) < 1:
            self.console.print("Usage: export <path>")
            return
        from pathlib import Path
        await self.session.export_session_state(Path(args[0]))
        self.console.print("OK")

    async def cmd_import(self, args: List[str]) -> None:
        """Import session state from file.

        Usage:
          import <path>
        """
        if len(args) < 1:
            self.console.print("Usage: import <path>")
            return
        from pathlib import Path
        data = await self.session.import_session_state(Path(args[0]))
        self.console.print({"loaded": True, "torrents": len(data.get("torrents", {}))})

    async def cmd_backup(self, args: List[str]) -> None:
        """Backup checkpoint.

        Usage:
          backup <info_hash> <dest>
        """
        if len(args) < 2:
            self.console.print("Usage: backup <info_hash> <dest>")
            return
        from ..checkpoint import CheckpointManager
        from ..config import get_config
        from pathlib import Path
        cm = CheckpointManager(get_config().disk)
        await cm.backup_checkpoint(bytes.fromhex(args[0]), Path(args[1]))
        self.console.print("OK")

    async def cmd_restore(self, args: List[str]) -> None:
        """Restore checkpoint.

        Usage:
          restore <backup_file>
        """
        if len(args) < 1:
            self.console.print("Usage: restore <backup_file>")
            return
        from ..checkpoint import CheckpointManager
        from ..config import get_config
        from pathlib import Path
        cm = CheckpointManager(get_config().disk)
        cp = await cm.restore_checkpoint(Path(args[0]))
        self.console.print({"restored": cp.torrent_name, "info_hash": cp.info_hash.hex()})

    async def cmd_config(self, args: List[str]) -> None:
        """Show or modify configuration at runtime.

        Usage:
          config show [section|key.path]
          config get <key.path>
          config set <key.path> <value>
          config reload
        """
        if not args:
            self.console.print("Usage: config [show|get|set|reload] ...")
            return
        sub = args[0]
        cm = ConfigManager(None)
        if sub == "show":
            target = args[1] if len(args) > 1 else None
            data = cm.config.model_dump(mode="json")
            if target:
                parts = target.split(".")
                ref = data
                try:
                    for p in parts:
                        ref = ref[p]
                    self.console.print(ref)
                except Exception:
                    self.console.print(f"[red]Key not found: {target}[/red]")
            else:
                from rich.pretty import Pretty
                self.console.print(Pretty(data))
        elif sub == "get":
            if len(args) < 2:
                self.console.print("Usage: config get <key.path>")
                return
            data = cm.config.model_dump(mode="json")
            ref = data
            try:
                for p in args[1].split("."):
                    ref = ref[p]
                self.console.print(ref)
            except Exception:
                self.console.print(f"[red]Key not found: {args[1]}[/red]")
        elif sub == "set":
            if len(args) < 3:
                self.console.print("Usage: config set <key.path> <value>")
                return
            key, raw = args[1], args[2]
            def parse_value(v: str):
                low = v.lower()
                if low in {"true","1","yes","on"}: return True
                if low in {"false","0","no","off"}: return False
                try:
                    if "." in v: return float(v)
                    return int(v)
                except ValueError:
                    return v
            val = parse_value(raw)
            # update current runtime config (in-memory only)
            cfg = cm.config.model_dump()
            ref = cfg
            parts = key.split(".")
            try:
                for p in parts[:-1]:
                    ref = ref.setdefault(p, {})
                ref[parts[-1]] = val
                # re-validate by constructing model
                from ..models import Config as ConfigModel
                new_cfg = ConfigModel(**cfg)
                cm.config = new_cfg
                # publish to global runtime
                from ..config import set_config
                set_config(new_cfg)
                self.console.print("[green]Updated runtime configuration[/green]")
            except Exception as e:
                self.console.print(f"[red]Failed to set config: {e}[/red]")
        elif sub == "reload":
            try:
                reload_config()
                self.console.print("[green]Configuration reloaded[/green]")
            except Exception as e:
                self.console.print(f"[red]Reload failed: {e}[/red]")
        else:
            self.console.print(f"Unknown subcommand: {sub}")
