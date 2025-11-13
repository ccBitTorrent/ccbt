"""ML-based Piece Predictor for ccBitTorrent.

from __future__ import annotations

Provides intelligent piece selection using machine learning:
- Predictive piece selection
- Download pattern analysis
- Piece priority optimization
- Completion time prediction
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ccbt.utils.events import Event, EventType, emit_event


class PiecePriority(Enum):
    """Piece priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class PieceStatus(Enum):
    """Piece status."""

    MISSING = "missing"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PieceInfo:
    """Piece information."""

    piece_index: int
    size: int
    hash: bytes
    status: PieceStatus = PieceStatus.MISSING
    priority: PiecePriority = PiecePriority.MEDIUM
    download_start_time: float = 0.0
    download_complete_time: float = 0.0
    download_duration: float = 0.0
    download_speed: float = 0.0
    retry_count: int = 0
    last_attempt: float = 0.0


@dataclass
class DownloadPattern:
    """Download pattern analysis."""

    piece_index: int
    download_times: list[float]
    download_speeds: list[float]
    success_rate: float
    avg_download_time: float
    pattern_type: str  # "sequential", "random", "rarest_first", "endgame"
    completion_probability: float


@dataclass
class PiecePrediction:
    """Piece download prediction."""

    piece_index: int
    predicted_download_time: float
    predicted_success_rate: float
    priority_score: float
    completion_probability: float
    confidence: float
    prediction_time: float


