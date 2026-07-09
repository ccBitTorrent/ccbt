#!/usr/bin/env python3
"""Shared utilities for benchmark recording and git metadata collection."""
from __future__ import annotations

import json
import logging
import os
import platform
import statistics
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Optional

DimensionKey = str
MetricName = str
DimensionValue = Any


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_DIMENSION_KEYS: set[str] = {
    "size_bytes",
    "piece_size_bytes",
    "block_size_bytes",
    "payload_bytes",
    "pipeline_depth",
    "dh_key_size",
    "iterations",
    "data_size_bytes",
    "block_size",
    "buffer_size",
    "cipher",
    "operation",
    "role",
    "stream_type",
    "transfer_type",
    "connection_type",
}

_METRIC_HINTS = (
    "elapsed",
    "throughput",
    "duration",
    "latency",
    "overhead",
    "stall",
    "memory",
    "bytes_processed",
    "bytes_transferred",
)


def _platform_info() -> Dict[str, str]:
    return {"system": platform.system(), "release": platform.release(), "python": sys.version.split()[0]}


def _to_dict(result: Any) -> Dict[str, Any]:
    """Convert a benchmark result item to a JSON-serializable dictionary."""
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, "__dict__"):
        if is_dataclass(result):
            return asdict(result)
        return dict(result.__dict__)
    return {"result": str(result)}


def _to_dict_list(results: Iterable[Any]) -> list[dict[str, Any]]:
    return [_to_dict(item) for item in results]


def _flatten_numeric_samples(values: Iterable[Any]) -> list[float]:
    """Recursively flatten nested list/tuple samples and coerce leaves to float.

    Defensive: older summarize logic could store ``[[x]]`` per metric; ``statistics.mean``
    then fails on Python 3.11+. Used when aggregating benchmark metrics.
    """
    out: list[float] = []
    for v in values:
        if isinstance(v, (list, tuple)):
            out.extend(_flatten_numeric_samples(v))
        else:
            out.append(float(v))
    return out


def _is_metric_field(name: str, value: Any) -> bool:
    if name in _DIMENSION_KEYS:
        return False
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    lower = name.lower()
    if lower in {"size_bytes", "iterations"}:
        return False
    if any(hint in lower for hint in _METRIC_HINTS):
        return True
    if lower.endswith("_s") or lower.endswith("_ms") or lower.endswith("_ms_per_x"):
        return True
    # By default, keep any unknown numeric values as metrics so render side can still compare.
    return True


def get_git_metadata() -> Dict[str, Any]:
    """Get git metadata for the current repository state."""
    metadata: Dict[str, Any] = {
        "commit_hash": None,
        "commit_hash_short": None,
        "branch": None,
        "author": None,
        "is_dirty": False,
    }

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            metadata["commit_hash"] = commit_hash
            metadata["commit_hash_short"] = commit_hash[:7] if commit_hash else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get commit hash: {e}")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            metadata["branch"] = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get branch: {e}")
        metadata["branch"] = os.environ.get("GIT_BRANCH") or os.environ.get("BRANCH_NAME")

    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            metadata["author"] = result.stdout.strip()
        else:
            metadata["author"] = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("USER") or os.environ.get("USERNAME")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get author: {e}")
        metadata["author"] = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("USER") or os.environ.get("USERNAME")

    try:
        result = subprocess.run(
            ["git", "diff", "--quiet"],
            capture_output=True,
            check=False,
            timeout=5,
        )
        metadata["is_dirty"] = result.returncode != 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to check dirty status: {e}")

    return metadata


