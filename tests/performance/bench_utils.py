#!/usr/bin/env python3
"""Shared utilities for benchmark recording and git metadata collection."""
from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def get_git_metadata() -> Dict[str, Any]:
    """Get git metadata for the current repository state.

    Returns:
        Dictionary with git metadata: commit_hash, commit_hash_short, branch, author, is_dirty
    """
    metadata: Dict[str, Any] = {
        "commit_hash": None,
        "commit_hash_short": None,
        "branch": None,
        "author": None,
        "is_dirty": False,
    }

    try:
        # Get commit hash
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
        # Get branch name
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
        # Fallback to environment variable
        metadata["branch"] = os.environ.get("GIT_BRANCH") or os.environ.get("BRANCH_NAME")

    try:
        # Get author
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
            # Fallback to environment variable
            metadata["author"] = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("USER") or os.environ.get("USERNAME")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get author: {e}")
        metadata["author"] = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("USER") or os.environ.get("USERNAME")

    try:
        # Check if working tree is dirty
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


def determine_record_mode(
    requested_mode: str | None, env_var: str | None = None
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

    # Build metadata
    meta = {
        "benchmark": benchmark_name,
        "config": config_name,
        "timestamp": timestamp.isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
        "git": git_meta,
    }

    # Convert results to dict (handle both dataclass and dict)
    results_dict = []
    for r in results:
        if hasattr(r, "__dict__"):
            # Try asdict first (for dataclasses)
            try:
                from dataclasses import asdict

                results_dict.append(asdict(r))
            except (TypeError, AttributeError):
                # Fallback to __dict__
                results_dict.append(r.__dict__)
        elif isinstance(r, dict):
            results_dict.append(r)
        else:
            # Try to convert to dict
            results_dict.append({"result": str(r)})

    data = {"meta": meta, "results": results_dict}

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

    # Convert results to dict
    results_dict = []
    for r in results:
        if hasattr(r, "__dict__"):
            try:
                from dataclasses import asdict

                results_dict.append(asdict(r))
            except (TypeError, AttributeError):
                results_dict.append(r.__dict__)
        elif isinstance(r, dict):
            results_dict.append(r)
        else:
            results_dict.append({"result": str(r)})

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
    output_base: Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Record benchmark results according to the specified mode.

    Args:
        benchmark_name: Name of the benchmark
        config_name: Configuration name used
        results: List of benchmark results
        record_mode: Recording mode ('auto', 'pre-commit', 'commit', 'both', 'none')
        output_base: Base directory for output (defaults to docs/reports/benchmarks)

    Returns:
        Tuple of (per_run_path, timeseries_path), either can be None
    """
    if output_base is None:
        output_base = Path("docs/reports/benchmarks")

    # Get git metadata
    git_meta = get_git_metadata()

    # Determine actual record mode
    actual_mode = determine_record_mode(record_mode)

    if actual_mode == "none":
        return (None, None)

    per_run_path: Path | None = None
    timeseries_path: Path | None = None

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

