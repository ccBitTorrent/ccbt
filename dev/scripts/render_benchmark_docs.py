#!/usr/bin/env python3
"""Render benchmark comparison tables and trend history for docs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def render_latest_table(comparison: dict[str, Any]) -> str:
    """Render the latest comparison as a markdown table."""
    lines = ["# Latest Benchmark Comparison", ""]
    comparisons = comparison.get("comparisons", [])
    if not comparisons:
        lines.append("No benchmark comparisons were produced for this run.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Benchmark | Scenario | Metric | Base | Head | Delta % | Status |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for item in comparisons:
        lines.append(
            "| {benchmark} | {scenario} | {metric} | {base_value:.4g} | {head_value:.4g} | {delta_percent:+.2f} | {status} |".format(
                **item
            )
        )
    return "\n".join(lines) + "\n"


def update_history(comparison: dict[str, Any], history_path: Path) -> dict[str, Any]:
    """Append comparison summary entries to benchmark history JSON."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.is_file():
        with history_path.open("r", encoding="utf-8") as handle:
            history = json.load(handle)
    else:
        history = {"series": {}}

    series = history.setdefault("series", {})
    generated_at = comparison.get("generated_at") or datetime.now(timezone.utc).isoformat()
    for item in comparison.get("comparisons", []):
        key = f"{item['benchmark']}::{item['scenario']}::{item['metric']}"
        entries = series.setdefault(key, [])
        entries.append(
            {
                "generated_at": generated_at,
                "base_value": item.get("base_value"),
                "head_value": item.get("head_value"),
                "delta_percent": item.get("delta_percent"),
                "status": item.get("status"),
            }
        )

    with history_path.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)
    return history


def render_trend_markdown(history: dict[str, Any]) -> str:
    """Render simple Mermaid trend charts from history series."""
    lines = ["# Benchmark Trends", ""]
    series = history.get("series", {})
    if not series:
        lines.append("No benchmark history is available yet.")
        return "\n".join(lines) + "\n"

    for key, entries in sorted(series.items()):
        if not entries:
            continue
        benchmark, scenario, metric = key.split("::", 2)
        lines.append(f"## {benchmark} / {scenario} / {metric}")
        lines.append("")
        lines.append("```mermaid")
        lines.append("xychart-beta")
        lines.append('    title "Head value trend"')
        labels = [str(index + 1) for index in range(len(entries))]
        values = [float(entry.get("head_value", 0.0)) for entry in entries]
        lines.append(f"    x-axis [{', '.join(labels)}]")
        lines.append(f'    y-axis "{metric}"')
        lines.append(f"    line [{', '.join(f'{value:.4g}' for value in values)}]")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render benchmark docs from comparison JSON")
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--keep", type=int, default=20)
    args = parser.parse_args(argv)

    with args.comparison.open("r", encoding="utf-8") as handle:
        comparison = json.load(handle)

    latest_md = render_latest_table(comparison)
    history = update_history(comparison, args.history)

    if args.keep > 0:
        for entries in history.get("series", {}).values():
            if len(entries) > args.keep:
                del entries[:-args.keep]

    trend_md = render_trend_markdown(history)
    out_dir = args.out_dir
    _write_markdown(out_dir / "comparison_latest.md", latest_md)
    _write_markdown(out_dir / "trend_charts.md", trend_md)
    with (out_dir / "comparison_latest.json").open("w", encoding="utf-8") as handle:
        json.dump(comparison, handle, indent=2)
    with args.history.open("w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)

    readme = out_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Generated Benchmark Reports\n\n"
            "These files are updated by the benchmark CI workflow.\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
