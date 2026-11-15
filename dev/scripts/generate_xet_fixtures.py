"""Generate deterministic XET conformance fixtures and their manifest.

Fixtures are generated, not vendored binaries: seeded inputs whose chunk
boundaries/hashes the golden tests reproduce. Run after codec changes
only if the vectors themselves change; manifest hashes then update.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "data" / "xet"


def _rand_bytes(seed: int, n: int) -> bytes:
    return random.Random(seed).randbytes(n)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vectors = {
        "comment": "Deterministic synthetic inputs. Bytes are regenerated in tests from these seeds; expected outputs are produced by the upstream algorithm and pinned by golden tests.",
        "chunking_inputs": [
            {"name": "empty", "kind": "empty"},
            {"name": "tiny", "kind": "bytes_hex", "data_hex": "68656c6c6f20786574"},
            {"name": "below_min", "kind": "random", "seed": 1, "size": 8191},
            {"name": "exact_min", "kind": "random", "seed": 2, "size": 8192},
            {"name": "exact_max", "kind": "random", "seed": 3, "size": 131072},
            {"name": "zeros_300k", "kind": "zeros", "size": 300000},
            {"name": "random_1m", "kind": "random", "seed": 42, "size": 1048576},
            {"name": "pattern_1m", "kind": "pattern", "pattern_hex": "6162636465666768", "size": 1048576},
            {"name": "edit_locality_base", "kind": "random", "seed": 7, "size": 524288},
        ],
    }
    (OUT / "synthetic_vectors.json").write_text(
        json.dumps(vectors, indent=2) + "\n", encoding="utf-8"
    )

    manifest: dict[str, str] = {}
    for path in sorted(OUT.glob("*")):
        if path.name == "manifest.json" or not path.is_file():
            continue
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "manifest.json").write_text(
        json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"fixtures in {OUT}: {sorted(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
