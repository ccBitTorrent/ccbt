"""G2/G9 residual claim tests."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.timeout(15)]


def test_xet_no_placeholder_modules() -> None:
    """Deleted placeholders must not be importable."""
    for mod in (
        "ccbt.storage.xet_data_aggregator",
        "ccbt.storage.xet_defrag_prevention",
        "ccbt.storage.xet_file_deduplication",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


def test_xet_config_target_enforced() -> None:
    from ccbt.models import DiskConfig
    from ccbt.storage.xet_chunking import TARGET_CHUNK_SIZE

    assert TARGET_CHUNK_SIZE == 65536
    # DiskConfig default when present
    if hasattr(DiskConfig, "model_fields"):
        fields = DiskConfig.model_fields
        if "xet_chunk_target_size" in fields:
            assert fields["xet_chunk_target_size"].default == 65536


def test_xet_tonic_v2_roundtrip(tmp_path: Path) -> None:
    from ccbt.core.tonic import TonicFile
    from ccbt.models import XetFileMetadata, XetTorrentMetadata
    from ccbt.storage.xet_hashing import XetHasher

    fh = XetHasher.compute_chunk_hash(b"file")
    meta = XetTorrentMetadata(
        chunk_hashes=[fh],
        file_metadata=[
            XetFileMetadata(
                file_path="f.txt", file_hash=fh, chunk_hashes=[fh], total_size=4
            )
        ],
    )
    blob = TonicFile().create(folder_name="ws", xet_metadata=meta)
    path = tmp_path / "ws.tonic"
    path.write_bytes(blob)
    parsed = TonicFile().parse(path)
    assert parsed["info"]["format_version"] == 2
    assert parsed["info"]["suite"] == TonicFile.SUITE_V2
