"""Tests for benchmark JSON compare/render scripts and bench_utils summaries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from tests.performance.bench_utils import (
    _flatten_numeric_samples,
    get_git_metadata,
    summarize_results_for_docs,
)


def _load_script_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def benchmark_compare_module() -> Any:
    """Loaded ``dev/scripts/compare_benchmark_json.py`` module."""
    path = Path("dev/scripts/compare_benchmark_json.py").resolve()
    return _load_script_module("compare_benchmark_json", path)


@pytest.fixture(scope="module")
def benchmark_render_module() -> Any:
    """Loaded ``dev/scripts/render_benchmark_docs.py`` module."""
    path = Path("dev/scripts/render_benchmark_docs.py").resolve()
    return _load_script_module("render_benchmark_docs", path)


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_compare_payloads_marks_regressions(benchmark_compare_module) -> None:
    """Head elapsed mean worse than baseline is flagged as regression."""
    base_payload = _load_fixture(
        Path("tests/unit/performance/fixtures/compare_payloads_base.json")
    )
    head_payload = _load_fixture(
        Path("tests/unit/performance/fixtures/compare_payloads_head.json")
    )
    # One metric per scenario so comparison count and ordering are deterministic.
    for payload in (base_payload, head_payload):
        payload["scenarios"][0]["metrics"] = {
            "elapsed": dict(payload["scenarios"][0]["metrics"]["elapsed"])
        }
    head_payload["scenarios"][0]["metrics"]["elapsed"]["mean"] = 1.2
    thresholds = {
        "defaults": {"max_regression_percent": 5.0},
    }

    comparison = benchmark_compare_module.compare_payloads(
        [base_payload], [head_payload], thresholds
    )

    assert comparison["summary"]["total"] == 1
    assert comparison["summary"]["regressions"] == 1
    assert comparison["comparisons"][0]["status"] == "regression"
    assert comparison["comparisons"][0]["benchmark"] == "hash_verify"
    assert comparison["comparisons"][0]["metric"] == "elapsed"


def test_compare_payloads_identifies_improvement(benchmark_compare_module) -> None:
    """Higher throughput beyond threshold is flagged as improved."""
    base_payload = _load_fixture(
        Path("tests/unit/performance/fixtures/compare_payloads_base.json")
    )
    head_payload = _load_fixture(
        Path("tests/unit/performance/fixtures/compare_payloads_head.json")
    )
    for payload in (base_payload, head_payload):
        payload["scenarios"][0]["metrics"] = {
            "throughput": dict(payload["scenarios"][0]["metrics"]["throughput"])
        }
    head_payload["scenarios"][0]["metrics"]["throughput"]["mean"] = 110.0
    thresholds = {
        "defaults": {"max_regression_percent": 5.0},
    }

    comparison = benchmark_compare_module.compare_payloads(
        [base_payload], [head_payload], thresholds
    )

    assert comparison["summary"]["total"] == 1
    assert comparison["summary"]["improvements"] == 1
    assert comparison["comparisons"][0]["status"] == "improved"
    assert comparison["comparisons"][0]["metric"] == "throughput"


def test_render_latest_and_history_flow(
    tmp_path: Path, benchmark_render_module
) -> None:
    """Render markdown tables and append benchmark history JSON."""
    comparison = {
        "generated_at": "2026-03-20T00:00:00Z",
        "comparisons": [
            {
                "benchmark": "hash_verify",
                "scenario": "size=1",
                "metric": "elapsed",
                "base_value": 1.0,
                "head_value": 1.2,
                "delta_percent": 20.0,
                "status": "regression",
                "base_git": {"commit_hash_short": "base"},
                "head_git": {"commit_hash_short": "head"},
            }
        ],
    }
    out_dir = tmp_path / "generated"
    history_path = out_dir / "benchmark_history.json"
    comparison_path = out_dir / "comparison.json"

    latest_md = benchmark_render_module.render_latest_table(comparison)
    history = benchmark_render_module.update_history(comparison, history_path)
    trend_md = benchmark_render_module.render_trend_markdown(history)
    benchmark_render_module._write_markdown(comparison_path, latest_md)  # noqa: SLF001
    benchmark_render_module._write_markdown(out_dir / "trend.md", trend_md)  # noqa: SLF001

    assert "| hash_verify |" in latest_md
    assert comparison_path.exists()
    assert out_dir.joinpath("trend.md").exists()
    assert "hash_verify" in latest_md
    assert history["series"]


def test_flatten_numeric_samples_nested_lists() -> None:
    """``_flatten_numeric_samples`` unwraps nested list/tuple samples."""
    assert _flatten_numeric_samples([]) == []
    assert _flatten_numeric_samples([1.0, 2.0]) == [1.0, 2.0]
    assert _flatten_numeric_samples([[1.0], [2.0, 3.0], [[4.0]]]) == [
        1.0,
        2.0,
        3.0,
        4.0,
    ]


def test_benchmark_scripts_validate() -> None:
    """Benchmark runner scripts must compile before CI executes them."""
    validate_module = _load_script_module(
        "validate_benchmark_scripts",
        Path("dev/scripts/validate_benchmark_scripts.py").resolve(),
    )
    assert validate_module.validate_benchmark_scripts() == []


def test_summarize_results_for_docs_duplicate_scenarios() -> None:
    """Duplicate scenario rows aggregate without breaking ``statistics.mean``."""
    rows = [
        {
            "size_bytes": 1048576,
            "iterations": 8,
            "elapsed_s": 0.001,
            "bytes_processed": 8388608,
            "throughput_bytes_per_s": 1e9,
        },
        {
            "size_bytes": 1048576,
            "iterations": 8,
            "elapsed_s": 0.002,
            "bytes_processed": 8388608,
            "throughput_bytes_per_s": 2e9,
        },
    ]
    summary = summarize_results_for_docs("hash_verify", "ci", rows, get_git_metadata())
    assert summary["benchmark"] == "hash_verify"
    assert len(summary["scenarios"]) == 1
    elapsed = summary["scenarios"][0]["metrics"]["elapsed_s"]
    expected_count = 2
    expected_mean = 0.0015
    assert elapsed["count"] == expected_count
    assert elapsed["mean"] == expected_mean
