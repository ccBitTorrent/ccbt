"""Integration tests for XET folder synchronization workflow.

Tests full sync workflow including folder creation, peer discovery, updates, and consensus.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccbt.config.config import get_config
from ccbt.discovery.xet_cas import P2PCASClient

pytestmark = [pytest.mark.integration, pytest.mark.extensions]


def _build_session_manager_stub(use_real_cas: bool = False) -> SimpleNamespace:
    """Build session manager stub. use_real_cas=True uses real P2PCASClient (slower in CI)."""
    if use_real_cas:
        cas = P2PCASClient()
    else:
        cas = MagicMock()
        cas.announce_chunk = AsyncMock(return_value=None)
        cas.find_chunks_peers_batch = AsyncMock(return_value={})
        cas.find_chunk_peers = AsyncMock(return_value=[])
    return SimpleNamespace(
        config=get_config(),
        xet_cas_client=cas,
        dht_client=None,
        udp_tracker_client=None,
        get_xet_discovery_status=dict,
    )


class TestXetSyncWorkflow:
    """Test full XET sync workflow."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def folder_path(self, temp_dir):
        """Create test folder."""
        folder = temp_dir / "test_folder"
        folder.mkdir()
        (folder / "test.txt").write_text("initial content")
        return folder

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_folder_sync_lifecycle(self, folder_path):
        """Test complete folder sync lifecycle."""
        from ccbt.storage.xet_folder_manager import XetFolder

        folder = XetFolder(
            folder_path=folder_path,
            sync_mode="best_effort",
            check_interval=1.0,
            enable_git=False,
            session_manager=_build_session_manager_stub(),
        )

        # Start sync
        await folder.start()

        # Get status
        status = folder.get_status()
        assert status.sync_mode == "best_effort"
        assert status.is_syncing is False

        # Stop sync
        await folder.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sync_mode_changes(self, folder_path):
        """Test changing sync mode."""
        from ccbt.storage.xet_folder_manager import XetFolder

        folder = XetFolder(
            folder_path=folder_path,
            sync_mode="best_effort",
            session_manager=_build_session_manager_stub(),
        )

        # Change sync mode
        folder.set_sync_mode("consensus", source_peers=["peer1"])

        status = folder.get_status()
        assert status.sync_mode == "consensus"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_folder_change_detection(self, folder_path):
        """Test folder change detection and queuing."""
        from ccbt.storage.xet_folder_manager import XetFolder
        from ccbt.utils.events import get_event_bus

        # Use mock CAS so CI does not run real discovery (timeouts on no network).
        session_manager = _build_session_manager_stub(use_real_cas=False)

        # Start event bus so FOLDER_CHANGED events are consumed; otherwise the queue
        # fills (watchdog can emit many events on Windows), emit blocks time out
        # repeatedly, and the test can hit the global timeout.
        event_bus = get_event_bus()
        bus_was_running = event_bus.running
        if not bus_was_running:
            await event_bus.start()
        try:
            folder = XetFolder(
                folder_path=folder_path,
                sync_mode="best_effort",
                check_interval=0.5,
                session_manager=session_manager,
            )

            await folder.start()

            # Create new file
            new_file = folder_path / "new_file.txt"
            new_file.write_text("new content")

            # Wait for change detection (realtime sync runs every check_interval=0.5s).
            await asyncio.sleep(1.5)

            # Trigger sync; retry if realtime sync has already started one.
            # More retries and longer sleep so we reliably get a successful sync on CI
            # (realtime loop can hold sync() for up to ~60s).
            success = False
            for _ in range(24):
                ok, _ = await folder.sync()
                if ok:
                    success = True
                    break
                await asyncio.sleep(1.0)
            assert success, "folder.sync() did not succeed within retries"

            await folder.stop()
            # Give Windows time to release db file handle before temp_dir teardown.
            await asyncio.sleep(0.25)
        finally:
            if not bus_was_running and event_bus.running:
                await event_bus.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_consensus_mode_workflow(self, folder_path):
        """Test consensus mode workflow."""
        from ccbt.storage.xet_folder_manager import XetFolder

        folder = XetFolder(
            folder_path=folder_path,
            sync_mode="consensus",
            check_interval=1.0,
            session_manager=_build_session_manager_stub(),
        )

        try:
            await folder.start()

            # Current runtime downgrades consensus when transport-backed consensus
            # is unavailable.
            status = folder.get_status()
            assert status.sync_mode == "best_effort"
        finally:
            await folder.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_tonic_create_and_sync(self, folder_path, temp_dir):
        """Test creating tonic file and syncing from it."""
        from ccbt.cli.tonic_generator import generate_tonic_from_folder
        from ccbt.core.tonic import TonicFile
        from ccbt.storage.xet_folder_manager import XetFolder

        # Generate tonic file
        tonic_data, _ = await generate_tonic_from_folder(
            folder_path=folder_path,
            sync_mode="best_effort",
            generate_link=False,
        )

        # Save tonic file
        tonic_path = temp_dir / "test.tonic"
        tonic_path.write_bytes(tonic_data)

        # Parse and verify
        tonic_file = TonicFile()
        parsed = tonic_file.parse(tonic_path)
        assert parsed["info"]["name"] == folder_path.name

        # Create folder from tonic
        output_dir = temp_dir / "synced_folder"
        synced_folder = XetFolder(
            folder_path=output_dir,
            sync_mode=parsed.get("sync_mode", "best_effort"),
            session_manager=_build_session_manager_stub(),
        )

        await synced_folder.start()
        await synced_folder.stop()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_allowlist_integration(self, folder_path, temp_dir):
        """Test allowlist integration in sync workflow."""
        from ccbt.security.xet_allowlist import XetAllowlist
        from ccbt.storage.xet_folder_manager import XetFolder

        # Create allowlist
        allowlist_path = temp_dir / "test.allowlist"
        allowlist = XetAllowlist(allowlist_path=allowlist_path)
        await allowlist.load()

        allowlist.add_peer(peer_id="peer_1", public_key=b"1" * 32, alias="Alice")
        await allowlist.save()

        # Get allowlist hash
        allowlist_hash = allowlist.get_allowlist_hash()

        # Create folder with allowlist
        folder = XetFolder(
            folder_path=folder_path,
            sync_mode="best_effort",
            session_manager=_build_session_manager_stub(),
        )

        # Set allowlist hash in sync manager
        folder.sync_manager.set_allowlist_hash(allowlist_hash)

        assert folder.sync_manager.get_allowlist_hash() == allowlist_hash

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_git_versioning_integration(self, folder_path):
        """Test git versioning integration."""
        import subprocess

        # Initialize git repo
        try:
            subprocess.run(
                ["git", "init"],
                cwd=folder_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=folder_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=folder_path,
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("Git not available")

        from ccbt.storage.xet_folder_manager import XetFolder

        folder = XetFolder(
            folder_path=folder_path,
            sync_mode="best_effort",
            enable_git=True,
            session_manager=_build_session_manager_stub(),
        )

        await folder.start()

        # Get git versions
        versions = await folder.get_versions(max_refs=10)
        # May be empty if no commits yet
        assert isinstance(versions, list)

        await folder.stop()