class PiecePredictor:
    """ML-based piece predictor."""

    def __init__(self):
        """Initialize ML-based piece predictor."""
        self.piece_info: dict[int, PieceInfo] = {}
        self.download_patterns: dict[int, DownloadPattern] = {}
        self.piece_features: dict[int, dict[str, float]] = {}

        # ML models
        self.download_time_model: dict[str, Any] = {}
        self.success_rate_model: dict[str, Any] = {}
        self.priority_model: dict[str, Any] = {}

        # Learning parameters
        self.learning_rate = 0.01
        self.min_samples = 5
        self.max_samples = 1000

        # Performance tracking
        self.performance_history: dict[int, list[float]] = defaultdict(list)
        self.prediction_accuracy: dict[int, list[bool]] = defaultdict(list)

        # Statistics
        self.stats = {
            "total_predictions": 0,
            "accurate_predictions": 0,
            "pieces_analyzed": 0,
            "patterns_learned": 0,
        }

    async def predict_piece_download_time(
        self,
        piece_index: int,
        piece_size: int,
    ) -> PiecePrediction:
        """Predict piece download time using ML.

        Args:
            piece_index: Piece index
            piece_size: Piece size in bytes

        Returns:
            Piece download prediction

        """
        # Extract features
        features = await self._extract_piece_features(piece_index, piece_size)

        # Predict download time
        predicted_time = await self._predict_download_time(features)

        # Predict success rate
        success_rate = await self._predict_success_rate(features)

        # Calculate priority score
        priority_score = await self._calculate_priority_score(features)

        # Calculate completion probability
        completion_prob = await self._calculate_completion_probability(features)

        # Create prediction
        prediction = PiecePrediction(
            piece_index=piece_index,
            predicted_download_time=predicted_time,
            predicted_success_rate=success_rate,
            priority_score=priority_score,
            completion_probability=completion_prob,
            confidence=0.8,  # Default confidence
            prediction_time=time.time(),
        )

        # Update statistics
        self.stats["total_predictions"] += 1

        # Emit prediction event
        await emit_event(
            Event(
                event_type=EventType.ML_PIECE_PREDICTION.value,
                data={
                    "piece_index": piece_index,
                    "predicted_download_time": predicted_time,
                    "predicted_success_rate": success_rate,
                    "priority_score": priority_score,
                    "completion_probability": completion_prob,
                    "features": features,
                    "timestamp": time.time(),
                },
            ),
        )

        return prediction

    async def select_optimal_pieces(
        self,
        available_pieces: list[int],
        count: int = 10,
    ) -> list[int]:
        """Select optimal pieces for download.

        Args:
            available_pieces: List of available piece indices
            count: Number of pieces to select

        Returns:
            List of optimal piece indices

        """
        piece_predictions = []

        for piece_index in available_pieces:
            # Get piece info
            piece_info = self.piece_info.get(piece_index)
            if not piece_info:
                continue

            # Predict piece performance
            prediction = await self.predict_piece_download_time(
                piece_index,
                piece_info.size,
            )
            piece_predictions.append((piece_index, prediction))

        # Sort by priority score
        piece_predictions.sort(key=lambda x: x[1].priority_score, reverse=True)

        # Select top pieces
        return [piece_index for piece_index, _ in piece_predictions[:count]]

    async def update_piece_performance(
        self,
        piece_index: int,
        performance_data: dict[str, Any],
    ) -> None:
        """Update piece performance data for learning.

        Args:
            piece_index: Piece index
            performance_data: Performance metrics

        """
        if piece_index not in self.piece_info:
            return

        piece_info = self.piece_info[piece_index]

        # Update piece info
        if "download_start_time" in performance_data:
            piece_info.download_start_time = performance_data["download_start_time"]

        if "download_complete_time" in performance_data:
            piece_info.download_complete_time = performance_data[
                "download_complete_time"
            ]
            piece_info.download_duration = (
                piece_info.download_complete_time - piece_info.download_start_time
            )

        if "download_speed" in performance_data:
            piece_info.download_speed = performance_data["download_speed"]

        if "success" in performance_data:
            if performance_data["success"]:
                piece_info.status = PieceStatus.COMPLETED
            else:
                piece_info.status = PieceStatus.FAILED
                piece_info.retry_count += 1

        # Update download pattern
        await self._update_download_pattern(piece_index, performance_data)

        # Record performance for learning
        self.performance_history[piece_index].append(
            performance_data.get("download_time", 0.0),
        )

        # Update prediction accuracy
        if "actual_download_time" in performance_data:
            predicted_time = performance_data.get("predicted_download_time", 0.0)
            actual_time = performance_data["actual_download_time"]

            # Check if prediction was accurate (within 20%)
            accuracy = abs(predicted_time - actual_time) / max(actual_time, 0.001) < 0.2
            self.prediction_accuracy[piece_index].append(accuracy)

            if accuracy:
                self.stats["accurate_predictions"] += 1

        # Trigger online learning
        await self._online_learning(piece_index, performance_data)

    async def analyze_download_patterns(self) -> dict[str, Any]:
        """Analyze download patterns across all pieces.

        Returns:
            Pattern analysis results

        """
        pattern_analysis: dict[str, Any] = {
            "total_pieces": len(self.piece_info),
            "completed_pieces": 0,
            "failed_pieces": 0,
            "avg_download_time": 0.0,
            "avg_download_speed": 0.0,
            "success_rate": 0.0,
            "pattern_types": defaultdict(int),
            "priority_distribution": defaultdict(int),
        }

        total_download_time = 0.0
        total_download_speed = 0.0
        total_successes = 0
        total_attempts = 0

        for piece_index, piece_info in self.piece_info.items():
            if piece_info.status == PieceStatus.COMPLETED:
                pattern_analysis["completed_pieces"] += 1
                total_successes += 1
            elif piece_info.status == PieceStatus.FAILED:
                pattern_analysis["failed_pieces"] += 1

            total_attempts += 1

            if piece_info.download_duration > 0:
                total_download_time += piece_info.download_duration
                total_download_speed += piece_info.download_speed

            # Analyze pattern type
            if piece_index in self.download_patterns:
                pattern = self.download_patterns[piece_index]
                pattern_analysis["pattern_types"][pattern.pattern_type] += 1

            # Analyze priority distribution
            pattern_analysis["priority_distribution"][piece_info.priority.value] += 1

        # Calculate averages
        completed_pieces = pattern_analysis["completed_pieces"]
        if completed_pieces > 0:
            pattern_analysis["avg_download_time"] = (
                total_download_time / completed_pieces
            )
            pattern_analysis["avg_download_speed"] = (
                total_download_speed / completed_pieces
            )

        if total_attempts > 0:
            pattern_analysis["success_rate"] = total_successes / total_attempts

        return pattern_analysis

    def get_piece_info(self, piece_index: int) -> PieceInfo | None:
        """Get piece information."""
        return self.piece_info.get(piece_index)

    def get_all_piece_info(self) -> dict[int, PieceInfo]:
        """Get all piece information."""
        return self.piece_info.copy()

    def get_download_pattern(self, piece_index: int) -> DownloadPattern | None:
        """Get download pattern for a piece."""
        return self.download_patterns.get(piece_index)

    def get_ml_statistics(self) -> dict[str, Any]:
        """Get ML statistics."""
        total_predictions = self.stats["total_predictions"]
        accurate_predictions = self.stats["accurate_predictions"]

        accuracy = accurate_predictions / max(1, total_predictions)

        return {
            "total_predictions": total_predictions,
            "accurate_predictions": accurate_predictions,
            "prediction_accuracy": accuracy,
            "pieces_analyzed": self.stats["pieces_analyzed"],
            "patterns_learned": self.stats["patterns_learned"],
            "tracked_pieces": len(self.piece_info),
        }

    def cleanup_old_data(self, max_age_seconds: int = 3600) -> None:
        """Clean up old ML data."""
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        # Clean up old piece info
        to_remove = []
        for piece_index, piece_info in self.piece_info.items():
            if piece_info.last_attempt < cutoff_time:
                to_remove.append(piece_index)

        for piece_index in to_remove:
            del self.piece_info[piece_index]

        # Clean up old performance history
        for piece_index in list(self.performance_history.keys()):
            if piece_index not in self.piece_info:
                del self.performance_history[piece_index]

    async def _extract_piece_features(
        self,
        piece_index: int,
        piece_size: int,
    ) -> dict[str, float]:
        """Extract features for piece prediction."""
        features = {
            "piece_index": float(piece_index),
            "piece_size": float(piece_size),
            "piece_priority": 0.5,  # Default priority
            "download_attempts": 0.0,
            "success_rate": 0.5,
            "avg_download_time": 0.0,
            "avg_download_speed": 0.0,
            "network_quality": 0.5,
            "peer_availability": 0.5,
            "piece_rarity": 0.5,
        }

        # Get piece info if available
        if piece_index in self.piece_info:
            piece_info = self.piece_info[piece_index]
            features["piece_priority"] = self._priority_to_score(piece_info.priority)
            features["download_attempts"] = float(piece_info.retry_count)
            features["avg_download_time"] = piece_info.download_duration
            features["avg_download_speed"] = piece_info.download_speed

        # Get download pattern if available
        if piece_index in self.download_patterns:
            pattern = self.download_patterns[piece_index]
            features["success_rate"] = pattern.success_rate
            features["avg_download_time"] = pattern.avg_download_time

        # Estimate network quality
        features["network_quality"] = await self._estimate_network_quality()

        # Estimate peer availability
        features["peer_availability"] = await self._estimate_peer_availability(
            piece_index,
        )

        # Estimate piece rarity
        features["piece_rarity"] = await self._estimate_piece_rarity(piece_index)

        return features

    async def _predict_download_time(self, features: dict[str, float]) -> float:
        """Predict piece download time using ML."""
        # This is a simplified prediction
        # In a real implementation, this would use a trained ML model

        # Base time calculation
        piece_size = features["piece_size"]
        network_quality = features["network_quality"]
        peer_availability = features["peer_availability"]

        # Estimate download time based on size and network quality
        base_time = piece_size / (1024 * 1024)  # Assume 1MB/s base speed
        quality_factor = 1.0 / max(0.1, network_quality)
        availability_factor = 1.0 / max(0.1, peer_availability)

        predicted_time = base_time * quality_factor * availability_factor

        return max(0.1, predicted_time)  # Minimum 0.1 seconds

    async def _predict_success_rate(self, features: dict[str, float]) -> float:
        """Predict piece download success rate."""
        # This is a simplified prediction
        # In a real implementation, this would use a trained ML model

        # Base success rate
        base_success_rate = 0.8

        # Adjust based on features
        network_quality = features["network_quality"]
        peer_availability = features["peer_availability"]
        piece_rarity = features["piece_rarity"]

        # Calculate success rate
        success_rate = (
            base_success_rate * network_quality * peer_availability * piece_rarity
        )

        return max(0.0, min(1.0, success_rate))

    async def _calculate_priority_score(self, features: dict[str, float]) -> float:
        """Calculate piece priority score."""
        # Weighted combination of features
        score = 0.0

        # Piece priority (40%)
        score += features["piece_priority"] * 0.4

        # Success rate (30%)
        score += features["success_rate"] * 0.3

        # Network quality (20%)
        score += features["network_quality"] * 0.2

        # Peer availability (10%)
        score += features["peer_availability"] * 0.1

        return max(0.0, min(1.0, score))

    async def _calculate_completion_probability(
        self,
        features: dict[str, float],
    ) -> float:
        """Calculate piece completion probability."""
        # This is a simplified calculation
        # In a real implementation, this would use a more sophisticated model

        # Base probability
        base_prob = 0.5

        # Adjust based on features
        network_quality = features["network_quality"]
        peer_availability = features["peer_availability"]
        success_rate = features["success_rate"]

        # Calculate completion probability
        completion_prob = base_prob * network_quality * peer_availability * success_rate

        return max(0.0, min(1.0, completion_prob))

    async def _update_download_pattern(
        self,
        piece_index: int,
        performance_data: dict[str, Any],
    ) -> None:
        """Update download pattern for a piece."""
        if piece_index not in self.download_patterns:
            self.download_patterns[piece_index] = DownloadPattern(
                piece_index=piece_index,
                download_times=[],
                download_speeds=[],
                success_rate=0.5,
                avg_download_time=0.0,
                pattern_type="unknown",
                completion_probability=0.5,
            )

        pattern = self.download_patterns[piece_index]

        # Update download times
        if "download_time" in performance_data:
            pattern.download_times.append(performance_data["download_time"])
            if len(pattern.download_times) > self.max_samples:
                pattern.download_times = pattern.download_times[-self.max_samples :]

        # Update download speeds
        if "download_speed" in performance_data:
            pattern.download_speeds.append(performance_data["download_speed"])
            if len(pattern.download_speeds) > self.max_samples:
                pattern.download_speeds = pattern.download_speeds[-self.max_samples :]

        # Update success rate
        if "success" in performance_data:
            # Calculate success rate from recent attempts
            recent_attempts = (
                pattern.download_times[-10:] if pattern.download_times else []
            )
            if recent_attempts:
                success_count = sum(
                    1 for _ in recent_attempts if performance_data["success"]
                )
                pattern.success_rate = success_count / len(recent_attempts)

        # Update average download time
        if pattern.download_times:
            pattern.avg_download_time = statistics.mean(pattern.download_times)

        # Determine pattern type
        pattern.pattern_type = await self._determine_pattern_type(piece_index)

        # Update completion probability
        pattern.completion_probability = await self._calculate_completion_probability(
            await self._extract_piece_features(piece_index, 0),
        )

    async def _determine_pattern_type(self, piece_index: int) -> str:
        """Determine download pattern type."""
        # This is a simplified pattern detection
        # In a real implementation, this would use more sophisticated analysis

        if piece_index in self.download_patterns:
            pattern = self.download_patterns[piece_index]

            # Analyze download times
            if len(pattern.download_times) >= 3:
                times = pattern.download_times
                if all(times[i] <= times[i + 1] for i in range(len(times) - 1)):
                    return "sequential"
                if all(times[i] >= times[i + 1] for i in range(len(times) - 1)):
                    return "reverse_sequential"
                return "random"

        return "unknown"

    async def _estimate_network_quality(self) -> float:
        """Estimate overall network quality."""
        # This is a placeholder implementation
        # In a real implementation, this would analyze network conditions

        return 0.7  # Default network quality

    async def _estimate_peer_availability(self, _piece_index: int) -> float:
        """Estimate peer availability for a piece."""
        # This is a placeholder implementation
        # In a real implementation, this would analyze peer availability

        return 0.8  # Default peer availability

    async def _estimate_piece_rarity(self, _piece_index: int) -> float:
        """Estimate piece rarity."""
        # This is a placeholder implementation
        # In a real implementation, this would analyze piece availability across peers

        return 0.6  # Default piece rarity

    def _priority_to_score(self, priority: PiecePriority) -> float:
        """Convert priority enum to numeric score."""
        priority_scores = {
            PiecePriority.CRITICAL: 1.0,
            PiecePriority.HIGH: 0.8,
            PiecePriority.MEDIUM: 0.6,
            PiecePriority.LOW: 0.4,
            PiecePriority.NONE: 0.2,
        }
        return priority_scores.get(priority, 0.5)

    async def _online_learning(
        self,
        piece_index: int,
        _performance_data: dict[str, Any],
    ) -> None:
        """Perform online learning to improve predictions."""
        if piece_index not in self.performance_history:
            return

        if len(self.performance_history[piece_index]) < self.min_samples:
            return

        # Get recent performance data
        recent_performance = self.performance_history[piece_index][-self.min_samples :]

        # Calculate performance trend
        if len(recent_performance) >= 2:
            trend = statistics.mean(recent_performance[-3:]) - statistics.mean(
                recent_performance[-6:-3],
            )

            # Adjust models based on performance
            if trend > 0.1:  # Performance improving
                self._adjust_models_positive(piece_index)
            elif trend < -0.1:  # Performance degrading
                self._adjust_models_negative(piece_index)

    def _adjust_models_positive(self, piece_index: int) -> None:
        """Adjust models positively for good performance."""
        # This is a placeholder for model adjustment
        # In a real implementation, this would update the ML models

    def _adjust_models_negative(self, piece_index: int) -> None:
        """Adjust models negatively for poor performance."""
        # This is a placeholder for model adjustment
        # In a real implementation, this would update the ML models
