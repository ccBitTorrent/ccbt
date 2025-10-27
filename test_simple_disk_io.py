import asyncio
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_disk_io_simple_version(tmp_path):
    """Test a simplified version of disk I/O operations."""

    class SimpleDiskIO:
        def __init__(self):
            self.executor = None

        async def start(self):
            from concurrent.futures import ThreadPoolExecutor
            self.executor = ThreadPoolExecutor(max_workers=1)

        async def stop(self):
            if self.executor:
                self.executor.shutdown(wait=True)

        async def write_block(self, file_path: Path, offset: int, data: bytes):
            """Simple write operation."""
            def write_sync():
                # Ensure parent directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Ensure file exists and is large enough
                if not file_path.exists():
                    with open(file_path, "wb") as f:
                        f.write(b"\x00" * (offset + len(data)))

                with open(file_path, "r+b") as f:
                    f.seek(offset)
                    f.write(data)

            await asyncio.get_event_loop().run_in_executor(self.executor, write_sync)

        async def read_block(self, file_path: Path, offset: int, length: int):
            """Simple read operation."""
            def read_sync():
                with open(file_path, "rb") as f:
                    f.seek(offset)
                    return f.read(length)

            return await asyncio.get_event_loop().run_in_executor(self.executor, read_sync)

    disk_io = SimpleDiskIO()

    try:
        await disk_io.start()

        test_file = tmp_path / "test.txt"

        # Write some data
        await disk_io.write_block(test_file, 0, b"Hello, World!")

        # Read it back
        data = await disk_io.read_block(test_file, 0, 13)
        assert data == b"Hello, World!"

    finally:
        await disk_io.stop()
