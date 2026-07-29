#!/usr/bin/env python3
"""Compare benchmark JSON artifacts from base and head CI runs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


def _load_thresholds(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _metric_higher_better(metric: str, thresholds: dict[str, Any]) -> bool:
    metric_cfg = thresholds.get("metric", {}).get(metric, {})
    if "higher_better" in metric_cfg:
        return bool(metric_cfg["higher_better"])
    lower_is_better = (
        "elapsed" in metric
        or "duration" in metric
        or "latency" in metric
        or "overhead" in metric
        or metric.endswith("_s")
        or metric.endswith("_ms")
    )
    return not lower_is_better


def _threshold_for(metric: str, benchmark: str, thresholds: dict[str, Any]) -> float:
    metric_cfg = thresholds.get("metric", {}).get(metric, {})
    if "max_regression_percent" in metric_cfg:
        return float(metric_cfg["max_regression_percent"])
    benchmark_cfg = thresholds.get("benchmark", {}).get(benchmark, {})
    if "max_regression_percent" in benchmark_cfg:
        return float(benchmark_cfg["max_regression_percent"])
    defaults = thresholds.get("defaults", {})
    return float(defaults.get("max_regression_percent", 5.0))


def _scenario_map(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    benchmark = str(payload.get("benchmark", "unknown"))
    scenarios = payload.get("scenarios", [])
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(scenarios, list):
        return mapped
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_key = str(scenario.get("scenario", ""))
        metrics = scenario.get("metrics", {})
        if not isinstance(metrics, dict):
            continue
        for metric_name, metric_values in metrics.items():
            if not isinstance(metric_values, dict):
                continue
            mean = metric_values.get("mean")
            if mean is None:
                continue
            mapped[(scenario_key, str(metric_name))] = {
                "benchmark": benchmark,
                "scenario": scenario_key,
                "metric": str(metric_name),
                "mean": float(mean),
                "git": payload.get("meta", {}).get("git", {}),
            }
    return mapped


def compare_payloads(
    base_payloads: list[dict[str, Any]],
    head_payloads: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Compare summarized benchmark payloads and classify metric deltas."""
    base_map: dict[tuple[str, str], dict[str, Any]] = {}
    for payload in base_payloads:
        base_map.update(_scenario_map(payload))

    comparisons: list[dict[str, Any]] = []
    for head_payload in head_payloads:
        head_map = _scenario_map(head_payload)
        for key, head_entry in head_map.items():
            base_entry = base_map.get(key)
            if base_entry is None:
                continue
            benchmark = head_entry["benchmark"]
            metric = head_entry["metric"]
            base_value = float(base_entry["mean"])
            head_value = float(head_entry["mean"])
            if base_value == 0:
                delta_percent = 0.0 if head_value == 0 else 100.0
            else:
                delta_percent = ((head_value - base_value) / base_value) * 100.0

            higher_better = _metric_higher_better(metric, thresholds)
            threshold = _threshold_for(metric, benchmark, thresholds)
            if higher_better:
                improved = delta_percent >= threshold
                regressed = delta_percent <= -threshold
            else:
                improved = delta_percent <= -threshold
                regressed = delta_percent >= threshold

            if regressed:
                status = "regression"
            elif improved:
                status = "improved"
            else:
                status = "unchanged"

            comparisons.append(
                {
                    "benchmark": benchmark,
                    "scenario": head_entry["scenario"],
                    "metric": metric,
                    "base_value": base_value,
                    "head_value": head_value,
                    "delta_percent": delta_percent,
                    "status": status,
                    "base_git": base_entry.get("git", {}),
                    "head_git": head_entry.get("git", {}),
                }
            )

    summary = {
        "total": len(comparisons),
        "regressions": sum(1 for item in comparisons if item["status"] == "regression"),
        "improvements": sum(1 for item in comparisons if item["status"] == "improved"),
        "unchanged": sum(1 for item in comparisons if item["status"] == "unchanged"),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "comparisons": comparisons,
    }


def _load_payloads(directory: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted(directory.glob("bench_*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payloads.append(json.load(handle))
    return payloads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare benchmark JSON artifacts")
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--head", required=True, type=Path)
    parser.add_argument("--thresholds", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    thresholds = _load_thresholds(args.thresholds)
    comparison = compare_payloads(
        _load_payloads(args.base),
        _load_payloads(args.head),
        thresholds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(comparison, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
