from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ccbt.executor.session_adapter import LocalSessionAdapter
from ccbt.i18n import _


async def show_status(adapter: LocalSessionAdapter, console: Console) -> None:
    """Show client status."""
    # Get session from adapter (for local sessions)
    session = adapter.session_manager

    table = Table(title=_("ccBitTorrent Status"))  # pragma: no cover - UI setup
    table.add_column(_("Component"), style="cyan")  # pragma: no cover
    table.add_column(_("Status"), style="green")  # pragma: no cover
    table.add_column(_("Details"))  # pragma: no cover

    table.add_row(
        _("Session"),
        _("Running"),
        _("Port: {port}").format(port=session.config.network.listen_port),
    )  # pragma: no cover
    table.add_row(
        _("Peers"),
        _("Connected"),
        _("Active: {count}").format(count=len(session.peers)),
    )  # pragma: no cover

    # Get IP filter stats via executor (if available)
    try:
        from ccbt.executor.executor import UnifiedCommandExecutor

        executor = UnifiedCommandExecutor(adapter)
        result = await executor.execute("security.get_ip_filter_stats")

        if result.success and result.data.get("enabled"):
            stats = result.data.get("stats", {})
            filter_status = _("Enabled")
            filter_details = _(
                "Rules: {rules}, IPv4: {ipv4}, IPv6: {ipv6}, Blocks: {blocks}"
            ).format(
                rules=stats.get("total_rules", 0),
                ipv4=stats.get("ipv4_ranges", 0),
                ipv6=stats.get("ipv6_ranges", 0),
                blocks=stats.get("blocks", 0),
            )
            table.add_row(
                _("IP Filter"), filter_status, filter_details
            )  # pragma: no cover
        else:
            table.add_row(
                _("IP Filter"), _("Disabled"), _("Not configured")
            )  # pragma: no cover
    except Exception:
        table.add_row(
            _("IP Filter"), _("Disabled"), _("Not available")
        )  # pragma: no cover

    try:
        scrape_cache_size = len(session.scrape_cache)
        if scrape_cache_size > 0:
            async with session.scrape_cache_lock:
                total_seeders = sum(r.seeders for r in session.scrape_cache.values())
                total_leechers = sum(r.leechers for r in session.scrape_cache.values())
            scrape_details = f"Cached: {scrape_cache_size}, Total Seeders: {total_seeders}, Total Leechers: {total_leechers}"
        else:
            scrape_details = _("No cached results")

        auto_scrape_status = (
            _("Enabled")
            if session.config.discovery.tracker_auto_scrape
            else _("Disabled")
        )
        table.add_row(
            _("Tracker Scrape"), auto_scrape_status, scrape_details
        )  # pragma: no cover
    except Exception:
        table.add_row(
            _("Tracker Scrape"), _("Unknown"), _("Error reading scrape cache")
        )  # pragma: no cover

    total_torrents = len(session.torrents)
    torrents_with_files = 0
    total_selected_files = 0
    total_files = 0
    private_torrents_count = 0

    async with session.lock:
        for torrent_session in session.torrents.values():
            if torrent_session.file_selection_manager:
                torrents_with_files += 1
                all_states = (
                    torrent_session.file_selection_manager.get_all_file_states()
                )
                total_files += len(all_states)
                total_selected_files += sum(
                    1 for state in all_states.values() if state.selected
                )
            if getattr(torrent_session, "is_private", False):
                private_torrents_count += 1

    file_info = (
        _(" | Files: {selected}/{total} selected").format(
            selected=total_selected_files, total=total_files
        )
        if torrents_with_files > 0
        else ""
    )
    private_info = (
        _(" | Private: {count}").format(count=private_torrents_count)
        if private_torrents_count > 0
        else ""
    )
    table.add_row(
        _("Torrents"),
        _("Active"),
        _("Count: {count}{file_info}{private_info}").format(
            count=total_torrents, file_info=file_info, private_info=private_info
        ),
    )  # pragma: no cover

    if hasattr(session, "scrape_cache"):
        try:
            async with session.scrape_cache_lock:
                scrape_results = list(session.scrape_cache.values())
            if scrape_results:
                console.print(_("\n[yellow]Tracker Scrape Statistics:[/yellow]"))
                scrape_table = Table()
                scrape_table.add_column(_("Info Hash"), style="cyan")
                scrape_table.add_column(_("Seeders"), style="green")
                scrape_table.add_column(_("Leechers"), style="yellow")
                scrape_table.add_column(_("Completed"), style="blue")

                for result in scrape_results[:10]:
                    scrape_table.add_row(
                        result.info_hash.hex()[:16] + "...",
                        str(result.seeders),
                        str(result.leechers),
                        str(result.completed),
                    )
                console.print(scrape_table)
        except Exception:
            pass

    dht_node_count = 0
    if session.dht:
        dht_stats = session.dht.get_stats()
        routing_table_stats = dht_stats.get("routing_table", {})
        dht_node_count = routing_table_stats.get("total_nodes", 0)
    table.add_row(
        _("DHT"), _("Enabled"), _("Nodes: {count}").format(count=dht_node_count)
    )  # pragma: no cover

    if session.config.network.enable_utp:
        try:
            from ccbt.transport.utp_socket import UTPSocketManager

            socket_manager = await UTPSocketManager.get_instance()
            stats = socket_manager.get_statistics()
            utp_status = "Enabled"
            utp_details = (
                f"Connections: {stats['active_connections']} | "
                f"Packets: {stats['total_packets_sent']}/{stats['total_packets_received']} | "
                f"Bytes: {stats['total_bytes_sent']}/{stats['total_bytes_received']}"
            )
        except Exception:
            utp_status = "Enabled"
            utp_details = "Socket manager not initialized"
    else:
        utp_status = "Disabled"
        utp_details = "Not configured"
    table.add_row("uTP", utp_status, utp_details)  # pragma: no cover

    protocol_v2_config = session.config.network.protocol_v2
    if protocol_v2_config.enable_protocol_v2:
        v2_status = "Enabled"
        v2_details = f"Prefer v2: {protocol_v2_config.prefer_protocol_v2} | Hybrid: {protocol_v2_config.support_hybrid} | Timeout: {protocol_v2_config.v2_handshake_timeout}s"
    else:
        v2_status = "Disabled"
        v2_details = "Not enabled"
    table.add_row("Protocol v2 (BEP 52)", v2_status, v2_details)  # pragma: no cover

    webtorrent_config = session.config.network.webtorrent
    if webtorrent_config.enable_webtorrent:
        webtorrent_status = "Disabled"
        webtorrent_details = "Not initialized"
        try:
            from ccbt.protocols.webtorrent import (
                WebTorrentProtocol,  # type: ignore[attr-defined]
            )

            webrtc_connections = 0
            signaling_status = "Stopped"
            if hasattr(session, "protocols"):
                for protocol in (
                    session.protocols.values()
                    if isinstance(session.protocols, dict)
                    else []
                ):
                    if (
                        isinstance(protocol, WebTorrentProtocol)
                        and WebTorrentProtocol is not None
                    ):
                        webtorrent_protocol = protocol  # type: ignore[assignment]
                        webrtc_connections = len(webtorrent_protocol.webrtc_connections)  # type: ignore[attr-defined]
                        signaling_status = (
                            "Running"
                            if webtorrent_protocol.websocket_server is not None  # type: ignore[attr-defined]
                            else "Stopped"
                        )
                        webtorrent_status = "Enabled"
                        webtorrent_details = (
                            f"Connections: {webrtc_connections}, "
                            f"Signaling: {signaling_status} "
                            f"({webtorrent_config.webtorrent_host}:{webtorrent_config.webtorrent_port})"
                        )
                        break

            if webtorrent_status == "Enabled":
                table.add_row(
                    "WebTorrent", webtorrent_status, webtorrent_details
                )  # pragma: no cover
            else:
                table.add_row(
                    "WebTorrent",
                    "Enabled (Not Started)",
                    f"Port: {webtorrent_config.webtorrent_port}, STUN: {len(webtorrent_config.webtorrent_stun_servers)} server(s)",
                )  # pragma: no cover
        except (ImportError, AttributeError):
            table.add_row(
                "WebTorrent", "Enabled (Dependency Missing)", "aiortc not installed"
            )  # pragma: no cover
    else:
        table.add_row(
            "WebTorrent", "Disabled", "Not enabled in configuration"
        )  # pragma: no cover

    console.print(table)  # pragma: no cover
