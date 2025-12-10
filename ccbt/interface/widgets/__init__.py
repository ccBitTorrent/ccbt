"""Widget components for the terminal dashboard."""

from __future__ import annotations

from ccbt.interface.widgets.core_widgets import (
    GlobalTorrentMetricsPanel,
    GraphsSectionContainer,
    Overview,
    PeersTable,
    QuickStatsPanel,
    SpeedSparklines,
    SummaryCards,
    SwarmHotspotsTable,
    TorrentsTable,
)
from ccbt.interface.widgets.config_wrapper import ConfigScreenWrapper
from ccbt.interface.widgets.file_browser import FileBrowserWidget
from ccbt.interface.widgets.dht_health_widget import DHTHealthWidget
from ccbt.interface.widgets.graph_widget import (
    BaseGraphWidget,
    PeerQualitySummaryWidget,
    SwarmHealthDotPlot,
    UploadDownloadGraphWidget,
)
from ccbt.interface.widgets.monitoring_wrapper import MonitoringScreenWrapper
from ccbt.interface.widgets.torrent_controls import TorrentControlsWidget
from ccbt.interface.widgets.reusable_table import ReusableDataTable
from ccbt.interface.widgets.tabbed_interface import MainTabsContainer
from ccbt.interface.widgets.torrent_selector import TorrentSelector
from ccbt.interface.widgets.language_selector import LanguageSelectorWidget
from ccbt.interface.widgets.piece_availability_bar import PieceAvailabilityHealthBar
from ccbt.interface.widgets.peer_quality_distribution_widget import (
    PeerQualityDistributionWidget,
)
from ccbt.interface.widgets.global_kpis_panel import GlobalKPIsPanel
from ccbt.interface.widgets.swarm_timeline_widget import SwarmTimelineWidget
from ccbt.interface.widgets.piece_selection_widget import PieceSelectionStrategyWidget
from ccbt.interface.widgets.reusable_widgets import (
    MetricsTableWidget,
    ProgressBarWidget,
    SparklineGroup,
)

__all__ = [
    "BaseGraphWidget",
    "ConfigScreenWrapper",
    "FileBrowserWidget",
    "DHTHealthWidget",
    "GlobalTorrentMetricsPanel",
    "GraphsSectionContainer",
    "MainTabsContainer",
    "MetricsTableWidget",
    "MonitoringScreenWrapper",
    "Overview",
    "PeersTable",
    "PieceAvailabilityHealthBar",
    "PeerQualityDistributionWidget",
    "GlobalKPIsPanel",
    "ProgressBarWidget",
    "QuickStatsPanel",
    "ReusableDataTable",
    "SparklineGroup",
    "SwarmHealthDotPlot",
    "SwarmHotspotsTable",
    "PieceSelectionStrategyWidget",
    "SwarmTimelineWidget",
    "SpeedSparklines",
    "SummaryCards",
    "TorrentControlsWidget",
    "TorrentSelector",
    "TorrentsTable",
    "UploadDownloadGraphWidget",
    "PeerQualitySummaryWidget",
    "LanguageSelectorWidget",
]
