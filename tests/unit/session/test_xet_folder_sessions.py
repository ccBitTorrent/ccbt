"""Unit tests for XET folder session registration and metadata resolution."""

from __future__ import annotations

import asyncio

import pytest

from ccbt.core.tonic import TonicFile
from ccbt.core.tonic_link import generate_tonic_link
from ccbt.discovery.xet_cas import P2PCASClient
from ccbt.models import XetTorrentMetadata
from ccbt.session.session import AsyncSessionManager
from ccbt.session.xet_metadata_resolver import XetMetadataResolver

pytestmark = [pytest.mark.unit, pytest.mark.session, pytest.mark.asyncio]


def _build_minimal_tonic_bytes(folder_name: str) -> tuple[bytes, bytes]:
    tonic_file = TonicFile()
    tonic_bytes = tonic_file.create(
        folder_name=folder_name,
        xet_metadata=XetTorrentMetadata(),
        sync_mode="best_effort",
    )
    parsed = tonic_file.parse_bytes(tonic_bytes)
    return tonic_bytes, tonic_file.get_info_hash(parsed)


def _build_session_manager(tmp_path) -> AsyncSessionManager:
    manager = AsyncSessionManager(output_dir=str(tmp_path))
    manager.xet_cas_client = P2PCASClient()
    return manager


