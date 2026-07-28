#!/usr/bin/env python3
"""Run the performance benchmark suite and emit normalized CI JSON artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_bench_utils() -> Any:
    module_path = _REPO_ROOT / "tests" / "performance" / "bench_utils.py"
    spec = importlib.util.spec_from_file_location("bench_utils", module_path)
    if spec is None or spec.loader is None:
        msg = f"Unable to load bench_utils from {module_path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_bench_utils = _load_bench_utils()
summarize_results_for_docs = _bench_utils.summarize_results_for_docs
get_git_metadata = _bench_utils.get_git_metadata


@dataclass(frozen=True)
class BenchmarkSpec:
    """One benchmark entry in the CI suite."""

    script: str
    benchmark_key: str
    output_name: str


DEFAULT_BENCHMARKS: tuple[BenchmarkSpec, ...] = (
    BenchmarkSpec("tests/performance/bench_hash_verify.py", "hash_verify", "bench_hash_verify.json"),
    BenchmarkSpec("tests/performance/bench_disk_io.py", "disk_io", "bench_disk_io.json"),
    BenchmarkSpec(
        "tests/performance/bench_piece_assembly.py",
        "piece_assembly",
        "bench_piece_assembly.json",
    ),
    BenchmarkSpec(
        "tests/performance/bench_loopback_throughput.py",
        "loopback_throughput",
        "bench_loopback_throughput.json",
    ),
    BenchmarkSpec("tests/performance/bench_encryption.py", "encryption", "bench_encryption.json"),
)


def _derive_config_name(config_file: str | None) -> str:
    if not config_file:
        return "default"
    stem = Path(config_file).stem
    parts = stem.split("example-config-")
    if len(parts) == 2 and parts[1]:
        return parts[1]
    return stem


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_payload(payload: dict[str, Any], benchmark_key: str, config_name: str) -> dict[str, Any]:
    if "summary" in payload and isinstance(payload["summary"], dict):
        summary = payload["summary"]
        summary.setdefault("benchmark", benchmark_key)
        summary.setdefault("config", config_name)
        return summary

    results = payload.get("results", [])
    if not isinstance(results, list):
        results = []
    return summarize_results_for_docs(benchmark_key, config_name, results, get_git_metadata())


def _find_legacy_artifact(workdir: Path, benchmark_key: str) -> Path | None:
    legacy_dir = workdir / "site" / "reports" / "benchmarks" / "artifacts"
    if not legacy_dir.is_dir():
        return None
    matches = sorted(legacy_dir.glob(f"{benchmark_key}-*.json"))
    return matches[-1] if matches else None


def _run_benchmark(
    spec: BenchmarkSpec,
    *,
    workdir: Path,
    output_dir: Path,
    config_file: str | None,
    record_mode: str,
    quick: bool,
    runner: str,
) -> Path:
    """Execute one benchmark script and write normalized JSON to ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / spec.output_name
    config_name = _derive_config_name(config_file)
    script_path = workdir / spec.script
    if not script_path.is_file():
        msg = f"Benchmark script not found: {script_path}"
        raise FileNotFoundError(msg)

    cmd: list[str]
    if runner == "uv":
        cmd = ["uv", "run", "python", str(script_path)]
    else:
        cmd = [sys.executable, str(script_path)]

    cmd.extend(
        [
            "--record-mode",
            record_mode,
        ]
    )
    if config_file:
        cmd.extend(["--config-file", config_file])
    if quick:
        cmd.append("--quick")

    def _invoke(with_json_out: bool) -> subprocess.CompletedProcess[str]:
        run_cmd = [*cmd]
        if with_json_out:
            run_cmd.extend(["--json-out", str(output_path)])
        return subprocess.run(
            run_cmd,
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )

    completed = _invoke(with_json_out=True)
    if completed.returncode != 0:
        # Older scripts may reject --json-out; retry without it and look for
        # legacy artifact paths or an explicit --output-dir write.
        completed = _invoke(with_json_out=False)

    if completed.returncode != 0:
        legacy = _find_legacy_artifact(workdir, spec.benchmark_key)
        if legacy is None:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            msg = f"Benchmark {spec.benchmark_key} failed ({completed.returncode}): {stderr}"
            raise RuntimeError(msg)
        payload = _normalize_payload(_load_json(legacy), spec.benchmark_key, config_name)
    elif output_path.is_file():
        payload = _normalize_payload(_load_json(output_path), spec.benchmark_key, config_name)
    else:
        legacy = _find_legacy_artifact(workdir, spec.benchmark_key)
        if legacy is None:
            detail = (completed.stderr or completed.stdout or "").strip()
            msg = f"Benchmark {spec.benchmark_key} produced no JSON artifact"
            if detail:
                msg = f"{msg}: {detail}"
            raise RuntimeError(msg)
        payload = _normalize_payload(_load_json(legacy), spec.benchmark_key, config_name)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ccBitTorrent benchmark suite for CI")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workdir", default=Path.cwd(), type=Path)
    parser.add_argument("--config-file", default=None)
    parser.add_argument("--record-mode", default="none")
    parser.add_argument("--runner", choices=("python", "uv"), default="python")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)

    workdir = args.workdir.resolve()
    output_dir = args.output_dir.resolve()
    for spec in DEFAULT_BENCHMARKS:
        _run_benchmark(
            spec,
            workdir=workdir,
            output_dir=output_dir,
            config_file=args.config_file,
            record_mode=args.record_mode,
            quick=args.quick,
            runner=args.runner,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
