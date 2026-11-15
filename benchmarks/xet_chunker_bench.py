"""XET chunker throughput micro-benchmark (WS9 performance gate)."""

from __future__ import annotations

import time

from ccbt.storage.xet_chunking import GearhashChunker

THRESHOLD_MB_S = 2.0  # Python scalar Gearhash floor (not native speed)


def main() -> None:
    data = (b"0123456789abcdef" * 4096) * 64  # ~4 MiB
    chunker = GearhashChunker()
    t0 = time.perf_counter()
    chunks = chunker.chunk_buffer(data)
    elapsed = time.perf_counter() - t0
    mb_s = (len(data) / (1024 * 1024)) / max(elapsed, 1e-9)
    print(f"chunks={len(chunks)} elapsed_s={elapsed:.4f} mb_s={mb_s:.1f}")
    if mb_s < THRESHOLD_MB_S:
        raise SystemExit(f"chunker throughput {mb_s:.1f} MB/s below {THRESHOLD_MB_S}")


if __name__ == "__main__":
    main()
