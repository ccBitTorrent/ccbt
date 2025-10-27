"""Machine Learning module for ccBitTorrent.

Provides ML-based optimizations including:
- Peer quality prediction
- Piece selection optimization
- Anomaly detection
- Adaptive rate limiting
"""

from .adaptive_limiter import AdaptiveLimiter
from .anomaly_detector import MLAnomalyDetector
from .peer_selector import PeerSelector
from .piece_predictor import PiecePredictor

__all__ = [
    "AdaptiveLimiter",
    "MLAnomalyDetector",
    "PeerSelector",
    "PiecePredictor",
]
