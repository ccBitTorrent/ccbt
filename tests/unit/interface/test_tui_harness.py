"""WS0-WS2 harness: fakes, format, read models, bindings registry, textual guard."""
import pytest
from ccbt.interface.bindings import BINDING_SPECS, action_names, footer_bindings
from ccbt.interface.format import fmt_bytes, fmt_eta, fmt_progress_bar, fmt_rate, fmt_ratio, fmt_status
from ccbt.interface.read_models import TorrentRow
from ccbt.interface.textual_guard import ensure_textual_version, textual_version
from tests.unit.interface.fakes import FakeExecutor, error_provider, many_torrents_provider, one_torrent_provider, torrent_payload, HASH_A, HASH_B

def test_format_shared():
    assert fmt_bytes(2048) == "2.00 KB"
    assert fmt_rate(2048) == "2.0 KB/s"
    assert fmt_eta(0) == "∞"
    assert fmt_ratio(100, 50) == "0.50"
    assert "42.0%" in fmt_progress_bar(0.42)
    assert "downloading" in fmt_status("downloading")

def test_torrent_row_seeds_peers_split():
    row = TorrentRow.from_dict(torrent_payload())
    assert row.peers_connected == 12
    assert row.seeds_connected == 3
    assert row.eta_seconds > 0
    assert row.ratio == pytest.approx(0.2)

def test_fake_provider_scenarios():
    import asyncio
    async def _run():
        assert len(await one_torrent_provider().list_torrents()) == 1
        assert len(await many_torrents_provider().list_torrents()) == 100
        with pytest.raises(RuntimeError):
            await error_provider().list_torrents()
    asyncio.run(_run())

def test_fake_executor_records_xet_share_flow():
    import asyncio
    async def _run():
        ex = FakeExecutor()
        for cmd in ["xet.create_tonic", "xet.share_folder", "xet.generate_link", "xet.sync"]:
            r = await ex.execute_command(cmd, folder_path="/data")
            assert r.success
        assert [c for c, _ in ex.calls] == ["xet.create_tonic", "xet.share_folder", "xet.generate_link", "xet.sync"]
    asyncio.run(_run())

def test_bindings_registry_actions_exist():
    from ccbt.interface.terminal_dashboard import TerminalDashboard
    missing = [a for a in action_names() if not hasattr(TerminalDashboard, f"action_{a}")]
    assert missing == [], f"bindings without actions: {missing}"
    assert footer_bindings()[0][1] == "pause_torrent"

def test_dashboard_pause_uses_unified_selection():
    import inspect
    from ccbt.interface.terminal_dashboard import TerminalDashboard
    src = inspect.getsource(TerminalDashboard.action_pause_torrent)
    assert "_get_selected_info_hash" in src
    assert "self.torrents.get_selected" not in src

def test_textual_guard_reports_version():
    v = textual_version()
    assert isinstance(v, tuple) and v
    # Installed env may be <8; guard must raise then (documented) not silently pass
    if v < (8, 0, 0):
        with pytest.raises(RuntimeError):
            ensure_textual_version()

def test_two_torrent_fixture_disjoint():
    from tests.unit.interface.fakes import two_torrent_provider
    import asyncio
    async def _run():
        p = two_torrent_provider()
        a = await p.get_torrent_files(HASH_A); b = await p.get_torrent_files(HASH_B)
        assert a[0]["path"] != b[0]["path"]
    asyncio.run(_run())
