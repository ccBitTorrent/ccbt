"""Graph metric series registry for dashboard graphs.

Provides a central definition of graphable metrics so widgets can dynamically
render legends, units, and styling without duplicating metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple


class SeriesCategory(Enum):
    """High-level categories for grouping graph metrics."""

    SPEED = "speed"
    DISK = "disk"
    TRANSFER = "transfer"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass(frozen=True)
class GraphMetricSeries:
    """Metadata for a single graphable metric series."""

    key: str
    label: str
    unit: str = "KiB/s"
    color: str = "green"
    style: str = "solid"
    description: str | None = None
    category: SeriesCategory = SeriesCategory.SPEED
    source_path: Tuple[str, ...] = ("global_stats",)
    scale: float = 1.0


SERIES_REGISTRY: Dict[str, GraphMetricSeries] = {
    # --- Rate limits & payload speeds ---
    "upload_rate_limit": GraphMetricSeries(
        key="upload_rate_limit",
        label="Upload Rate Limit",
        color="bright_magenta",
        description="Configured maximum upload rate",
        source_path=("global_stats", "upload_rate_limit"),
    ),
    "download_rate_limit": GraphMetricSeries(
        key="download_rate_limit",
        label="Download Rate Limit",
        color="bright_cyan",
        description="Configured maximum download rate",
        source_path=("global_stats", "download_rate_limit"),
    ),
    "upload_rate_payload": GraphMetricSeries(
        key="upload_rate_payload",
        label="Upload Rate (Payload)",
        color="yellow",
        source_path=("global_stats", "upload_rate"),
    ),
    "download_rate_payload": GraphMetricSeries(
        key="download_rate_payload",
        label="Download Rate (Payload)",
        color="bright_green",
        source_path=("global_stats", "download_rate"),
    ),
    "upload_rate_local": GraphMetricSeries(
        key="upload_rate_local",
        label="Upload Rate (Local Peers)",
        color="orange1",
        source_path=("global_stats", "upload_rate_local"),
    ),
    "download_rate_local": GraphMetricSeries(
        key="download_rate_local",
        label="Download Rate (Local Peers)",
        color="chartreuse4",
        source_path=("global_stats", "download_rate_local"),
    ),
    "upload_rate_overhead": GraphMetricSeries(
        key="upload_rate_overhead",
        label="Upload Rate (incl. overhead)",
        color="pink1",
        source_path=("global_stats", "upload_overhead"),
    ),
    "download_rate_overhead": GraphMetricSeries(
        key="download_rate_overhead",
        label="Download Rate (incl. overhead)",
        color="spring_green2",
        source_path=("global_stats", "download_overhead"),
    ),
    "send_rate_player": GraphMetricSeries(
        key="send_rate_player",
        label="Send Rate to Player",
        color="gold1",
        description="Streaming send rate used for media playback",
        source_path=("global_stats", "send_rate_player"),
    ),
    # --- Disk statistics ---
    "disk_read_throughput": GraphMetricSeries(
        key="disk_read_throughput",
        label="Disk Read Throughput",
        unit="MB/s",
        color="dodger_blue2",
        category=SeriesCategory.DISK,
        source_path=("disk_io", "read_throughput"),
        scale=1 / 1024,
    ),
    "disk_write_throughput": GraphMetricSeries(
        key="disk_write_throughput",
        label="Disk Write Throughput",
        unit="MB/s",
        color="steel_blue",
        category=SeriesCategory.DISK,
        source_path=("disk_io", "write_throughput"),
        scale=1 / 1024,
    ),
    "disk_cache_hit_rate": GraphMetricSeries(
        key="disk_cache_hit_rate",
        label="Cache Hit Rate",
        unit="%",
        color="khaki1",
        category=SeriesCategory.DISK,
        source_path=("disk_io", "cache_hit_rate"),
    ),
    # --- Transfer cap / historical usage ---
    "transfer_cap_utilization": GraphMetricSeries(
        key="transfer_cap_utilization",
        label="Transfer Cap Utilization",
        unit="%",
        color="purple",
        category=SeriesCategory.TRANSFER,
        source_path=("transfer", "cap_utilization"),
    ),
    "historical_download_usage": GraphMetricSeries(
        key="historical_download_usage",
        label="Historical Download",
        unit="GiB",
        color="deep_sky_blue1",
        category=SeriesCategory.TRANSFER,
        source_path=("transfer", "historical_download_gib"),
    ),
    "historical_upload_usage": GraphMetricSeries(
        key="historical_upload_usage",
        label="Historical Upload",
        unit="GiB",
        color="light_salmon1",
        category=SeriesCategory.TRANSFER,
        source_path=("transfer", "historical_upload_gib"),
    ),
    # --- Network overhead / timing ---
    "network_overhead_rate": GraphMetricSeries(
        key="network_overhead_rate",
        label="Network Overhead",
        color="light_slate_blue",
        category=SeriesCategory.NETWORK,
        source_path=("network", "overhead_rate"),
    ),
    "utp_delay_ms": GraphMetricSeries(
        key="utp_delay_ms",
        label="uTP Delay",
        unit="ms",
        color="light_steel_blue",
        category=SeriesCategory.NETWORK,
        source_path=("network", "utp_delay_ms"),
    ),
    "disk_timing_ms": GraphMetricSeries(
        key="disk_timing_ms",
        label="Disk Timing",
        unit="ms",
        color="turquoise2",
        category=SeriesCategory.SYSTEM,
        source_path=("disk_io", "timing_ms"),
    ),
    # --- Per-Torrent Series ---
    "torrent_upload_rate": GraphMetricSeries(
        key="torrent_upload_rate",
        label="Torrent Upload Rate",
        color="yellow",
        description="Upload rate for a specific torrent",
        source_path=("torrent_stats", "upload_rate"),
    ),
    "torrent_download_rate": GraphMetricSeries(
        key="torrent_download_rate",
        label="Torrent Download Rate",
        color="bright_green",
        description="Download rate for a specific torrent",
        source_path=("torrent_stats", "download_rate"),
    ),
    "torrent_progress": GraphMetricSeries(
        key="torrent_progress",
        label="Torrent Progress",
        unit="%",
        color="cyan",
        category=SeriesCategory.TRANSFER,
        description="Download progress percentage",
        source_path=("torrent_stats", "progress"),
        scale=100.0,  # Convert 0-1 to 0-100
    ),
    "torrent_peers_connected": GraphMetricSeries(
        key="torrent_peers_connected",
        label="Connected Peers",
        unit="",
        color="bright_blue",
        category=SeriesCategory.NETWORK,
        description="Number of connected peers",
        source_path=("torrent_stats", "num_peers"),
    ),
    "torrent_seeds_connected": GraphMetricSeries(
        key="torrent_seeds_connected",
        label="Connected Seeds",
        unit="",
        color="bright_cyan",
        category=SeriesCategory.NETWORK,
        description="Number of connected seeds",
        source_path=("torrent_stats", "num_seeds"),
    ),
    "torrent_piece_download_rate": GraphMetricSeries(
        key="torrent_piece_download_rate",
        label="Piece Download Rate",
        color="lime",
        category=SeriesCategory.SPEED,
        description="Rate at which pieces are being downloaded",
        source_path=("torrent_stats", "piece_download_rate"),
    ),
    "torrent_swarm_availability": GraphMetricSeries(
        key="torrent_swarm_availability",
        label="Swarm Availability",
        unit="%",
        color="magenta",
        category=SeriesCategory.NETWORK,
        description="Percentage of pieces available in swarm",
        source_path=("torrent_stats", "swarm_availability"),
        scale=100.0,
    ),
}


def list_series(keys: Iterable[str]) -> List[GraphMetricSeries]:
    """Return series metadata for the requested keys.

    Unknown keys are ignored to keep the API forgiving.
    """

    return [SERIES_REGISTRY[key] for key in keys if key in SERIES_REGISTRY]


def list_series_by_category(category: SeriesCategory) -> List[GraphMetricSeries]:
    """Iterate all series in a category."""

    return [series for series in SERIES_REGISTRY.values() if series.category == category]


# ============================================================================
# Series Presets (Predefined Groups)
# ============================================================================


@dataclass(frozen=True)
class SeriesPreset:
    """Predefined group of series for common graph views."""

    key: str
    label: str
    description: str
    series_keys: Tuple[str, ...]
    default_resolution: str = "1s"


PRESETS: Dict[str, SeriesPreset] = {
    "upload_download": SeriesPreset(
        key="upload_download",
        label="Upload & Download",
        description="Upload and download rates with limits",
        series_keys=(
            "upload_rate_payload",
            "download_rate_payload",
            "upload_rate_limit",
            "download_rate_limit",
        ),
    ),
    "disk_statistics": SeriesPreset(
        key="disk_statistics",
        label="Disk Statistics",
        description="Disk I/O throughput and cache performance",
        series_keys=(
            "disk_read_throughput",
            "disk_write_throughput",
            "disk_cache_hit_rate",
        ),
    ),
    "network_overhead": SeriesPreset(
        key="network_overhead",
        label="Network Overhead",
        description="Network overhead and uTP delay metrics",
        series_keys=(
            "network_overhead_rate",
            "utp_delay_ms",
            "disk_timing_ms",
        ),
    ),
    "transfer_cap": SeriesPreset(
        key="transfer_cap",
        label="Transfer Cap & Usage",
        description="Transfer cap utilization and historical usage",
        series_keys=(
            "transfer_cap_utilization",
            "historical_download_usage",
            "historical_upload_usage",
        ),
    ),
    "all_speeds": SeriesPreset(
        key="all_speeds",
        label="All Speed Metrics",
        description="All upload/download rate variants",
        series_keys=(
            "upload_rate_payload",
            "download_rate_payload",
            "upload_rate_local",
            "download_rate_local",
            "upload_rate_overhead",
            "download_rate_overhead",
            "send_rate_player",
        ),
    ),
}


def get_preset(preset_key: str) -> Optional[SeriesPreset]:
    """Get a series preset by key."""
    return PRESETS.get(preset_key)


def list_presets() -> List[SeriesPreset]:
    """List all available presets."""
    return list(PRESETS.values())


# ============================================================================
# Data Extraction Helpers
# ============================================================================


def extract_series_value(data: Dict[str, Any], series: GraphMetricSeries) -> Optional[float]:
    """Extract a metric value from nested data using series source_path.

    Args:
        data: Nested dictionary containing metrics
        series: Series definition with source_path

    Returns:
        Extracted value (scaled) or None if path not found
    """
    try:
        value = data
        for key in series.source_path:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
            if value is None:
                return None

        if not isinstance(value, (int, float)):
            return None

        # Apply scale factor
        return float(value) * series.scale
    except (KeyError, TypeError, ValueError):
        return None


def extract_multiple_series_values(
    data: Dict[str, Any], series_list: List[GraphMetricSeries]
) -> Dict[str, Optional[float]]:
    """Extract values for multiple series from data.

    Args:
        data: Nested dictionary containing metrics
        series_list: List of series to extract

    Returns:
        Dictionary mapping series keys to values (or None if not found)
    """
    return {series.key: extract_series_value(data, series) for series in series_list}


# ============================================================================
# Per-Torrent Series Variants
# ============================================================================


def get_per_torrent_series_key(global_key: str) -> Optional[str]:
    """Get per-torrent variant key for a global series key.

    Args:
        global_key: Global series key (e.g., "upload_rate_payload")

    Returns:
        Per-torrent key (e.g., "torrent_upload_rate_payload") or None if no variant
    """
    # Map global keys to per-torrent variants
    per_torrent_mapping: Dict[str, str] = {
        "upload_rate_payload": "torrent_upload_rate",
        "download_rate_payload": "torrent_download_rate",
        "upload_rate_local": "torrent_upload_rate_local",
        "download_rate_local": "torrent_download_rate_local",
    }
    return per_torrent_mapping.get(global_key)


def create_per_torrent_series(global_series: GraphMetricSeries, info_hash: str) -> GraphMetricSeries:
    """Create a per-torrent variant of a global series.

    Args:
        global_series: Global series definition
        info_hash: Torrent info hash for scoping

    Returns:
        New series definition scoped to the torrent
    """
    per_torrent_key = get_per_torrent_series_key(global_series.key) or f"torrent_{global_series.key}"
    # Update source_path to include torrent scope
    new_path = ("torrents", info_hash) + global_series.source_path[1:]
    return GraphMetricSeries(
        key=per_torrent_key,
        label=f"{global_series.label} (Torrent)",
        unit=global_series.unit,
        color=global_series.color,
        style=global_series.style,
        description=global_series.description,
        category=global_series.category,
        source_path=new_path,
        scale=global_series.scale,
    )


# ============================================================================
# Series Validation & Compatibility
# ============================================================================


def validate_series_keys(keys: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Validate series keys and return valid/invalid lists.

    Args:
        keys: Iterable of series keys to validate

    Returns:
        Tuple of (valid_keys, invalid_keys)
    """
    key_list = list(keys)
    valid = [k for k in key_list if k in SERIES_REGISTRY]
    invalid = [k for k in key_list if k not in SERIES_REGISTRY]
    return (valid, invalid)


