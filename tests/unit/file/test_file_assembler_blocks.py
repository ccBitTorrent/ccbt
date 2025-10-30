import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.file]

from ccbt.storage.file_assembler import AsyncFileAssembler
from ccbt.models import FileInfo


def make_td_single():
    return {
        "name": "t.txt",
        "info_hash": b"x" * 20,
        "files": [
            FileInfo(
                name="t.txt",
                length=1024,
                path=["t.txt"],
            ),
        ],
        "total_length": 1024,
        "piece_length": 512,
        "pieces": [b"x" * 20, b"x" * 20],
        "num_pieces": 2,
    }


@pytest.mark.asyncio
async def test_read_block_roundtrip(tmp_path):
    td = make_td_single()

    # Create mock disk I/O manager
    mock_disk_io = Mock()
    mock_disk_io.start = AsyncMock()
    mock_disk_io.stop = AsyncMock()

    # Mock write_block to write synchronously to files
    async def mock_write_block(file_path, offset, data):
        import os

        os.makedirs(file_path.parent, exist_ok=True)
        with open(file_path, "r+b" if file_path.exists() else "wb") as f:
            f.seek(offset)
            f.write(data)
        # Return a completed future
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result(None)
        return future

    mock_disk_io.write_block = AsyncMock(side_effect=mock_write_block)

    # Mock read_block to read synchronously from files
    async def mock_read_block(file_path, offset, length):
        if not file_path.exists():
            return None
        with open(file_path, "rb") as f:
            f.seek(offset)
            return f.read(length)

    mock_disk_io.read_block = AsyncMock(side_effect=mock_read_block)

    async with AsyncFileAssembler(
        td,
        output_dir=str(tmp_path),
        disk_io_manager=mock_disk_io,
    ) as asm:
        # write two pieces
        await asm.write_piece_to_file(0, b"A" * 512)
        await asm.write_piece_to_file(1, b"B" * 512)

        # read across piece boundary
        data = await asm.read_block(0, 256, 512)
        assert data == b"A" * 256 + b"B" * 256
