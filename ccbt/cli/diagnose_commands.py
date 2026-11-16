"""Read-only `btbt diagnose` command: daemon-true peer/speed diagnostics."""

from __future__ import annotations

import asyncio
import json as _json

import click
from rich.console import Console
from rich.table import Table

from ccbt.daemon.diagnostics import collect_diagnostics, summarize_torrent
from ccbt.daemon.ipc_client import IPCClient


@click.command("diagnose")
@click.argument("info_hash", required=False, default=None)
@click.option(
    "-j", "--json", "as_json", is_flag=True, help="Emit machine-readable JSON"
)
@click.option(
    "-l",
    "--log-lines",
    type=int,
    default=20,
    show_default=True,
    help="Daemon log tail lines",
)
def diagnose(info_hash, as_json, log_lines):
    """Diagnose peer connectivity / download speed using daemon-true data.

    Read-only: queries the running daemon over IPC and prints torrent,
    peer, tracker, DHT, peer-quality, NAT and rate state, plus the
    daemon log tail. Unlike `btbt status`/`btbt metrics`, nothing here
    comes from a local session.
    """
    console = Console()

    async def _run():
        client = IPCClient()
        try:
            report = await collect_diagnostics(client, info_hash, log_lines=log_lines)
        finally:
            await client.close()
        return report

    try:
        report = asyncio.run(_run())
    except Exception as exc:
        msg = (
            f"Could not reach the daemon via IPC: {exc}. "
            "Is it running? Check with 'btbt daemon status'."
        )
        raise click.ClickException(msg) from exc

    if as_json:
        click.echo(_json.dumps(report, indent=2, default=str))
        return

    daemon = report.get("daemon") or {}
    if "error" in daemon:
        console.print(f"[red]Daemon status unavailable: {daemon['error']}[/red]")
    else:
        console.print(
            f"[bold]Daemon[/bold] status={daemon.get('status')} pid={daemon.get('pid')} "
            f"uptime={daemon.get('uptime')} torrents={daemon.get('num_torrents')} "
            f"ipc={daemon.get('ipc_url')}"
        )

    nat = report.get("nat") or {}
    if isinstance(nat, dict) and "error" not in nat:
        enabled = nat.get("enabled")
        method = nat.get("method") or nat.get("active_protocol")
        mapped = nat.get("mapped_port")
        mappings = nat.get("mappings") or []
        reachable = bool(mapped or mappings)
        console.print(
            "[bold]NAT[/bold] "
            f"enabled={enabled} method={method} external_ip={nat.get('external_ip')} "
            f"mapped_port={mapped} mappings={len(mappings)}"
        )
        console.print(
            "[bold]Inbound[/bold] "
            + (
                "reachable (port mapping active; trackers are told the mapped external port)"
                if reachable
                else "NOT reachable — outbound-only. If downloads are slow with few peers, "
                "forward UDP+TCP 64122 (peer listen) and UDP 64120 (DHT) on your router "
                "to this machine, or enable UPnP/NAT-PMP, then restart the daemon."
            )
        )
    else:
        console.print(f"[bold]NAT[/bold] {nat.get('error', nat)}")

    for entry in report.get("torrents", []):
        s = summarize_torrent(entry)
        table = Table(title=f"{s['name']} [{str(s['info_hash'])[:12]}...]")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        for key in (
            "status",
            "connected_peers",
            "active_peers",
            "productive_peers",
            "requestable_peers",
            "productive_peers_from_rows",
            "requestable_peers_from_rows",
            "seeds_connected",
            "peer_rows",
            "choked_peers",
            "download_rate",
            "upload_rate",
        ):
            table.add_row(key, str(s.get(key)))
        console.print(table)

        if s.get("peers_detail"):
            ptable = Table(title="Peers")
            for col in ("Peer", "Choked", "Down", "Up", "Client"):
                ptable.add_column(col)
            for p in s["peers_detail"]:
                ptable.add_row(
                    str(p.get("peer_key")),
                    str(p.get("choked")),
                    str(p.get("download_rate", "?")),
                    str(p.get("upload_rate", "?")),
                    str(p.get("client", "?")),
                )
            console.print(ptable)
        if s.get("dht_last_bootstrap_failure_reason") or s.get(
            "dht_bootstrap_zero_nodes_last_reason"
        ):
            console.print(
                "[bold]DHT bootstrap[/bold] "
                f"routing={s.get('dht_routing_table_size')} "
                f"bound_port={s.get('dht_bound_port')} "
                f"last_failure={s.get('dht_last_bootstrap_failure_reason') or s.get('dht_bootstrap_zero_nodes_last_reason')}"
            )

        trackers = entry.get("trackers") or {}
        trows = (
            trackers.get("trackers", trackers)
            if isinstance(trackers, dict)
            else trackers
        )
        if isinstance(trows, list) and trows:
            ttable = Table(title="Trackers")
            for col in ("URL", "Status", "Seeds", "Peers", "Last error"):
                ttable.add_column(col)
            for t in trows:
                if not isinstance(t, dict):
                    continue
                ttable.add_row(
                    str(t.get("url", "?"))[:48],
                    str(t.get("status", "?")),
                    str(t.get("seeders", t.get("seeds", "?"))),
                    str(t.get("leechers", t.get("peers", "?"))),
                    str(t.get("last_error", t.get("error", "")) or ""),
                )
            console.print(ttable)

        for section in ("dht", "peer_quality", "aggressive_discovery"):
            data = entry.get(section)
            if data:
                console.print(f"[bold]{section}[/bold] {data}")

    tail = report.get("daemon_log_tail") or []
    if tail:
        console.print("[bold]Daemon log (tail)[/bold]")
        for line in tail:
            console.print(line, markup=False)
