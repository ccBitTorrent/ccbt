"""Machine Learning module for ccBitTorrent.

from __future__ import annotations

Provides ML-based optimizations including:
- Peer quality prediction
- Piece selection optimization
- Anomaly detection
- Adaptive rate limiting
"""

from ccbt.ml.adaptive_limiter import AdaptiveLimiter

# from ccbt.ml.anomaly_detector import MLAnomalyDetector  # Module doesn't exist yet
from ccbt.ml.peer_selector import PeerSelector
from ccbt.ml.piece_predictor import PiecePredictor

__all__ = [
    "AdaptiveLimiter",
    # "MLAnomalyDetector",  # Module doesn't exist yet
    "PeerSelector",
    "PiecePredictor",
]