def summarize_results_for_docs(
    benchmark_name: str,
    config_name: str,
    results: list[Any],
    git_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Build compact benchmark summaries for documentation rendering.

    The returned structure normalizes per-case fields into scenario groups to keep comparisons stable.
    """
    serialized = _to_dict_list(results)
    timestamp = datetime.now(timezone.utc).isoformat()
    by_scenario: dict[str, tuple[dict[DimensionKey, DimensionValue], dict[MetricName, list[float]]]] = {}

    for index, item in enumerate(serialized):
        dimensions: dict[DimensionKey, DimensionValue] = {}
        metric_values: dict[MetricName, list[float]] = {}
        for key, value in item.items():
            if _is_metric_field(key, value):
                metric_values.setdefault(key, []).append(float(value))
            else:
                dimensions[key] = value

        if not dimensions:
            dimensions = {"_index": index}

        dimension_items = sorted(dimensions.items(), key=lambda item: item[0])
        scenario_key = ",".join(f"{key}={json.dumps(value, sort_keys=True)}" for key, value in dimension_items)

        existing = by_scenario.get(scenario_key)
        if existing is None:
            # metric_values values are already list[float]; copy and flatten (guards legacy [[x]] shape).
            by_scenario[scenario_key] = (
                dimensions,
                {k: _flatten_numeric_samples(vals) for k, vals in metric_values.items()},
            )
            continue

        _, existing_metrics = existing
        for metric, values in metric_values.items():
            existing_metrics.setdefault(metric, []).extend(_flatten_numeric_samples(values))

    scenarios: list[dict[str, Any]] = []
    for scenario_key, (dimensions, metric_values) in by_scenario.items():
        metrics: dict[str, Any] = {}
        for metric, values in metric_values.items():
            flat = _flatten_numeric_samples(values)
            if not flat:
                continue
            metrics[metric] = {
                "count": len(flat),
                "mean": statistics.mean(flat),
                "min": min(flat),
                "max": max(flat),
            }

        scenarios.append(
            {
                "scenario": scenario_key,
                "dimensions": dimensions,
                "metrics": metrics,
            }
        )

    return {
        "benchmark": benchmark_name,
        "config": config_name,
        "generated_at": timestamp,
        "meta": {
            "git": git_meta,
            "platform": _platform_info(),
        },
        "scenarios": scenarios,
    }


def determine_record_mode(
    requested_mode: Optional[str], env_var: Optional[str] = None
) -> Literal["pre-commit", "commit", "both", "none"]:
    """Determine the actual recording mode based on context.

    Args:
        requested_mode: Requested mode ('auto', 'pre-commit', 'commit', 'both', 'none')
        env_var: Optional environment variable override

    Returns:
        Actual recording mode to use
    """
    # Check environment variable override
    if env_var:
        if env_var in ("pre-commit", "commit", "both", "none"):
            return env_var  # type: ignore[return-value]
        logger.warning(f"Invalid record mode in env var: {env_var}, using requested_mode")

    # Check PRE_COMMIT environment variable for pre-commit context
    if os.environ.get("PRE_COMMIT"):
        if requested_mode in ("auto", None):
            return "pre-commit"
        if requested_mode == "both":
            return "both"

    # Handle explicit modes
    if requested_mode == "auto" or requested_mode is None:
        # Auto-detect: if in pre-commit context, use pre-commit, otherwise none for safety
        if os.environ.get("PRE_COMMIT"):
            return "pre-commit"
        return "none"

    if requested_mode in ("pre-commit", "commit", "both", "none"):
        return requested_mode  # type: ignore[return-value]

    logger.warning(f"Unknown record mode: {requested_mode}, defaulting to 'none'")
    return "none"


def write_per_run_json(
    benchmark_name: str,
    config_name: str,
    results: list[Any],
    git_meta: Dict[str, Any],
    runs_dir: Path,
) -> Path:
    """Write a per-run benchmark JSON file.

    Args:
        benchmark_name: Name of the benchmark
        config_name: Configuration name used
        results: List of benchmark results (dataclass instances)
        git_meta: Git metadata dictionary
        runs_dir: Directory to write per-run files to

    Returns:
        Path to the written file
    """
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp and commit hash
    timestamp = datetime.now(timezone.utc)
    timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")
    commit_short = git_meta.get("commit_hash_short") or "unknown"
    filename = f"{benchmark_name}-{timestamp_str}-{commit_short}.json"

    results_dict = _to_dict_list(results)

    meta = {
        "benchmark": benchmark_name,
        "config": config_name,
        "timestamp": timestamp.isoformat(),
        "platform": _platform_info(),
        "git": git_meta,
    }

    data = {
        "meta": meta,
        "results": results_dict,
        "summary": summarize_results_for_docs(benchmark_name, config_name, results, git_meta),
    }

    # Write JSON file
    path = runs_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return path


def update_time_series(
    benchmark_name: str,
    config_name: str,
    results: list[Any],
    git_meta: Dict[str, Any],
    platform_info: Dict[str, str],
    timeseries_dir: Path,
) -> None:
    """Update the time-series JSON file for a benchmark.

    Args:
        benchmark_name: Name of the benchmark
        config_name: Configuration name used
        results: List of benchmark results (dataclass instances)
        git_meta: Git metadata dictionary
        platform_info: Platform information dictionary
        timeseries_dir: Directory containing time-series files
    """
    timeseries_dir.mkdir(parents=True, exist_ok=True)

    # File path for time-series
    timeseries_file = timeseries_dir / f"{benchmark_name}_timeseries.json"

    # Read existing file or initialize
    if timeseries_file.exists():
        try:
            with timeseries_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read existing timeseries file: {e}, initializing new")
            data = {"entries": []}
    else:
        data = {"entries": []}

    results_dict = _to_dict_list(results)

    # Create new entry
    new_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git": git_meta,
        "platform": platform_info,
        "config": config_name,
        "results": results_dict,
    }

    # Append to entries
    data["entries"].append(new_entry)

    # Atomic write: write to temp file, then rename
    temp_file = timeseries_file.with_suffix(".json.tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(timeseries_file)
    except OSError as e:
        logger.error(f"Failed to write timeseries file: {e}")
        if temp_file.exists():
            temp_file.unlink()
        raise


def record_benchmark_results(
    benchmark_name: str,
    config_name: str,
    results: list[Any],
    record_mode: str,
    output_base: Optional[Path] = None,
    json_out: Optional[Path] = None,
) -> tuple[Optional[Path], Optional[Path]]:
    """Record benchmark results according to the specified mode.

    Args:
        benchmark_name: Name of the benchmark
        config_name: Configuration name used
        results: List of benchmark results
        record_mode: Recording mode ('auto', 'pre-commit', 'commit', 'both', 'none')
        output_base: Base directory for output (defaults to docs/reports/benchmarks)
        json_out: Optional explicit JSON output path or directory for CI artifacts

    Returns:
        Tuple of (per_run_path, timeseries_path), either can be None
    """
    if output_base is None:
        output_base = Path("docs/reports/benchmarks")

    # Get git metadata
    git_meta = get_git_metadata()

    # Determine actual record mode
    actual_mode = determine_record_mode(record_mode)

    if json_out is not None:
        json_out_path = Path(json_out)
        if json_out_path.suffix.lower() != ".json":
            commit_short = git_meta.get("commit_hash_short") or "unknown"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            json_out_path = json_out_path / f"{benchmark_name}-{timestamp}-{commit_short}.json"
        payload = {
            "meta": {
                "benchmark": benchmark_name,
                "config": config_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "platform": _platform_info(),
                "git": git_meta,
            },
            "results": _to_dict_list(results),
            "summary": summarize_results_for_docs(benchmark_name, config_name, results, git_meta),
        }
        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with json_out_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info(f"Wrote benchmark JSON artifact: {json_out_path}")
        except OSError as e:
            logger.error(f"Failed to write benchmark JSON artifact: {e}")

    if actual_mode == "none":
        return (None, None)

    per_run_path: Optional[Path] = None
    timeseries_path: Optional[Path] = None

    # Platform info
    platform_info = {
        "system": platform.system(),
        "release": platform.release(),
        "python": sys.version.split()[0],
    }

    # Write per-run file if mode includes pre-commit or commit
    if actual_mode in ("pre-commit", "commit", "both"):
        runs_dir = output_base / "runs"
        try:
            per_run_path = write_per_run_json(benchmark_name, config_name, results, git_meta, runs_dir)
            logger.info(f"Wrote per-run benchmark: {per_run_path}")
        except Exception as e:
            logger.error(f"Failed to write per-run benchmark: {e}")

    # Update time-series if mode includes commit
    if actual_mode in ("commit", "both"):
        timeseries_dir = output_base / "timeseries"
        try:
            update_time_series(benchmark_name, config_name, results, git_meta, platform_info, timeseries_dir)
            timeseries_path = timeseries_dir / f"{benchmark_name}_timeseries.json"
            logger.info(f"Updated timeseries: {timeseries_path}")
        except Exception as e:
            logger.error(f"Failed to update timeseries: {e}")

    return (per_run_path, timeseries_path)

