"""Performance analysis monitoring screen."""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, Footer, Header, Static
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import (
            Horizontal,
            Vertical,
        )
        from textual.widgets import (
            Button,
            Footer,
            Header,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Horizontal = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Button = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.config.config import get_config
from ccbt.interface.commands.executor import CommandExecutor
from ccbt.interface.screens.base import MonitoringScreen


class PerformanceAnalysisScreen(MonitoringScreen):  # type: ignore[misc]
    """Screen to display performance analysis from CLI command."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #system_info {
        height: 1fr;
        min-height: 8;
    }
    #config_analysis {
        height: 1fr;
        min-height: 8;
    }
    #optimizations {
        height: 1fr;
        min-height: 8;
    }
    #actions {
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the performance analysis screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="system_info")
            yield Static(id="config_analysis")
            yield Static(id="optimizations")
            with Horizontal(id="actions"):
                yield Button("Refresh", id="refresh", variant="primary")
                yield Button("Run Benchmark", id="benchmark", variant="default")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and initialize command executor."""
        # Initialize command executor
        if not hasattr(self, "_command_executor") or self._command_executor is None:
            self._command_executor = CommandExecutor(self.session)
        await self._refresh_data()

    async def _refresh_data(self) -> None:  # pragma: no cover
        """Refresh performance analysis display."""
        try:
            content = self.query_one("#content", Static)
            system_info = self.query_one("#system_info", Static)
            config_analysis = self.query_one("#config_analysis", Static)
            optimizations = self.query_one("#optimizations", Static)

            # Get system information directly
            sys_table = Table(
                title="System Information", expand=True, show_header=False, box=None
            )
            sys_table.add_column("Item", style="cyan", ratio=1)
            sys_table.add_column("Value", style="green", ratio=2)

            sys_table.add_row("Python", sys.version.split()[0])
            sys_table.add_row("Platform", platform.platform())
            sys_table.add_row("CPU Count", str(os.cpu_count() or 1))
            sys_table.add_row("Architecture", platform.machine())

            system_info.update(Panel(sys_table))

            # Get configuration analysis
            cfg = get_config()
            config_table = Table(
                title="Configuration Analysis", expand=True, show_header=False, box=None
            )
            config_table.add_column("Setting", style="cyan", ratio=2)
            config_table.add_column("Value", style="green", ratio=2)
            config_table.add_column("Status", style="yellow", ratio=1)

            # Disk configuration
            disk_workers = cfg.disk.disk_workers
            cpu_count = os.cpu_count() or 1
            disk_workers_status = (
                "[green]Optimal[/green]"
                if disk_workers >= 2
                else "[yellow]Low[/yellow]"
            )
            config_table.add_row("Disk Workers", str(disk_workers), disk_workers_status)

            write_buffer = cfg.disk.write_buffer_kib
            write_buffer_status = (
                "[green]Good[/green]"
                if write_buffer >= 256
                else "[yellow]Small[/yellow]"
            )
            config_table.add_row(
                "Write Buffer (KiB)", str(write_buffer), write_buffer_status
            )

            write_batch = cfg.disk.write_batch_kib
            write_batch_status = (
                "[green]Good[/green]"
                if write_batch >= 1024
                else "[yellow]Small[/yellow]"
            )
            config_table.add_row(
                "Write Batch (KiB)", str(write_batch), write_batch_status
            )

            use_mmap = cfg.disk.use_mmap
            mmap_status = (
                "[green]Enabled[/green]" if use_mmap else "[dim]Disabled[/dim]"
            )
            config_table.add_row("Use MMAP", str(use_mmap), mmap_status)

            direct_io = cfg.disk.direct_io
            direct_io_status = (
                "[green]Enabled[/green]" if direct_io else "[dim]Disabled[/dim]"
            )
            config_table.add_row("Direct I/O", str(direct_io), direct_io_status)

            io_uring = cfg.disk.enable_io_uring
            io_uring_status = (
                "[green]Enabled[/green]" if io_uring else "[dim]Disabled[/dim]"
            )
            config_table.add_row("io_uring", str(io_uring), io_uring_status)

            config_analysis.update(Panel(config_table))

            # Get optimization suggestions
            suggestions = []

            if disk_workers < 2:
                suggestions.append(
                    "Increase disk workers to at least 2 for better I/O performance"
                )

            if write_buffer < 256:
                suggestions.append(
                    "Increase write buffer to 256 KiB or more for better sequential write performance"
                )

            if write_batch < 1024:
                suggestions.append(
                    "Increase write batch size to 1024 KiB or more for better batching efficiency"
                )

            if not use_mmap:
                suggestions.append(
                    "Enable mmap for large sequential reads (reduces memory copies)"
                )

            if cpu_count >= 4 and disk_workers < cpu_count // 2:
                suggestions.append(
                    f"Consider increasing disk workers to {cpu_count // 2} for {cpu_count}-core system"
                )

            if not direct_io and platform.system() == "Linux":
                suggestions.append(
                    "Consider enabling direct I/O on Linux/NVMe for large sequential writes"
                )

            if not io_uring and platform.system() == "Linux":
                suggestions.append(
                    "Consider enabling io_uring on Linux for modern async I/O (requires kernel 5.1+)"
                )

            if suggestions:
                opt_table = Table(
                    title="Optimization Suggestions",
                    expand=True,
                    show_header=False,
                    box=None,
                )
                opt_table.add_column("Suggestion", style="cyan", ratio=1)

                for suggestion in suggestions:
                    opt_table.add_row(f"• {suggestion}")

                optimizations.update(Panel(opt_table))
            else:
                optimizations.update(
                    Panel(
                        "No optimization suggestions. Your configuration looks good!",
                        title="Optimization Suggestions",
                        border_style="green",
                    )
                )

            content.update(
                Panel(
                    "Performance analysis complete. Review system info, configuration, and optimization suggestions below.",
                    title="Performance Analysis",
                    border_style="green",
                )
            )

        except Exception as e:
            content = self.query_one("#content", Static)
            content.update(
                Panel(
                    f"Error loading performance analysis: {e}",
                    title="Error",
                    border_style="red",
                )
            )

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "refresh":
            await self._refresh_data()
        elif event.button.id == "benchmark":
            await self._run_benchmark()

    async def _run_benchmark(self) -> None:  # pragma: no cover
        """Run performance benchmark."""
        content = self.query_one("#content", Static)
        content.update(
            Panel(
                "Running benchmark... This may take a moment.",
                title="Benchmark",
                border_style="yellow",
            )
        )

        try:
            if not hasattr(self, "_command_executor") or self._command_executor is None:
                self._command_executor = CommandExecutor(self.session)

            # Execute benchmark command
            success, output, _ = await self._command_executor.execute_click_command(
                "performance", ["--benchmark"]
            )

            if success:
                # Parse benchmark results from output
                # Try to extract JSON from output
                json_match = re.search(r"\{[^}]+\}", output)
                if json_match:
                    try:
                        results = json.loads(json_match.group())
                        benchmark_table = Table(title="Benchmark Results", expand=True)
                        benchmark_table.add_column("Metric", style="cyan", ratio=1)
                        benchmark_table.add_column("Value", style="green", ratio=2)

                        size_mb = results.get("size_mb", 0)
                        write_mb_s = results.get("write_mb_s", 0)
                        read_mb_s = results.get("read_mb_s", 0)
                        write_time = results.get("write_time_s", 0)
                        read_time = results.get("read_time_s", 0)

                        benchmark_table.add_row("Test Size", f"{size_mb} MB")
                        benchmark_table.add_row("Write Speed", f"{write_mb_s:.2f} MB/s")
                        benchmark_table.add_row("Read Speed", f"{read_mb_s:.2f} MB/s")
                        benchmark_table.add_row("Write Time", f"{write_time:.3f} s")
                        benchmark_table.add_row("Read Time", f"{read_time:.3f} s")

                        content.update(Panel(benchmark_table))
                    except Exception:
                        content.update(
                            Panel(
                                f"Benchmark completed:\n\n{output}",
                                title="Benchmark Results",
                                border_style="green",
                            )
                        )
                else:
                    content.update(
                        Panel(
                            f"Benchmark completed:\n\n{output}",
                            title="Benchmark Results",
                            border_style="green",
                        )
                    )
            else:
                content.update(
                    Panel(
                        f"Benchmark failed: {output}",
                        title="Error",
                        border_style="red",
                    )
                )
        except Exception as e:
            content.update(
                Panel(
                    f"Error running benchmark: {e}",
                    title="Error",
                    border_style="red",
                )
            )