async def test_session_manager_adds_xet_folder_from_tonic(tmp_path) -> None:
    """Session manager should create a live XET folder runtime from a tonic file."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tonic_bytes, _ = _build_minimal_tonic_bytes("workspace")
    tonic_path = tmp_path / "workspace.tonic"
    tonic_path.write_bytes(tonic_bytes)

    manager = _build_session_manager(tmp_path)
    folder_key = await manager.add_xet_folder(
        folder_path=str(workspace),
        tonic_file=str(tonic_path),
        check_interval=0.05,
    )

    folders = await manager.list_xet_folders()
    assert len(folders) == 1
    assert folders[0]["folder_key"] == folder_key
    assert folders[0]["folder_path"] == str(workspace.resolve())
    assert await manager.get_registered_xet_metadata(folders[0]["workspace_id"]) is not None
    assert await manager.get_xet_folder(folder_key) is not None

    assert await manager.remove_xet_folder(folder_key) is True


async def test_resolver_uses_registered_metadata_for_tonic_link(tmp_path) -> None:
    """Resolver should satisfy tonic links from the session metadata registry."""
    tonic_bytes, info_hash = _build_minimal_tonic_bytes("linked-workspace")
    manager = _build_session_manager(tmp_path)
    await manager.register_xet_metadata(info_hash.hex(), tonic_bytes)

    link = generate_tonic_link(
        info_hash=info_hash,
        display_name="linked-workspace",
        sync_mode="best_effort",
    )
    resolved = await XetMetadataResolver().resolve(link, session_manager=manager)

    assert resolved.workspace_id == info_hash
    assert resolved.metadata_bytes == tonic_bytes
    assert resolved.parsed_metadata["info"]["name"] == "linked-workspace"


async def test_resolver_raises_runtime_error_for_missing_tonic_link_metadata(
    tmp_path,
) -> None:
    """Resolver must raise RuntimeError (not FileNotFoundError) when tonic link has no metadata."""
    _, info_hash = _build_minimal_tonic_bytes("orphan")
    link = generate_tonic_link(
        info_hash=info_hash,
        display_name="orphan",
        sync_mode="best_effort",
    )
    manager = _build_session_manager(tmp_path)
    # Do not register metadata for this workspace.

    resolver = XetMetadataResolver()
    with pytest.raises(RuntimeError) as exc_info:
        await resolver.resolve(link, session_manager=manager)
    assert "No metadata is available for tonic link" in str(exc_info.value)
    assert info_hash.hex() in str(exc_info.value)


async def test_joined_workspace_materializes_imported_metadata(tmp_path) -> None:
    """Joining from imported metadata should materialize files before publishing a local snapshot."""
    manager = _build_session_manager(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "hello.txt").write_text("hello from source", encoding="utf-8")

    source_key = await manager.add_xet_folder(
        folder_path=str(source),
        check_interval=0.05,
    )
    records = await manager.list_xet_folders()
    source_record = next(record for record in records if record["folder_key"] == source_key)
    metadata_bytes = await manager.get_registered_xet_metadata(source_record["workspace_id"])
    assert metadata_bytes is not None

    tonic_path = tmp_path / "workspace.tonic"
    tonic_path.write_bytes(metadata_bytes)

    destination = tmp_path / "destination"
    destination_key = await manager.add_xet_folder(
        folder_path=str(destination),
        tonic_file=str(tonic_path),
        check_interval=0.05,
    )

    assert destination_key != source_key
    assert (destination / "hello.txt").read_text(encoding="utf-8") == "hello from source"

    destination_records = await manager.list_xet_folders()
    destination_record = next(
        record for record in destination_records if record["folder_key"] == destination_key
    )
    assert destination_record["bootstrap_pending"] is False

    assert await manager.remove_xet_folder(destination_key) is True
    assert await manager.remove_xet_folder(source_key) is True


async def test_best_effort_updates_propagate_between_workspace_runtimes(tmp_path) -> None:
    """Sibling runtimes for one workspace should share create, modify, and delete updates."""
    manager = _build_session_manager(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("version one", encoding="utf-8")

    source_key = await manager.add_xet_folder(
        folder_path=str(source),
        check_interval=0.05,
    )
    source_records = await manager.list_xet_folders()
    source_record = next(record for record in source_records if record["folder_key"] == source_key)
    metadata_bytes = await manager.get_registered_xet_metadata(source_record["workspace_id"])
    assert metadata_bytes is not None

    tonic_path = tmp_path / "workspace.tonic"
    tonic_path.write_bytes(metadata_bytes)
    destination = tmp_path / "destination"
    destination_key = await manager.add_xet_folder(
        folder_path=str(destination),
        tonic_file=str(tonic_path),
        check_interval=0.05,
    )

    source_folder = await manager.get_xet_folder(source_key)
    destination_folder = await manager.get_xet_folder(destination_key)
    assert source_folder is not None
    assert destination_folder is not None

    # Stop destination realtime sync so it does not re-queue notes.txt; clear queue so only
    # the broadcast update is applied (avoids bootstrap/leftover updates for the same file).
    if destination_folder._realtime_sync is not None:
        await destination_folder._realtime_sync.stop()
        destination_folder._realtime_sync = None
    async with destination_folder.sync_manager.queue_lock:
        destination_folder.sync_manager.update_queue.clear()

    (source / "notes.txt").write_text("version two", encoding="utf-8")
    await source_folder._queue_folder_change("modified", "notes.txt")
    started, processed = await destination_folder.sync()
    assert started, "sync() should start successfully"
    assert processed >= 1, (
        f"expected at least one update processed, got {processed}; "
        f"last_error={destination_folder.sync_manager.last_error!r}"
    )
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "version two"

    (source / "extra.txt").write_text("new file", encoding="utf-8")
    await source_folder._queue_folder_change("created", "extra.txt")
    await destination_folder.sync()
    assert (destination / "extra.txt").read_text(encoding="utf-8") == "new file"

    (source / "notes.txt").unlink()
    # Pause destination's realtime sync and watcher so only the broadcast delete
    # is applied; otherwise repeated scans can re-queue notes.txt and recreate it.
    if destination_folder._realtime_sync is not None:
        await destination_folder._realtime_sync.stop()
        destination_folder._realtime_sync = None
    await destination_folder.folder_watcher.stop()
    async with destination_folder.sync_manager.queue_lock:
        destination_folder.sync_manager.update_queue.clear()
    await source_folder._queue_folder_change("deleted", "notes.txt")
    started_del, processed_del = await destination_folder.sync()
    assert started_del, "sync() for delete should start successfully"
    assert processed_del >= 1, (
        f"expected at least one update (delete) processed, got {processed_del}; "
        f"last_error={destination_folder.sync_manager.last_error!r}"
    )
    assert not (destination / "notes.txt").exists(), "notes.txt should be removed after delete sync"

    assert await manager.remove_xet_folder(destination_key) is True
    assert await manager.remove_xet_folder(source_key) is True


async def test_workspace_scoped_updates_do_not_cross_runtimes(tmp_path) -> None:
    """Incoming updates should only be queued for the addressed workspace."""
    manager = _build_session_manager(tmp_path)

    workspace_a = tmp_path / "workspace_a"
    workspace_b = tmp_path / "workspace_b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    (workspace_a / "shared.txt").write_text("workspace-a", encoding="utf-8")
    (workspace_b / "shared.txt").write_text("workspace-b", encoding="utf-8")

    folder_key_a = await manager.add_xet_folder(
        folder_path=str(workspace_a),
        check_interval=0.05,
    )
    folder_key_b = await manager.add_xet_folder(
        folder_path=str(workspace_b),
        check_interval=0.05,
    )

    records = await manager.list_xet_folders()
    record_a = next(record for record in records if record["folder_key"] == folder_key_a)
    record_b = next(record for record in records if record["folder_key"] == folder_key_b)

    folder_a = await manager.get_xet_folder(folder_key_a)
    folder_b = await manager.get_xet_folder(folder_key_b)
    assert folder_a is not None
    assert folder_b is not None

    # Stop realtime sync (and watcher) on both so queue sizes are stable between capture and assert.
    for folder in (folder_a, folder_b):
        if folder._realtime_sync is not None:
            await folder._realtime_sync.stop()
            folder._realtime_sync = None
        await folder.folder_watcher.stop()
    queue_size_before_a = folder_a.sync_manager.get_queue_size()
    queue_size_before_b = folder_b.sync_manager.get_queue_size()
    metadata_a = folder_a.sync_manager.get_file_metadata("shared.txt")
    assert metadata_a is not None

    await manager._handle_incoming_xet_update(
        peer_id="peer-a",
        workspace_id_hex=record_a["workspace_id"],
        file_path="shared.txt",
        chunk_hash=metadata_a.file_hash,
        git_ref=None,
    )

    assert folder_a.sync_manager.get_queue_size() == queue_size_before_a + 1
    assert folder_b.sync_manager.get_queue_size() == queue_size_before_b
    assert record_a["workspace_id"] != record_b["workspace_id"]

    assert await manager.remove_xet_folder(folder_key_b) is True
    assert await manager.remove_xet_folder(folder_key_a) is True


async def test_incoming_update_fetches_metadata_before_materialization(tmp_path) -> None:
    """Incoming updates should recover file metadata from the workspace registry."""
    manager = _build_session_manager(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("initial", encoding="utf-8")

    source_key = await manager.add_xet_folder(
        folder_path=str(source),
        check_interval=0.05,
    )
    source_records = await manager.list_xet_folders()
    source_record = next(record for record in source_records if record["folder_key"] == source_key)
    metadata_bytes = await manager.get_registered_xet_metadata(source_record["workspace_id"])
    assert metadata_bytes is not None

    tonic_path = tmp_path / "workspace.tonic"
    tonic_path.write_bytes(metadata_bytes)
    destination = tmp_path / "destination"
    destination_key = await manager.add_xet_folder(
        folder_path=str(destination),
        tonic_file=str(tonic_path),
        check_interval=0.05,
    )

    source_folder = await manager.get_xet_folder(source_key)
    destination_folder = await manager.get_xet_folder(destination_key)
    assert source_folder is not None
    assert destination_folder is not None

    (source / "notes.txt").write_text("version two", encoding="utf-8")
    updated_metadata = await source_folder._build_file_metadata("notes.txt")
    assert updated_metadata is not None
    await source_folder._refresh_metadata_snapshot()

    # Simulate a receiver that has lost its in-memory metadata for this path.
    destination_folder.sync_manager.file_metadata_by_path.clear()
    parsed_snapshot = dict(destination_folder.parsed_metadata or {})
    xet_metadata = dict(parsed_snapshot.get("xet_metadata", {}))
    xet_metadata["file_metadata"] = []
    parsed_snapshot["xet_metadata"] = xet_metadata
    destination_folder.parsed_metadata = parsed_snapshot

    # Stop destination realtime sync and watcher first, then clear queue, so no updates
    # are added during the registry wait below (ensures only our incoming update is applied).
    if destination_folder._realtime_sync is not None:
        await destination_folder._realtime_sync.stop()
        destination_folder._realtime_sync = None
    await destination_folder.folder_watcher.stop()
    for _ in range(5):
        await asyncio.sleep(0)
    async with destination_folder.sync_manager.queue_lock:
        destination_folder.sync_manager.update_queue.clear()

    # Ensure session registry has the updated metadata before we simulate incoming (avoids
    # handler applying stale metadata when run under load / after other tests).
    tf = TonicFile()
    registry_ready = False
    for _ in range(30):
        reg = await manager.get_registered_xet_metadata(source_record["workspace_id"])
        if reg is not None:
            parsed = tf.parse_bytes(reg)
            xet = (parsed or {}).get("xet_metadata") or {}
            for fm in xet.get("file_metadata", []):
                if isinstance(fm, dict) and fm.get("file_path") == "notes.txt":
                    h = fm.get("file_hash")
                    if h is not None and h == updated_metadata.file_hash:
                        registry_ready = True
                        break
            if registry_ready:
                break
        await asyncio.sleep(0.02)
    if not registry_ready:
        await asyncio.sleep(0.15)

    # Ensure only our incoming update is in the queue (clear again right before enqueue).
    async with destination_folder.sync_manager.queue_lock:
        destination_folder.sync_manager.update_queue.clear()

    await manager._handle_incoming_xet_update(
        peer_id="peer-source",
        workspace_id_hex=source_record["workspace_id"],
        file_path="notes.txt",
        chunk_hash=updated_metadata.file_hash,
        git_ref=None,
    )
    started, processed = await destination_folder.sync()
    assert started, "sync() should start successfully"
    assert processed >= 1, (
        f"expected at least one update processed, got {processed}; "
        f"last_error={destination_folder.sync_manager.last_error!r}"
    )
    # Allow materialization and event processing to complete
    for _ in range(15):
        await asyncio.sleep(0.1)
        if (destination / "notes.txt").exists():
            content = (destination / "notes.txt").read_text(encoding="utf-8")
            if content == "version two":
                break
    content = (destination / "notes.txt").read_text(encoding="utf-8")
    assert content == "version two", (
        f"expected notes.txt content 'version two', got {content!r}; "
        f"processed={processed}, last_error={destination_folder.sync_manager.last_error!r}"
    )
    assert destination_folder.sync_manager.get_file_metadata("notes.txt") is not None

    assert await manager.remove_xet_folder(destination_key) is True
    assert await manager.remove_xet_folder(source_key) is True


async def test_set_xet_folder_sync_mode_updates_runtime_and_transport_state(tmp_path) -> None:
    """Live sync-mode changes should update both runtime and transport state."""
    manager = _build_session_manager(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    folder_key = await manager.add_xet_folder(
        folder_path=str(workspace),
        check_interval=0.05,
    )

    updated = await manager.set_xet_folder_sync_mode(
        folder_key,
        "designated",
        source_peers=["peer-a", "peer-b"],
    )

    assert updated is not None
    assert updated["sync_mode"] == "designated"
    assert updated["source_peers"] == ["peer-a", "peer-b"]

    folders = await manager.list_xet_folders()
    record = next(record for record in folders if record["folder_key"] == folder_key)
    transport_state = manager.get_xet_transport_state(record["workspace_id"])

    assert record["sync_mode"] == "designated"
    assert record["source_peers"] == ["peer-a", "peer-b"]
    assert transport_state is not None
    assert transport_state["sync_mode"] == "designated"
    assert transport_state["source_peers"] == ["peer-a", "peer-b"]

    assert await manager.remove_xet_folder(folder_key) is True
