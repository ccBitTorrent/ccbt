# Benchmark Generated Artifacts

This directory stores benchmark artifacts that are committed by CI so
`mkdocs` always has source files for the live benchmark report pages.

The contents are generated from CI comparison runs and are intended to be
stable enough for documentation diffs while still reflecting recent performance
trends.

## Files

- `comparison_latest.md` contains the most recent base-vs-head comparison table.
- `trend_charts.md` contains rendered Mermaid trend charts for the tracked
  benchmark-series.
- `benchmark_history.json` stores compact historical values used to generate trend
  charts.
