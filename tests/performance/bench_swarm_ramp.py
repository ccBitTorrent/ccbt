"""Deterministic virtual-swarm ramp benchmark.

Usage: python tests/performance/bench_swarm_ramp.py [--peers 20,50,100]
Writes/compares JSON; in CI use run_benchmark() and assert gates in tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ccbt.performance.swarm_sim import run_scenario


def run_benchmark(peer_counts=(20, 50, 100), seed: int = 1234) -> dict:
    return {
        str(n): run_scenario(n, seed=seed)
        for n in peer_counts
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peers", default="20,50,100")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    counts = [int(x) for x in args.peers.split(",") if x.strip()]
    results = run_benchmark(counts, seed=args.seed)
    text = json.dumps(results, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
