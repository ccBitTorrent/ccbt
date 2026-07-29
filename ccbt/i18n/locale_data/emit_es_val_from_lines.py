"""Build ``es_val_N.json`` from ``es_val_N.jsonl`` (one JSON string per line)."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        msg = "usage: emit_es_val_from_lines.py <N>  (N in 0..5)"
        raise SystemExit(msg)
    n = int(sys.argv[1])
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    jsonl_path = here / f"es_val_{n}.jsonl"
    keys_path = root / "dev" / f"es_slice_{n}.json"
    keys: list[str] = json.loads(keys_path.read_text(encoding="utf-8"))
    vals: list[str] = []
    for line_no, ln in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), 1):
        ln = ln.strip()
        if not ln:
            continue
        try:
            vals.append(json.loads(ln))
        except json.JSONDecodeError as e:
            msg = f"{jsonl_path}:{line_no}: {e}"
            raise SystemExit(msg) from e
    if len(vals) != len(keys):
        msg = f"es_val_{n}.jsonl has {len(vals)} entries but es_slice_{n}.json has {len(keys)} keys"
        raise SystemExit(msg)
    out = here / f"es_val_{n}.json"
    out.write_text(json.dumps(vals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
