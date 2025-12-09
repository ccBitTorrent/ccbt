"""Graph metrics module for dashboard graphs.

Provides series definitions, presets, data extraction, and utilities
for working with graphable metrics.
"""

from __future__ import annotations

from ccbt.interface.metrics.graph_series import (
    GraphMetricSeries,
    SeriesCategory,
    SeriesConfiguration,
    SeriesPreset,
    are_series_compatible,
    create_per_torrent_series,
    export_configuration,
    extract_multiple_series_values,
    extract_series_value,
    format_series_value,
    get_per_torrent_series_key,
    get_preset,
    get_series_display_info,
    group_series_by_unit,
    import_configuration,
    list_presets,
    list_series,
    list_series_by_category,
    validate_series_keys,
)

__all__ = [
    "GraphMetricSeries",
    "SeriesCategory",
    "SeriesConfiguration",
    "SeriesPreset",
    "are_series_compatible",
    "create_per_torrent_series",
    "export_configuration",
    "extract_multiple_series_values",
    "extract_series_value",
    "format_series_value",
    "get_per_torrent_series_key",
    "get_preset",
    "get_series_display_info",
    "group_series_by_unit",
    "import_configuration",
    "list_presets",
    "list_series",
    "list_series_by_category",
    "validate_series_keys",
]










