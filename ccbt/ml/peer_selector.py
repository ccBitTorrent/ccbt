"""ML-based Peer Selector for ccBitTorrent.

Provides intelligent peer selection using machine learning:
- Peer quality prediction
- Feature extraction from peer behavior
- Online learning for adaptation
- Performance-based ranking
"""

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..events import Event, EventType, emit_event
from ..models import PeerInfo


class PeerQuality(Enum):
    """Peer quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    BAD = "bad"


@dataclass
class PeerFeatures:
    """Features extracted from peer behavior."""
    peer_id: str
    ip: str

    # Connection features
    connection_count: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    avg_connection_duration: float = 0.0

    # Performance features
    avg_download_speed: float = 0.0
    avg_upload_speed: float = 0.0
    bytes_sent: int = 0
    bytes_received: int = 0

    # Reliability features
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    response_time: float = 0.0

    # Behavioral features
    message_frequency: float = 0.0
    request_pattern: str = "unknown"
    piece_selection_strategy: str = "unknown"

    # Network features
    latency: float = 0.0
    bandwidth: float = 0.0
    packet_loss: float = 0.0

    # Temporal features
    first_seen: float = 0.0
    last_seen: float = 0.0
    activity_duration: float = 0.0

    # Quality score
    quality_score: float = 0.5
    confidence: float = 0.0


@dataclass
class PeerPrediction:
    """Peer quality prediction."""
    peer_id: str
    predicted_quality: PeerQuality
    confidence: float
    features: PeerFeatures
    prediction_time: float


class PeerSelector:
    """ML-based peer selector."""

    def __init__(self):
        self.peer_features: Dict[str, PeerFeatures] = {}
        self.quality_models: Dict[str, Any] = {}
        self.feature_weights: Dict[str, float] = {}

        # Initialize feature weights
        self._initialize_feature_weights()

        # Learning parameters
        self.learning_rate = 0.01
        self.min_samples = 10
        self.max_samples = 1000

        # Performance tracking
        self.performance_history: Dict[str, List[float]] = defaultdict(list)
        self.prediction_accuracy: Dict[str, List[bool]] = defaultdict(list)

        # Statistics
        self.stats = {
            "total_predictions": 0,
            "accurate_predictions": 0,
            "peer_rankings": 0,
            "feature_extractions": 0,
        }

    async def predict_peer_quality(self, peer_info: PeerInfo) -> PeerPrediction:
        """Predict peer quality using ML.
        
        Args:
            peer_info: Peer information
            
        Returns:
            Peer quality prediction
        """
        peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""

        # Extract features
        features = await self._extract_features(peer_id, peer_info)

        # Predict quality
        predicted_quality, confidence = await self._predict_quality(features)

        # Update features
        self.peer_features[peer_id] = features

        # Create prediction
        prediction = PeerPrediction(
            peer_id=peer_id,
            predicted_quality=predicted_quality,
            confidence=confidence,
            features=features,
            prediction_time=time.time(),
        )

        # Update statistics
        self.stats["total_predictions"] += 1

        # Emit prediction event
        await emit_event(Event(
            event_type=EventType.ML_PEER_PREDICTION.value,
            data={
                "peer_id": peer_id,
                "predicted_quality": predicted_quality.value,
                "confidence": confidence,
                "features": {
                    "connection_count": features.connection_count,
                    "avg_download_speed": features.avg_download_speed,
                    "error_rate": features.error_rate,
                    "latency": features.latency,
                },
                "timestamp": time.time(),
            },
        ))

        return prediction

    async def rank_peers(self, peers: List[PeerInfo]) -> List[Tuple[PeerInfo, float]]:
        """Rank peers by predicted quality.
        
        Args:
            peers: List of peers to rank
            
        Returns:
            List of (peer, score) tuples sorted by score
        """
        peer_scores = []

        for peer_info in peers:
            peer_id = peer_info.peer_id.hex() if peer_info.peer_id else ""

            # Get or predict quality
            if peer_id in self.peer_features:
                features = self.peer_features[peer_id]
                score = features.quality_score
            else:
                prediction = await self.predict_peer_quality(peer_info)
                score = self._quality_to_score(prediction.predicted_quality)

            peer_scores.append((peer_info, score))

        # Sort by score (descending)
        peer_scores.sort(key=lambda x: x[1], reverse=True)

        # Update statistics
        self.stats["peer_rankings"] += 1

        return peer_scores

    async def update_peer_performance(self, peer_id: str, performance_data: Dict[str, Any]) -> None:
        """Update peer performance data for learning.
        
        Args:
            peer_id: Peer identifier
            performance_data: Performance metrics
        """
        if peer_id not in self.peer_features:
            return

        features = self.peer_features[peer_id]

        # Update features with new data
        await self._update_features(features, performance_data)

        # Record performance for learning
        self.performance_history[peer_id].append(performance_data.get("quality_score", 0.5))

        # Update prediction accuracy
        if "actual_quality" in performance_data:
            predicted_quality = features.quality_score
            actual_quality = performance_data["actual_quality"]

            # Check if prediction was accurate
            accuracy = abs(predicted_quality - actual_quality) < 0.2
            self.prediction_accuracy[peer_id].append(accuracy)

            if accuracy:
                self.stats["accurate_predictions"] += 1

        # Trigger online learning
        await self._online_learning(peer_id, performance_data)

    async def get_best_peers(self, peers: List[PeerInfo], count: int = 10) -> List[PeerInfo]:
        """Get the best peers based on ML predictions.
        
        Args:
            peers: List of available peers
            count: Number of best peers to return
            
        Returns:
            List of best peers
        """
        # Rank all peers
        ranked_peers = await self.rank_peers(peers)

        # Return top N peers
        best_peers = [peer for peer, _ in ranked_peers[:count]]

        return best_peers

    def get_peer_features(self, peer_id: str) -> Optional[PeerFeatures]:
        """Get features for a specific peer."""
        return self.peer_features.get(peer_id)

    def get_all_peer_features(self) -> Dict[str, PeerFeatures]:
        """Get features for all peers."""
        return self.peer_features.copy()

    def get_ml_statistics(self) -> Dict[str, Any]:
        """Get ML statistics."""
        total_predictions = self.stats["total_predictions"]
        accurate_predictions = self.stats["accurate_predictions"]

        accuracy = accurate_predictions / max(1, total_predictions)

        return {
            "total_predictions": total_predictions,
            "accurate_predictions": accurate_predictions,
            "prediction_accuracy": accuracy,
            "peer_rankings": self.stats["peer_rankings"],
            "feature_extractions": self.stats["feature_extractions"],
            "tracked_peers": len(self.peer_features),
            "feature_weights": self.feature_weights.copy(),
        }

    def cleanup_old_data(self, max_age_seconds: int = 3600) -> None:
        """Clean up old ML data."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up old peer features
        to_remove = []
        for peer_id, features in self.peer_features.items():
            if features.last_seen < cutoff_time:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            del self.peer_features[peer_id]

        # Clean up old performance history
        for peer_id in list(self.performance_history.keys()):
            if peer_id not in self.peer_features:
                del self.performance_history[peer_id]

    async def _extract_features(self, peer_id: str, peer_info: PeerInfo) -> PeerFeatures:
        """Extract features from peer information."""
        current_time = time.time()

        # Initialize features
        features = PeerFeatures(
            peer_id=peer_id,
            ip=peer_info.ip,
            first_seen=current_time,
            last_seen=current_time,
        )

        # Extract basic features
        features.connection_count = 1
        features.successful_connections = 1

        # Estimate network features
        features.latency = await self._estimate_latency(peer_info.ip)
        features.bandwidth = await self._estimate_bandwidth(peer_info.ip)

        # Set default values
        features.avg_download_speed = 1000.0  # 1KB/s default
        features.avg_upload_speed = 500.0  # 500B/s default
        features.error_rate = 0.0
        features.timeout_rate = 0.0
        features.response_time = 1.0
        features.message_frequency = 1.0
        features.request_pattern = "sequential"
        features.piece_selection_strategy = "rarest_first"

        # Calculate quality score
        features.quality_score = await self._calculate_quality_score(features)
        features.confidence = 0.5  # Default confidence

        # Update statistics
        self.stats["feature_extractions"] += 1

        return features

    async def _predict_quality(self, features: PeerFeatures) -> Tuple[PeerQuality, float]:
        """Predict peer quality using ML model."""
        # This is a simplified prediction
        # In a real implementation, this would use a trained ML model

        # Calculate quality score based on features
        quality_score = features.quality_score

        # Determine quality level
        if quality_score >= 0.8:
            predicted_quality = PeerQuality.EXCELLENT
            confidence = 0.9
        elif quality_score >= 0.6:
            predicted_quality = PeerQuality.GOOD
            confidence = 0.8
        elif quality_score >= 0.4:
            predicted_quality = PeerQuality.AVERAGE
            confidence = 0.7
        elif quality_score >= 0.2:
            predicted_quality = PeerQuality.POOR
            confidence = 0.6
        else:
            predicted_quality = PeerQuality.BAD
            confidence = 0.5

        return predicted_quality, confidence

    async def _update_features(self, features: PeerFeatures, performance_data: Dict[str, Any]) -> None:
        """Update features with new performance data."""
        current_time = time.time()

        # Update connection features
        if "connection_success" in performance_data:
            if performance_data["connection_success"]:
                features.successful_connections += 1
            else:
                features.failed_connections += 1

        # Update performance features
        if "download_speed" in performance_data:
            features.avg_download_speed = self._update_average(
                features.avg_download_speed,
                performance_data["download_speed"],
            )

        if "upload_speed" in performance_data:
            features.avg_upload_speed = self._update_average(
                features.avg_upload_speed,
                performance_data["upload_speed"],
            )

        # Update reliability features
        if "error_count" in performance_data:
            total_messages = features.connection_count + features.successful_connections
            if total_messages > 0:
                features.error_rate = performance_data["error_count"] / total_messages

        if "response_time" in performance_data:
            features.response_time = self._update_average(
                features.response_time,
                performance_data["response_time"],
            )

        # Update temporal features
        features.last_seen = current_time
        features.activity_duration = current_time - features.first_seen

        # Recalculate quality score
        features.quality_score = await self._calculate_quality_score(features)

    async def _calculate_quality_score(self, features: PeerFeatures) -> float:
        """Calculate quality score from features."""
        # Weighted combination of features
        score = 0.0

        # Connection reliability (30%)
        if features.connection_count > 0:
            success_rate = features.successful_connections / features.connection_count
            score += success_rate * 0.3

        # Performance (25%)
        # Normalize download speed (assume max 10MB/s)
        normalized_speed = min(1.0, features.avg_download_speed / (10 * 1024 * 1024))
        score += normalized_speed * 0.25

        # Reliability (20%)
        reliability = 1.0 - features.error_rate
        score += reliability * 0.2

        # Network quality (15%)
        # Lower latency is better
        latency_score = max(0.0, 1.0 - (features.latency / 1000.0))  # Assume max 1s latency
        score += latency_score * 0.15

        # Activity (10%)
        # More activity is better
        activity_score = min(1.0, features.activity_duration / 3600.0)  # Normalize to 1 hour
        score += activity_score * 0.1

        return max(0.0, min(1.0, score))

    def _quality_to_score(self, quality: PeerQuality) -> float:
        """Convert quality enum to numeric score."""
        quality_scores = {
            PeerQuality.EXCELLENT: 0.9,
            PeerQuality.GOOD: 0.7,
            PeerQuality.AVERAGE: 0.5,
            PeerQuality.POOR: 0.3,
            PeerQuality.BAD: 0.1,
        }
        return quality_scores.get(quality, 0.5)

    def _update_average(self, current_avg: float, new_value: float) -> float:
        """Update running average."""
        # Simple exponential moving average
        alpha = 0.1
        return alpha * new_value + (1 - alpha) * current_avg

    async def _estimate_latency(self, ip: str) -> float:
        """Estimate network latency to peer."""
        # This is a placeholder implementation
        # In a real implementation, this would ping the peer

        # For now, return a random latency between 10ms and 500ms
        import random
        return random.uniform(0.01, 0.5)

    async def _estimate_bandwidth(self, ip: str) -> float:
        """Estimate available bandwidth to peer."""
        # This is a placeholder implementation
        # In a real implementation, this would measure bandwidth

        # For now, return a random bandwidth between 100KB/s and 10MB/s
        import random
        return random.uniform(100 * 1024, 10 * 1024 * 1024)

    async def _online_learning(self, peer_id: str, performance_data: Dict[str, Any]) -> None:
        """Perform online learning to improve predictions."""
        if peer_id not in self.performance_history:
            return

        if len(self.performance_history[peer_id]) < self.min_samples:
            return

        # Get recent performance data
        recent_performance = self.performance_history[peer_id][-self.min_samples:]

        # Calculate performance trend
        if len(recent_performance) >= 2:
            trend = statistics.mean(recent_performance[-5:]) - statistics.mean(recent_performance[-10:-5])

            # Adjust feature weights based on performance
            if trend > 0.1:  # Performance improving
                self._adjust_weights_positive(peer_id)
            elif trend < -0.1:  # Performance degrading
                self._adjust_weights_negative(peer_id)

    def _adjust_weights_positive(self, peer_id: str) -> None:
        """Adjust weights positively for good performance."""
        # Increase weights for features that correlate with good performance
        for feature in ["avg_download_speed", "successful_connections", "response_time"]:
            if feature in self.feature_weights:
                self.feature_weights[feature] = min(1.0, self.feature_weights[feature] + 0.01)

    def _adjust_weights_negative(self, peer_id: str) -> None:
        """Adjust weights negatively for poor performance."""
        # Decrease weights for features that correlate with poor performance
        for feature in ["error_rate", "timeout_rate", "latency"]:
            if feature in self.feature_weights:
                self.feature_weights[feature] = max(0.0, self.feature_weights[feature] - 0.01)

    def _initialize_feature_weights(self) -> None:
        """Initialize feature weights."""
        self.feature_weights = {
            "connection_count": 0.1,
            "successful_connections": 0.2,
            "avg_download_speed": 0.3,
            "avg_upload_speed": 0.2,
            "error_rate": -0.2,
            "timeout_rate": -0.1,
            "response_time": -0.1,
            "latency": -0.1,
            "bandwidth": 0.2,
            "activity_duration": 0.1,
        }