def are_series_compatible(series_list: List[GraphMetricSeries]) -> bool:
    """Check if multiple series can be displayed together on the same graph.

    Args:
        series_list: List of series to check

    Returns:
        True if compatible (same units/category), False otherwise
    """
    if not series_list:
        return True

    # Check if all have same unit (required for same Y-axis)
    first_unit = series_list[0].unit
    if not all(s.unit == first_unit for s in series_list):
        return False

    # Check if all have same category (recommended but not required)
    first_category = series_list[0].category
    if not all(s.category == first_category for s in series_list):
        # Allow mixing if units match (e.g., different speed types)
        pass

    return True


def group_series_by_unit(series_list: List[GraphMetricSeries]) -> Dict[str, List[GraphMetricSeries]]:
    """Group series by their unit for multi-axis graphs.

    Args:
        series_list: List of series to group

    Returns:
        Dictionary mapping units to series lists
    """
    groups: Dict[str, List[GraphMetricSeries]] = {}
    for series in series_list:
        unit = series.unit
        if unit not in groups:
            groups[unit] = []
        groups[unit].append(series)
    return groups


# ============================================================================
# Series Configuration Export/Import
# ============================================================================


@dataclass
class SeriesConfiguration:
    """Configuration for a graph with multiple series."""

    name: str
    series_keys: List[str]
    resolution: str = "1s"
    max_samples: int = 120
    preset_key: Optional[str] = None


