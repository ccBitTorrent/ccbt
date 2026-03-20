from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

def _load_script_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def benchmark_compare_module():
    path = Path("dev/scripts/compare_benchmark_json.py").resolve()
    return _load_script_module("compare_benchmark_json", path)


def benchmark_render_module():
    path = Path("dev/scripts/render_benchmark_docs.py").resolve()
    return _load_script_module("render_benchmark_docs", path)


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_compare_payloads_marks_regressions(benchmark_compare_module) -> None:
    base_payload = _load_fixture(Path("tests/unit/performance/fixtures/compare_payloads_base.json"))
    head_payload = _load_fixture(Path("tests/unit/performance/fixtures/compare_payloads_head.json"))
    head_payload["scenarios"][0]["metrics"]["elapsed"]["mean"] = 1.2
    thresholds = {
        "defaults": {"max_regression_percent": 5.0},
    }

    comparison = benchmark_compare_module.compare_payloads([base_payload], [head_payload], thresholds)

    assert comparison["summary"]["total"] == 1
    assert comparison["summary"]["regressions"] == 1
    assert comparison["comparisons"][0]["status"] == "regression"
    assert comparison["comparisons"][0]["benchmark"] == "hash_verify"


def test_compare_payloads_identifies_improvement(benchmark_compare_module) -> None:
    base_payload = _load_fixture(Path("tests/unit/performance/fixtures/compare_payloads_base.json"))
    head_payload = _load_fixture(Path("tests/unit/performance/fixtures/compare_payloads_head.json"))
    head_payload["scenarios"][0]["metrics"]["elapsed"]["mean"] = 1.0
    head_payload["scenarios"][0]["metrics"]["throughput"]["mean"] = 110.0
    thresholds = {
        "defaults": {"max_regression_percent": 5.0},
    }

    comparison = benchmark_compare_module.compare_payloads([base_payload], [head_payload], thresholds)

    assert comparison["summary"]["improvements"] == 1
    assert comparison["comparisons"][0]["status"] == "improved"


def test_render_latest_and_history_flow(tmp_path: Path, benchmark_render_module) -> None:
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
    benchmark_render_module._write_markdown(comparison_path, latest_md)
    benchmark_render_module._write_markdown(out_dir / "trend.md", trend_md)

    assert "| hash_verify |" in latest_md
    assert comparison_path.exists()
    assert out_dir.joinpath("trend.md").exists()
    assert "hash_verify" in latest_md
    assert history["series"]
