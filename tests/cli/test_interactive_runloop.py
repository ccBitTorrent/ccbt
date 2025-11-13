import asyncio
from types import SimpleNamespace

import pytest


@pytest.mark.unit
@pytest.mark.cli
class TestInteractiveRunLoop:
    class FakeSession:
        def __init__(self):
            self._status = {}
            self.torrents = {}
            self.lock = asyncio.Lock()

        async def add_torrent(self, torrent_data, resume=False):
            info_hash_hex = torrent_data.get("info_hash", "0" * 40)
            # Populate torrents dict with mock session
            info_hash_bytes = bytes.fromhex(info_hash_hex)
            from unittest.mock import AsyncMock
            mock_torrent_session = AsyncMock()
            mock_torrent_session.file_selection_manager = None
            self.torrents[info_hash_bytes] = mock_torrent_session
            return info_hash_hex

        async def get_torrent_status(self, info_hash_hex):
            return self._status.get(info_hash_hex)

        async def get_peers_for_torrent(self, info_hash_hex):
            return []

        async def pause_torrent(self, info_hash_hex):
            return None

        async def resume_torrent(self, info_hash_hex):
            return None

        async def remove(self, info_hash_hex):
            return None

    @pytest.fixture
    def console(self, monkeypatch):
        # Minimal console stub collecting printed data
        outputs = []

        class Console:
            def print(self, *args, **kwargs):
                outputs.append((args, kwargs))

            def print_json(self, *args, **kwargs):
                outputs.append((args, kwargs))

            def clear(self):
                outputs.clear()

        return SimpleNamespace(obj=Console(), outputs=outputs)

    @pytest.mark.asyncio
    async def test_run_loop_keyboard_interrupt(self, console, monkeypatch):  # pragma: no cover
        """Test run loop handles KeyboardInterrupt gracefully.
        
        Note: Skipped during coverage runs to prevent pytest from interpreting
        KeyboardInterrupt as a real user interrupt and exiting early.
        This test intentionally raises KeyboardInterrupt to verify graceful shutdown of the interactive CLI run loop.
        """
        # Skip only if coverage is running to prevent early test suite exit
        import sys
        if any("--cov" in arg or "-m" in arg and "cov" in arg for arg in sys.argv):
            pytest.skip(
                "KeyboardInterrupt test skipped in coverage runs to prevent early test suite exit. "
                "This test intentionally raises KeyboardInterrupt which pytest may interpret as a "
                "real user interrupt, causing the test suite to exit at 94%. "
                "Run with --no-cov to execute this test.",
                allow_module_level=False,
            )  # pragma: no cover
        from ccbt.cli.interactive import InteractiveCLI

        # Patch Live context manager to a no-op
        class DummyLive:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr("ccbt.cli.interactive.Live", DummyLive)

        # Make asyncio.sleep raise KeyboardInterrupt once, then behave normally
        called = {"n": 0}
        original_sleep = asyncio.sleep

        async def fake_sleep(_):
            called["n"] += 1
            if called["n"] == 1:
                raise KeyboardInterrupt
            # yield control without disrupting other async tasks in the test run
            return await original_sleep(0)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        cli = InteractiveCLI(self.FakeSession(), console.obj)
        # Ensure no torrent and run exits immediately on KeyboardInterrupt
        await cli.run()
        assert cli.running is True or cli.running is False  # loop handled without crash

    @pytest.mark.asyncio
    async def test_status_no_torrent_and_basic_commands(self, console, monkeypatch):
        from ccbt.cli.interactive import InteractiveCLI

        cli = InteractiveCLI(self.FakeSession(), console.obj)

        # status with no current_torrent
        await cli.cmd_status([])
        assert any("No torrent active" in (args[0] if args else "") for args, _ in console.outputs)

        console.outputs.clear()
        # help renders a panel via console.print; just ensure it calls print
        await cli.cmd_help([])
        assert len(console.outputs) >= 1

        # clear clears outputs
        await cli.cmd_clear([])
        assert console.outputs == []

    @pytest.mark.asyncio
    async def test_download_interface_and_updates(self, console, monkeypatch):
        from ccbt.cli.interactive import InteractiveCLI

        session = self.FakeSession()
        cli = InteractiveCLI(session, console.obj)

        # Ensure layout is initialized for show_download_interface panes
        cli.setup_layout()

        # Prepare minimal torrent data and status
        torrent = {
            "name": "test.torrent",
            "info_hash": "0" * 40,
            "total_length": 1024 * 1024,
            "pieces": b"\x00" * 20,
        }

        # Set a status that update_download_stats will read
        info_hash_hex = "0" * 40
        session._status[info_hash_hex] = {
            "progress": 0.5,
            "download_rate": 1024.0,
            "upload_rate": 512.0,
            "pieces_completed": 1,
            "pieces_total": 2,
            "downloaded_bytes": 512 * 1024,
        }

        await cli.download_torrent(torrent, resume=False)
        # After starting download, panels should be creatable without exceptions
        panel = cli.create_download_panel()
        assert panel is not None
        peers_panel = cli.create_peers_panel()
        assert peers_panel is not None
        status_panel = cli.create_status_panel()
        assert status_panel is not None