def export_configuration(config: SeriesConfiguration) -> Dict[str, Any]:
    """Export a series configuration to a dictionary.

    Args:
        config: Configuration to export

    Returns:
        Dictionary representation
    """
    return {
        "name": config.name,
        "series_keys": config.series_keys,
        "resolution": config.resolution,
        "max_samples": config.max_samples,
        "preset_key": config.preset_key,
    }


def import_configuration(data: Dict[str, Any]) -> SeriesConfiguration:
    """Import a series configuration from a dictionary.

    Args:
        data: Dictionary representation

    Returns:
        SeriesConfiguration object
    """
    return SeriesConfiguration(
        name=data.get("name", "Custom Graph"),
        series_keys=data.get("series_keys", []),
        resolution=data.get("resolution", "1s"),
        max_samples=data.get("max_samples", 120),
        preset_key=data.get("preset_key"),
    )


# ============================================================================
# Series Metadata for UI
# ============================================================================


def get_series_display_info(series: GraphMetricSeries) -> Dict[str, Any]:
    """Get display metadata for a series (for UI rendering).

    Args:
        series: Series definition

    Returns:
        Dictionary with display information
    """
    return {
        "key": series.key,
        "label": series.label,
        "unit": series.unit,
        "color": series.color,
        "style": series.style,
        "description": series.description,
        "category": series.category.value,
    }


def format_series_value(value: Optional[float], series: GraphMetricSeries) -> str:
    """Format a series value for display.

    Args:
        value: Value to format (or None)
        series: Series definition

    Returns:
        Formatted string (e.g., "1.5 KiB/s" or "N/A")
    """
    if value is None:
        return "N/A"

    if series.unit == "%":
        return f"{value:.1f}%"
    elif series.unit == "ms":
        return f"{value:.1f} ms"
    elif series.unit in ("KiB/s", "MB/s", "GiB"):
        if value >= 1024 and series.unit == "KiB/s":
            return f"{value / 1024:.2f} MB/s"
        elif value >= 1024 and series.unit == "MB/s":
            return f"{value / 1024:.2f} GB/s"
        elif value >= 1024 and series.unit == "GiB":
            return f"{value / 1024:.2f} TiB"
        else:
            return f"{value:.2f} {series.unit}"
    else:
        return f"{value:.2f} {series.unit}"
