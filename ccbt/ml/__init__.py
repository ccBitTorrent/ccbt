"""Machine Learning module for ccBitTorrent.

Provides ML-based optimizations including:
- Peer quality prediction
- Piece selection optimization
- Anomaly detection
- Adaptive rate limiting
"""

from __future__ import annotations

from ccbt.ml.adaptive_limiter import AdaptiveLimiter

# from ccbt.ml.anomaly_detector import MLAnomalyDetector  # Module doesn't exist yet
from ccbt.ml.peer_selector import (
    PeerSelector,
    peer_selector_cache_key,
    peer_selector_cache_key_for_piece_peer_key,
)
from ccbt.ml.piece_predictor import PiecePredictor

# MLAnomalyDetector module doesn't exist yet — not exported.
__all__ = [
    "AdaptiveLimiter",
    "PeerSelector",
    "PiecePredictor",
    "peer_selector_cache_key",
    "peer_selector_cache_key_for_piece_peer_key",
]
