"""Configuration screens package."""

from ccbt.interface.screens.config.global_config import (
    GlobalConfigDetailScreen,
    GlobalConfigMainScreen,
)
from ccbt.interface.screens.config.proxy import ProxyConfigScreen
from ccbt.interface.screens.config.ssl import SSLConfigScreen
from ccbt.interface.screens.config.torrent_config import (
    PerTorrentConfigMainScreen,
    TorrentConfigDetailScreen,
)
from ccbt.interface.screens.config.utp import UTPConfigScreen

__all__ = [
    "GlobalConfigDetailScreen",
    "GlobalConfigMainScreen",
    "PerTorrentConfigMainScreen",
    "ProxyConfigScreen",
    "SSLConfigScreen",
    "TorrentConfigDetailScreen",
    "UTPConfigScreen",
]

