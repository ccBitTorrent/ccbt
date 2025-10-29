"""Tests for ML piece predictor."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from ccbt.ml.piece_predictor import (
    DownloadPattern,
    PieceInfo,
    PiecePrediction,
    PiecePredictor,
    PiecePriority,
    PieceStatus,
)


class TestPiecePredictor:
    """Test cases for PiecePredictor."""

    @pytest.fixture
    def predictor(self):
        """Create a PiecePredictor instance."""
        return PiecePredictor()

    @pytest.fixture
    def sample_piece_info(self):
        """Create sample piece info."""
        return PieceInfo(
            piece_index=0,
            size=16384,
            hash=b"piece_hash_123456789",
            status=PieceStatus.MISSING,
            priority=PiecePriority.MEDIUM,
        )

    @pytest.mark.asyncio
    async def test_predict_piece_download_time(self, predictor):
        """Test piece download time prediction."""
        piece_index = 0
        piece_size = 16384
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock), \
             patch.object(predictor, '_extract_piece_features', return_value={
                 "piece_size": float(piece_size),
                 "network_quality": 0.8,
                 "peer_availability": 0.7,
                 "piece_rarity": 0.6,
                 "success_rate": 0.9,
                 "piece_priority": 0.5,
             }), \
             patch.object(predictor, '_predict_download_time', return_value=2.0), \
             patch.object(predictor, '_predict_success_rate', return_value=0.9), \
             patch.object(predictor, '_calculate_priority_score', return_value=0.7), \
             patch.object(predictor, '_calculate_completion_probability', return_value=0.8):
            
            prediction = await predictor.predict_piece_download_time(piece_index, piece_size)
        
        assert isinstance(prediction, PiecePrediction)
        assert prediction.piece_index == piece_index
        assert prediction.predicted_download_time == 2.0
        assert prediction.predicted_success_rate == 0.9
        assert prediction.priority_score == 0.7
        assert prediction.completion_probability == 0.8
        assert prediction.confidence == 0.8

    @pytest.mark.asyncio
    async def test_select_optimal_pieces_empty_list(self, predictor):
        """Test selecting optimal pieces from empty list."""
        result = await predictor.select_optimal_pieces([], count=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_select_optimal_pieces_no_piece_info(self, predictor):
        """Test selecting optimal pieces when piece info doesn't exist."""
        result = await predictor.select_optimal_pieces([0, 1, 2], count=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_select_optimal_pieces_with_piece_info(self, predictor, sample_piece_info):
        """Test selecting optimal pieces with existing piece info."""
        predictor.piece_info[0] = sample_piece_info
        
        with patch.object(predictor, 'predict_piece_download_time', return_value=PiecePrediction(
            piece_index=0,
            predicted_download_time=2.0,
            predicted_success_rate=0.9,
            priority_score=0.7,
            completion_probability=0.8,
            confidence=0.8,
            prediction_time=time.time(),
        )):
            result = await predictor.select_optimal_pieces([0], count=5)
        
        assert result == [0]

    @pytest.mark.asyncio
    async def test_select_optimal_pieces_multiple_pieces(self, predictor):
        """Test selecting optimal pieces from multiple pieces."""
        # Add piece info for multiple pieces
        for i in range(3):
            predictor.piece_info[i] = PieceInfo(
                piece_index=i,
                size=16384,
                hash=f"piece_hash_{i}".encode(),
                status=PieceStatus.MISSING,
                priority=PiecePriority.MEDIUM,
            )
        
        # Mock predictions with different priority scores
        predictions = [
            PiecePrediction(0, 2.0, 0.9, 0.9, 0.8, 0.8, time.time()),  # Highest priority
            PiecePrediction(1, 1.5, 0.8, 0.7, 0.7, 0.8, time.time()),  # Medium priority
            PiecePrediction(2, 3.0, 0.7, 0.5, 0.6, 0.8, time.time()),  # Lowest priority
        ]
        
        with patch.object(predictor, 'predict_piece_download_time', side_effect=predictions):
            result = await predictor.select_optimal_pieces([0, 1, 2], count=2)
        
        assert len(result) == 2
        assert result == [0, 1]  # Should be sorted by priority score

    @pytest.mark.asyncio
    async def test_update_piece_performance_new_piece(self, predictor):
        """Test updating performance for new piece."""
        performance_data = {
            "download_start_time": time.time(),
            "download_complete_time": time.time() + 2.0,
            "download_speed": 8192.0,
            "success": True,
            "download_time": 2.0,
            "actual_download_time": 2.0,
            "predicted_download_time": 1.8,
        }
        
        # Should not raise exception for non-existent piece
        await predictor.update_piece_performance(0, performance_data)

    @pytest.mark.asyncio
    async def test_update_piece_performance_existing_piece(self, predictor, sample_piece_info):
        """Test updating performance for existing piece."""
        predictor.piece_info[0] = sample_piece_info
        
        performance_data = {
            "download_start_time": time.time(),
            "download_complete_time": time.time() + 2.0,
            "download_speed": 8192.0,
            "success": True,
            "download_time": 2.0,
            "actual_download_time": 2.0,
            "predicted_download_time": 1.8,
        }
        
        with patch.object(predictor, '_update_download_pattern', new_callable=AsyncMock), \
             patch.object(predictor, '_online_learning', new_callable=AsyncMock):
            
            await predictor.update_piece_performance(0, performance_data)
        
        piece_info = predictor.piece_info[0]
        assert piece_info.download_start_time == performance_data["download_start_time"]
        assert piece_info.download_complete_time == performance_data["download_complete_time"]
        assert piece_info.download_duration == 2.0
        assert piece_info.download_speed == 8192.0
        assert piece_info.status == PieceStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_update_piece_performance_failed_download(self, predictor, sample_piece_info):
        """Test updating performance for failed download."""
        predictor.piece_info[0] = sample_piece_info
        
        performance_data = {
            "success": False,
            "download_time": 2.0,
        }
        
        with patch.object(predictor, '_update_download_pattern', new_callable=AsyncMock), \
             patch.object(predictor, '_online_learning', new_callable=AsyncMock):
            
            await predictor.update_piece_performance(0, performance_data)
        
        piece_info = predictor.piece_info[0]
        assert piece_info.status == PieceStatus.FAILED
        assert piece_info.retry_count == 1

    @pytest.mark.asyncio
    async def test_analyze_download_patterns_empty(self, predictor):
        """Test analyzing download patterns with no pieces."""
        result = await predictor.analyze_download_patterns()
        
        assert result["total_pieces"] == 0
        assert result["completed_pieces"] == 0
        assert result["failed_pieces"] == 0
        assert result["avg_download_time"] == 0.0
        assert result["avg_download_speed"] == 0.0
        assert result["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_analyze_download_patterns_with_pieces(self, predictor):
        """Test analyzing download patterns with pieces."""
        # Add some piece info
        predictor.piece_info[0] = PieceInfo(
            piece_index=0,
            size=16384,
            hash=b"hash1",
            status=PieceStatus.COMPLETED,
            download_duration=2.0,
            download_speed=8192.0,
        )
        
        predictor.piece_info[1] = PieceInfo(
            piece_index=1,
            size=16384,
            hash=b"hash2",
            status=PieceStatus.FAILED,
            download_duration=0.0,
            download_speed=0.0,
        )
        
        # Add download patterns
        predictor.download_patterns[0] = DownloadPattern(
            piece_index=0,
            download_times=[2.0, 1.8, 2.2],
            download_speeds=[8000, 9000, 7500],
            success_rate=1.0,
            avg_download_time=2.0,
            pattern_type="sequential",
            completion_probability=0.9,
        )
        
        result = await predictor.analyze_download_patterns()
        
        assert result["total_pieces"] == 2
        assert result["completed_pieces"] == 1
        assert result["failed_pieces"] == 1
        assert result["avg_download_time"] == 2.0
        assert result["avg_download_speed"] == 8192.0
        assert result["success_rate"] == 0.5
        assert result["pattern_types"]["sequential"] == 1

    def test_get_piece_info_existing(self, predictor, sample_piece_info):
        """Test getting existing piece info."""
        predictor.piece_info[0] = sample_piece_info
        
        result = predictor.get_piece_info(0)
        assert result == sample_piece_info

    def test_get_piece_info_nonexistent(self, predictor):
        """Test getting non-existent piece info."""
        result = predictor.get_piece_info(0)
        assert result is None

    def test_get_all_piece_info(self, predictor, sample_piece_info):
        """Test getting all piece info."""
        predictor.piece_info[0] = sample_piece_info
        
        all_info = predictor.get_all_piece_info()
        assert len(all_info) == 1
        assert all_info[0] == sample_piece_info

    def test_get_download_pattern_existing(self, predictor):
        """Test getting existing download pattern."""
        pattern = DownloadPattern(
            piece_index=0,
            download_times=[2.0, 1.8],
            download_speeds=[8000, 9000],
            success_rate=1.0,
            avg_download_time=1.9,
            pattern_type="sequential",
            completion_probability=0.9,
        )
        predictor.download_patterns[0] = pattern
        
        result = predictor.get_download_pattern(0)
        assert result == pattern

    def test_get_download_pattern_nonexistent(self, predictor):
        """Test getting non-existent download pattern."""
        result = predictor.get_download_pattern(0)
        assert result is None

    def test_get_ml_statistics(self, predictor):
        """Test getting ML statistics."""
        # Add some data
        predictor.piece_info[0] = PieceInfo(piece_index=0, size=16384, hash=b"hash")
        predictor.stats["total_predictions"] = 10
        predictor.stats["accurate_predictions"] = 8
        
        stats = predictor.get_ml_statistics()
        
        assert "total_predictions" in stats
        assert "accurate_predictions" in stats
        assert "prediction_accuracy" in stats
        assert "pieces_analyzed" in stats
        assert "patterns_learned" in stats
        assert "tracked_pieces" in stats
        assert stats["tracked_pieces"] == 1
        assert stats["prediction_accuracy"] == 0.8  # 8/10

    def test_cleanup_old_data(self, predictor):
        """Test cleanup of old data."""
        current_time = time.time()
        old_time = current_time - 4000  # 4000 seconds ago
        
        # Add old piece info
        old_piece = PieceInfo(
            piece_index=0,
            size=16384,
            hash=b"old_hash",
            last_attempt=old_time,
        )
        predictor.piece_info[0] = old_piece
        
        # Add recent piece info
        recent_piece = PieceInfo(
            piece_index=1,
            size=16384,
            hash=b"recent_hash",
            last_attempt=current_time,
        )
        predictor.piece_info[1] = recent_piece
        
        # Add performance history for old piece
        predictor.performance_history[0] = [100, 200, 300]
        
        # Cleanup data older than 1 hour
        predictor.cleanup_old_data(max_age_seconds=3600)
        
        # Old piece should be removed
        assert 0 not in predictor.piece_info
        assert 0 not in predictor.performance_history
        
        # Recent piece should remain
        assert 1 in predictor.piece_info

    @pytest.mark.asyncio
    async def test_extract_piece_features(self, predictor):
        """Test piece feature extraction."""
        piece_index = 0
        piece_size = 16384
        
        # Add piece info
        predictor.piece_info[piece_index] = PieceInfo(
            piece_index=piece_index,
            size=piece_size,
            hash=b"hash",
            priority=PiecePriority.HIGH,
            retry_count=2,
            download_duration=2.0,
            download_speed=8192.0,
        )
        
        # Add download pattern
        predictor.download_patterns[piece_index] = DownloadPattern(
            piece_index=piece_index,
            download_times=[2.0, 1.8],
            download_speeds=[8000, 9000],
            success_rate=0.9,
            avg_download_time=1.9,
            pattern_type="sequential",
            completion_probability=0.8,
        )
        
        with patch.object(predictor, '_estimate_network_quality', return_value=0.8), \
             patch.object(predictor, '_estimate_peer_availability', return_value=0.7), \
             patch.object(predictor, '_estimate_piece_rarity', return_value=0.6):
            
            features = await predictor._extract_piece_features(piece_index, piece_size)
        
        assert features["piece_index"] == float(piece_index)
        assert features["piece_size"] == float(piece_size)
        assert features["piece_priority"] == 0.8  # HIGH priority
        assert features["download_attempts"] == 2.0
        assert features["success_rate"] == 0.9
        assert features["avg_download_time"] == 1.9
        assert features["network_quality"] == 0.8
        assert features["peer_availability"] == 0.7
        assert features["piece_rarity"] == 0.6

    @pytest.mark.asyncio
    async def test_predict_download_time(self, predictor):
        """Test download time prediction."""
        features = {
            "piece_size": 16384.0,
            "network_quality": 0.8,
            "peer_availability": 0.7,
        }
        
        predicted_time = await predictor._predict_download_time(features)
        
        assert predicted_time > 0.0
        assert predicted_time >= 0.1  # Minimum time

    @pytest.mark.asyncio
    async def test_predict_success_rate(self, predictor):
        """Test success rate prediction."""
        features = {
            "network_quality": 0.8,
            "peer_availability": 0.7,
            "piece_rarity": 0.6,
        }
        
        success_rate = await predictor._predict_success_rate(features)
        
        assert 0.0 <= success_rate <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_priority_score(self, predictor):
        """Test priority score calculation."""
        features = {
            "piece_priority": 0.8,
            "success_rate": 0.9,
            "network_quality": 0.7,
            "peer_availability": 0.6,
        }
        
        score = await predictor._calculate_priority_score(features)
        
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_completion_probability(self, predictor):
        """Test completion probability calculation."""
        features = {
            "network_quality": 0.8,
            "peer_availability": 0.7,
            "success_rate": 0.9,
        }
        
        prob = await predictor._calculate_completion_probability(features)
        
        assert 0.0 <= prob <= 1.0

    @pytest.mark.asyncio
    async def test_update_download_pattern_new_pattern(self, predictor):
        """Test updating download pattern for new piece."""
        piece_index = 0
        performance_data = {
            "download_time": 2.0,
            "download_speed": 8192.0,
            "success": True,
        }
        
        with patch.object(predictor, '_determine_pattern_type', return_value="sequential"), \
             patch.object(predictor, '_calculate_completion_probability', return_value=0.8):
            
            await predictor._update_download_pattern(piece_index, performance_data)
        
        pattern = predictor.download_patterns[piece_index]
        assert pattern.piece_index == piece_index
        assert pattern.download_times == [2.0]
        assert pattern.download_speeds == [8192.0]
        assert pattern.success_rate > 0.0
        assert pattern.pattern_type == "sequential"
        assert pattern.completion_probability == 0.8

    @pytest.mark.asyncio
    async def test_update_download_pattern_existing_pattern(self, predictor):
        """Test updating existing download pattern."""
        piece_index = 0
        
        # Create existing pattern
        predictor.download_patterns[piece_index] = DownloadPattern(
            piece_index=piece_index,
            download_times=[2.0],
            download_speeds=[8000],
            success_rate=1.0,
            avg_download_time=2.0,
            pattern_type="sequential",
            completion_probability=0.9,
        )
        
        performance_data = {
            "download_time": 1.8,
            "download_speed": 9000,
            "success": True,
        }
        
        with patch.object(predictor, '_determine_pattern_type', return_value="sequential"), \
             patch.object(predictor, '_calculate_completion_probability', return_value=0.8):
            
            await predictor._update_download_pattern(piece_index, performance_data)
        
        pattern = predictor.download_patterns[piece_index]
        assert len(pattern.download_times) == 2
        assert len(pattern.download_speeds) == 2
        assert pattern.download_times[-1] == 1.8
        assert pattern.download_speeds[-1] == 9000

    @pytest.mark.asyncio
    async def test_determine_pattern_type_sequential(self, predictor):
        """Test pattern type determination for sequential."""
        predictor.download_patterns[0] = DownloadPattern(
            piece_index=0,
            download_times=[1.0, 1.1, 1.2, 1.3],
            download_speeds=[],
            success_rate=1.0,
            avg_download_time=1.15,
            pattern_type="unknown",
            completion_probability=0.8,
        )
        
        pattern_type = await predictor._determine_pattern_type(0)
        assert pattern_type == "sequential"

    @pytest.mark.asyncio
    async def test_determine_pattern_type_reverse_sequential(self, predictor):
        """Test pattern type determination for reverse sequential."""
        predictor.download_patterns[0] = DownloadPattern(
            piece_index=0,
            download_times=[1.3, 1.2, 1.1, 1.0],
            download_speeds=[],
            success_rate=1.0,
            avg_download_time=1.15,
            pattern_type="unknown",
            completion_probability=0.8,
        )
        
        pattern_type = await predictor._determine_pattern_type(0)
        assert pattern_type == "reverse_sequential"

    @pytest.mark.asyncio
    async def test_determine_pattern_type_random(self, predictor):
        """Test pattern type determination for random."""
        predictor.download_patterns[0] = DownloadPattern(
            piece_index=0,
            download_times=[1.0, 1.3, 1.1, 1.2],
            download_speeds=[],
            success_rate=1.0,
            avg_download_time=1.15,
            pattern_type="unknown",
            completion_probability=0.8,
        )
        
        pattern_type = await predictor._determine_pattern_type(0)
        assert pattern_type == "random"

    @pytest.mark.asyncio
    async def test_determine_pattern_type_unknown(self, predictor):
        """Test pattern type determination for unknown."""
        predictor.download_patterns[0] = DownloadPattern(
            piece_index=0,
            download_times=[1.0, 1.1],  # Not enough samples
            download_speeds=[],
            success_rate=1.0,
            avg_download_time=1.05,
            pattern_type="unknown",
            completion_probability=0.8,
        )
        
        pattern_type = await predictor._determine_pattern_type(0)
        assert pattern_type == "unknown"

    @pytest.mark.asyncio
    async def test_estimate_network_quality(self, predictor):
        """Test network quality estimation."""
        quality = await predictor._estimate_network_quality()
        assert quality == 0.7  # Default value

    @pytest.mark.asyncio
    async def test_estimate_peer_availability(self, predictor):
        """Test peer availability estimation."""
        availability = await predictor._estimate_peer_availability(0)
        assert availability == 0.8  # Default value

    @pytest.mark.asyncio
    async def test_estimate_piece_rarity(self, predictor):
        """Test piece rarity estimation."""
        rarity = await predictor._estimate_piece_rarity(0)
        assert rarity == 0.6  # Default value

    def test_priority_to_score(self, predictor):
        """Test priority enum to score conversion."""
        assert predictor._priority_to_score(PiecePriority.CRITICAL) == 1.0
        assert predictor._priority_to_score(PiecePriority.HIGH) == 0.8
        assert predictor._priority_to_score(PiecePriority.MEDIUM) == 0.6
        assert predictor._priority_to_score(PiecePriority.LOW) == 0.4
        assert predictor._priority_to_score(PiecePriority.NONE) == 0.2

    @pytest.mark.asyncio
    async def test_online_learning_insufficient_samples(self, predictor):
        """Test online learning with insufficient samples."""
        predictor.performance_history[0] = [1.0, 2.0]  # Only 2 samples
        
        # Should not raise exception
        await predictor._online_learning(0, {})

    @pytest.mark.asyncio
    async def test_online_learning_improving_performance(self, predictor):
        """Test online learning with improving performance."""
        # Add performance history showing improvement (need more samples for trend calculation)
        predictor.performance_history[0] = [
            0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
        ]
        
        with patch.object(predictor, '_adjust_models_positive') as mock_adjust:
            await predictor._online_learning(0, {})
            mock_adjust.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_online_learning_degrading_performance(self, predictor):
        """Test online learning with degrading performance."""
        # Add performance history showing degradation (need more samples for trend calculation)
        predictor.performance_history[0] = [
            3.0, 2.8, 2.6, 2.4, 2.2, 2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.8, 0.6, 0.4, 0.2
        ]
        
        with patch.object(predictor, '_adjust_models_negative') as mock_adjust:
            await predictor._online_learning(0, {})
            mock_adjust.assert_called_once_with(0)

    def test_adjust_models_positive(self, predictor):
        """Test positive model adjustment."""
        # Should not raise exception
        predictor._adjust_models_positive(0)

    def test_adjust_models_negative(self, predictor):
        """Test negative model adjustment."""
        # Should not raise exception
        predictor._adjust_models_negative(0)
