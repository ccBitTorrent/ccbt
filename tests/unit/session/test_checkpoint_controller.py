import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from ccbt.models import TorrentCheckpoint
from ccbt.session.checkpointing import CheckpointController
from ccbt.session.models import SessionContext
from ccbt.session.tasks import TaskSupervisor


class FakePieceManager:
    def __init__(self, info_hash: bytes, total_pieces: int = 1) -> None:
        self._info_hash = info_hash
        self._total_pieces = total_pieces
        self.on_checkpoint_save = None

    async def get_checkpoint_state(self, name: str, info_hash: bytes, output_dir: str) -> TorrentCheckpoint:
        assert info_hash == self._info_hash
        return TorrentCheckpoint(
            info_hash=info_hash,
            torrent_name=name,
            total_pieces=self._total_pieces,
            output_dir=output_dir,
        )


class FakeCheckpointManager:
    def __init__(self) -> None:
        self.saved: list[TorrentCheckpoint] = []

    async def save_checkpoint(self, checkpoint: TorrentCheckpoint) -> None:
        self.saved.append(checkpoint)


@pytest.mark.asyncio
async def test_checkpoint_controller_batch_and_save(tmp_path: Path):
    info_hash = b"x" * 20
    piece_manager = FakePieceManager(info_hash)
    cm = FakeCheckpointManager()
    ctx = SessionContext(
        config=SimpleNamespace(),
        torrent_data={"info_hash": info_hash, "name": "t"},
        output_dir=tmp_path,
        piece_manager=piece_manager,
        checkpoint_manager=cm,
        info=SimpleNamespace(info_hash=info_hash, name="t"),
        logger=None,
    )
    sup = TaskSupervisor()
    ctrl = CheckpointController(ctx, sup, checkpoint_manager=cm)
    ctrl.bind_piece_manager_checkpoint_hook()
    ctrl.enable_batching(interval=0.01, pieces=1)

    # Enqueue a couple saves and ensure at least one persisted
    await ctrl.enqueue_save()
    await asyncio.sleep(0.05)

    assert len(cm.saved) >= 1
    await ctrl.stop()


