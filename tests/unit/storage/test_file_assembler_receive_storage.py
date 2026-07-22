# ruff: noqa: INP001
"""Focused receive-storage tests for AsyncFileAssembler."""

from __future__ import annotations

import asyncio
from pathlib import Path  # noqa: TC003
from unittest.mock import AsyncMock

import pytest

from ccbt.storage.file_assembler import AsyncFileAssembler, FileAssemblerError

pytestmark = [pytest.mark.unit]


def _torrent_data() -> dict[str, object]:
    return {
        "name": "payload.bin",
        "info_hash": b"\x01" * 20,
        "total_length": 4,
        "piece_length": 4,
        "pieces": [b"\x02" * 20],
        "num_pieces": 1,
        "file_info": {
            "type": "single",
            "name": "payload.bin",
            "length": 4,
            "total_length": 4,
        },
    }


def _multi_file_torrent_data() -> dict[str, object]:
    return {
        "name": "payload",
        "info_hash": b"\x01" * 20,
        "total_length": 4,
        "piece_length": 4,
        "pieces": [b"\x02" * 20],
        "num_pieces": 1,
        "files": [
            {"name": "first.bin", "full_path": "first.bin", "length": 2},
            {"name": "second.bin", "full_path": "second.bin", "length": 2},
        ],
    }


@pytest.mark.asyncio
async def test_piece_is_marked_written_only_after_disk_future_completes(
    tmp_path: Path,
) -> None:
    """Await every segment Future before reporting a piece written."""
    disk_io = AsyncMock()
    first_write = asyncio.get_running_loop().create_future()
    second_write = asyncio.get_running_loop().create_future()
    disk_io.write_block.side_effect = [first_write, second_write]
    expected_segments = 2
    assembler = AsyncFileAssembler(
        _multi_file_torrent_data(),
        str(tmp_path),
        disk_io_manager=disk_io,
    )

    write_task = asyncio.create_task(
        assembler.write_piece_to_file(0, b"data", use_xet_chunking=False)
    )
    await asyncio.wait_for(disk_io.write_block.wait(), timeout=1.0)

    assert not write_task.done()
    assert not assembler.is_piece_written(0)

    first_write.set_result(None)

    async def wait_for_second_segment() -> None:
        while disk_io.write_block.await_count < expected_segments:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait_for_second_segment(), timeout=1.0)
    assert not write_task.done()
    assert not assembler.is_piece_written(0)

    second_write.set_result(None)
    await asyncio.wait_for(write_task, timeout=1.0)

    assert assembler.is_piece_written(0)
    assert disk_io.write_block.await_args_list[0].args == (
        tmp_path / "first.bin",
        0,
        b"da",
    )
    assert disk_io.write_block.await_args_list[1].args == (
        tmp_path / "second.bin",
        0,
        b"ta",
    )


@pytest.mark.asyncio
async def test_disk_future_failure_does_not_mark_piece_written(
    tmp_path: Path,
) -> None:
    """Propagate disk Future failures without marking the piece written."""
    disk_io = AsyncMock()
    failed_write = asyncio.get_running_loop().create_future()
    failed_write.set_exception(OSError("disk full"))
    disk_io.write_block.return_value = failed_write
    assembler = AsyncFileAssembler(
        _torrent_data(),
        str(tmp_path),
        disk_io_manager=disk_io,
    )

    with pytest.raises(FileAssemblerError, match="disk full"):
        await assembler.write_piece_to_file(0, b"data", use_xet_chunking=False)

    assert not assembler.is_piece_written(0)
