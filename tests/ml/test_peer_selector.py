"""Tests for ML peer selector."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from ccbt.ml.peer_selector import (
    PeerFeatures,
    PeerPrediction,
    PeerQuality,
    PeerSelector,
)
from ccbt.models import PeerInfo


class TestPeerSelector:
    """Test cases for PeerSelector."""

    @pytest.fixture
    def peer_selector(self):
        """Create a PeerSelector instance."""
        return PeerSelector()

    @pytest.fixture
    def sample_peer_info(self):
        """Create sample peer info."""
        return PeerInfo(
            peer_id=b"peer1234567890123456",
            ip="192.168.1.100",
            port=6881,
        )

    @pytest.mark.asyncio
    async def test_predict_peer_quality(self, peer_selector, sample_peer_info):
        """Test peer quality prediction."""
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            prediction = await peer_selector.predict_peer_quality(sample_peer_info)
        
        assert isinstance(prediction, PeerPrediction)
        assert prediction.peer_id == "7065657231323334353637383930313233343536"
        assert isinstance(prediction.predicted_quality, PeerQuality)
        assert 0.0 <= prediction.confidence <= 1.0
        assert isinstance(prediction.features, PeerFeatures)

    @pytest.mark.asyncio
    async def test_predict_peer_quality_without_peer_id(self, peer_selector):
        """Test peer quality prediction without peer_id."""
        peer_info = PeerInfo(
            peer_id=None,
            ip="192.168.1.100",
            port=6881,
        )
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            prediction = await peer_selector.predict_peer_quality(peer_info)
        
        assert prediction.peer_id == ""
        assert isinstance(prediction.predicted_quality, PeerQuality)

    @pytest.mark.asyncio
    async def test_rank_peers_empty_list(self, peer_selector):
        """Test ranking empty peer list."""
        result = await peer_selector.rank_peers([])
        assert result == []

    @pytest.mark.asyncio
    async def test_rank_peers_single_peer(self, peer_selector, sample_peer_info):
        """Test ranking single peer."""
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = await peer_selector.rank_peers([sample_peer_info])
        
        assert len(result) == 1
        peer, score = result[0]
        assert peer == sample_peer_info
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_rank_peers_multiple_peers(self, peer_selector):
        """Test ranking multiple peers."""
        peers = [
            PeerInfo(
                peer_id=b"peer1111111111111111",
                ip="192.168.1.101",
                port=6881,
            ),
            PeerInfo(
                peer_id=b"peer2222222222222222",
                ip="192.168.1.102",
                port=6881,
            ),
        ]
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = await peer_selector.rank_peers(peers)
        
        assert len(result) == 2
        # Results should be sorted by score (descending)
        assert result[0][1] >= result[1][1]

    @pytest.mark.asyncio
    async def test_rank_peers_existing_features(self, peer_selector, sample_peer_info):
        """Test ranking peers with existing features."""
        peer_id = sample_peer_info.peer_id.hex()
        
        # Add existing features
        features = PeerFeatures(
            peer_id=peer_id,
            ip=sample_peer_info.ip,
            quality_score=0.8,
            confidence=0.9,
        )
        peer_selector.peer_features[peer_id] = features
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            result = await peer_selector.rank_peers([sample_peer_info])
        
        assert len(result) == 1
        peer, score = result[0]
        assert score == 0.8  # Should use existing quality score

    @pytest.mark.asyncio
    async def test_update_peer_performance_new_peer(self, peer_selector):
        """Test updating performance for new peer."""
        performance_data = {
            "connection_success": True,
            "download_speed": 1000.0,
            "upload_speed": 500.0,
            "error_count": 2,
            "response_time": 0.1,
            "actual_quality": 0.7,
        }
        
        # Should not raise exception for non-existent peer
        await peer_selector.update_peer_performance("new_peer", performance_data)

    @pytest.mark.asyncio
    async def test_update_peer_performance_existing_peer(self, peer_selector, sample_peer_info):
        """Test updating performance for existing peer."""
        peer_id = sample_peer_info.peer_id.hex()
        
        # First predict quality to create features
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            await peer_selector.predict_peer_quality(sample_peer_info)
        
        performance_data = {
            "connection_success": True,
            "download_speed": 2000.0,
            "upload_speed": 1000.0,
            "error_count": 1,
            "response_time": 0.05,
            "actual_quality": 0.8,
        }
        
        await peer_selector.update_peer_performance(peer_id, performance_data)
        
        # Check that features were updated
        features = peer_selector.get_peer_features(peer_id)
        assert features is not None
        assert features.successful_connections == 2  # 1 initial + 1 from update
        assert features.avg_download_speed > 0
        assert features.avg_upload_speed > 0

    @pytest.mark.asyncio
    async def test_get_best_peers(self, peer_selector):
        """Test getting best peers."""
        peers = [
            PeerInfo(
                peer_id=b"peer1111111111111111",
                ip="192.168.1.101",
                port=6881,
            ),
            PeerInfo(
                peer_id=b"peer2222222222222222",
                ip="192.168.1.102",
                port=6881,
            ),
            PeerInfo(
                peer_id=b"peer3333333333333333",
                ip="192.168.1.103",
                port=6881,
            ),
        ]
        
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            best_peers = await peer_selector.get_best_peers(peers, count=2)
        
        assert len(best_peers) == 2
        assert all(isinstance(peer, PeerInfo) for peer in best_peers)

    @pytest.mark.asyncio
    async def test_get_best_peers_count_larger_than_available(self, peer_selector, sample_peer_info):
        """Test getting best peers when count is larger than available."""
        with patch('ccbt.events.emit_event', new_callable=AsyncMock):
            best_peers = await peer_selector.get_best_peers([sample_peer_info], count=5)
        
        assert len(best_peers) == 1
        assert best_peers[0] == sample_peer_info

    def test_get_peer_features_existing(self, peer_selector):
        """Test getting existing peer features."""
        peer_id = "test_peer"
        features = PeerFeatures(
            peer_id=peer_id,
            ip="192.168.1.100",
            quality_score=0.7,
            confidence=0.8,
        )
        peer_selector.peer_features[peer_id] = features
        
        result = peer_selector.get_peer_features(peer_id)
        assert result == features

    def test_get_peer_features_nonexistent(self, peer_selector):
        """Test getting non-existent peer features."""
        result = peer_selector.get_peer_features("nonexistent")
        assert result is None

    def test_get_all_peer_features(self, peer_selector):
        """Test getting all peer features."""
        # Add some features
        features1 = PeerFeatures(peer_id="peer1", ip="192.168.1.1")
        features2 = PeerFeatures(peer_id="peer2", ip="192.168.1.2")
        
        peer_selector.peer_features["peer1"] = features1
        peer_selector.peer_features["peer2"] = features2
        
        all_features = peer_selector.get_all_peer_features()
        
        assert len(all_features) == 2
        assert "peer1" in all_features
        assert "peer2" in all_features
        assert all_features["peer1"] == features1
        assert all_features["peer2"] == features2

    def test_get_ml_statistics(self, peer_selector):
        """Test getting ML statistics."""
        # Add some data
        features = PeerFeatures(peer_id="peer1", ip="192.168.1.1")
        peer_selector.peer_features["peer1"] = features
        peer_selector.stats["total_predictions"] = 10
        peer_selector.stats["accurate_predictions"] = 8
        
        stats = peer_selector.get_ml_statistics()
        
        assert "total_predictions" in stats
        assert "accurate_predictions" in stats
        assert "prediction_accuracy" in stats
        assert "peer_rankings" in stats
        assert "feature_extractions" in stats
        assert "tracked_peers" in stats
        assert "feature_weights" in stats
        assert stats["tracked_peers"] == 1
        assert stats["prediction_accuracy"] == 0.8  # 8/10

    def test_cleanup_old_data(self, peer_selector):
        """Test cleanup of old data."""
        current_time = time.time()
        old_time = current_time - 4000  # 4000 seconds ago
        
        # Add old features
        old_features = PeerFeatures(
            peer_id="old_peer",
            ip="192.168.1.100",
            last_seen=old_time,
        )
        peer_selector.peer_features["old_peer"] = old_features
        
        # Add recent features
        recent_features = PeerFeatures(
            peer_id="recent_peer",
            ip="192.168.1.101",
            last_seen=current_time,
        )
        peer_selector.peer_features["recent_peer"] = recent_features
        
        # Add performance history for old peer
        peer_selector.performance_history["old_peer"] = [100, 200, 300]
        
        # Cleanup data older than 1 hour
        peer_selector.cleanup_old_data(max_age_seconds=3600)
        
        # Old peer should be removed
        assert "old_peer" not in peer_selector.peer_features
        assert "old_peer" not in peer_selector.performance_history
        
        # Recent peer should remain
        assert "recent_peer" in peer_selector.peer_features

    @pytest.mark.asyncio
    async def test_extract_features(self, peer_selector, sample_peer_info):
        """Test feature extraction."""
        peer_id = sample_peer_info.peer_id.hex()
        
        with patch.object(peer_selector, '_estimate_latency', return_value=0.05), \
             patch.object(peer_selector, '_estimate_bandwidth', return_value=1000000), \
             patch.object(peer_selector, '_calculate_quality_score', return_value=0.7):
            
            features = await peer_selector._extract_features(peer_id, sample_peer_info)
        
        assert isinstance(features, PeerFeatures)
        assert features.peer_id == peer_id
        assert features.ip == sample_peer_info.ip
        assert features.connection_count == 1
        assert features.successful_connections == 1
        assert features.latency == 0.05
        assert features.bandwidth == 1000000
        assert features.quality_score == 0.7

    @pytest.mark.asyncio
    async def test_predict_quality_excellent(self, peer_selector):
        """Test quality prediction for excellent peer."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            quality_score=0.9,
        )
        
        quality, confidence = await peer_selector._predict_quality(features)
        
        assert quality == PeerQuality.EXCELLENT
        assert confidence == 0.9

    @pytest.mark.asyncio
    async def test_predict_quality_good(self, peer_selector):
        """Test quality prediction for good peer."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            quality_score=0.7,
        )
        
        quality, confidence = await peer_selector._predict_quality(features)
        
        assert quality == PeerQuality.GOOD
        assert confidence == 0.8

    @pytest.mark.asyncio
    async def test_predict_quality_average(self, peer_selector):
        """Test quality prediction for average peer."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            quality_score=0.5,
        )
        
        quality, confidence = await peer_selector._predict_quality(features)
        
        assert quality == PeerQuality.AVERAGE
        assert confidence == 0.7

    @pytest.mark.asyncio
    async def test_predict_quality_poor(self, peer_selector):
        """Test quality prediction for poor peer."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            quality_score=0.3,
        )
        
        quality, confidence = await peer_selector._predict_quality(features)
        
        assert quality == PeerQuality.POOR
        assert confidence == 0.6

    @pytest.mark.asyncio
    async def test_predict_quality_bad(self, peer_selector):
        """Test quality prediction for bad peer."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            quality_score=0.1,
        )
        
        quality, confidence = await peer_selector._predict_quality(features)
        
        assert quality == PeerQuality.BAD
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_update_features(self, peer_selector):
        """Test updating features with performance data."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            successful_connections=1,
            avg_download_speed=1000.0,
            avg_upload_speed=500.0,
            error_rate=0.0,
            response_time=1.0,
            first_seen=time.time() - 100,
        )
        
        performance_data = {
            "connection_success": True,
            "download_speed": 2000.0,
            "upload_speed": 1000.0,
            "error_count": 1,
            "response_time": 0.5,
        }
        
        with patch.object(peer_selector, '_calculate_quality_score', return_value=0.8):
            await peer_selector._update_features(features, performance_data)
        
        assert features.successful_connections == 2
        assert features.avg_download_speed > 1000.0  # Should be updated
        assert features.avg_upload_speed > 500.0  # Should be updated
        assert features.error_rate > 0.0  # Should have some error rate
        assert features.response_time < 1.0  # Should be updated
        assert features.last_seen > features.first_seen

    @pytest.mark.asyncio
    async def test_calculate_quality_score(self, peer_selector):
        """Test quality score calculation."""
        features = PeerFeatures(
            peer_id="peer1",
            ip="192.168.1.1",
            connection_count=10,
            successful_connections=9,
            avg_download_speed=5 * 1024 * 1024,  # 5MB/s
            error_rate=0.1,
            latency=50.0,  # 50ms
            activity_duration=1800.0,  # 30 minutes
        )
        
        score = await peer_selector._calculate_quality_score(features)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be good with these features

    def test_quality_to_score(self, peer_selector):
        """Test quality enum to score conversion."""
        assert peer_selector._quality_to_score(PeerQuality.EXCELLENT) == 0.9
        assert peer_selector._quality_to_score(PeerQuality.GOOD) == 0.7
        assert peer_selector._quality_to_score(PeerQuality.AVERAGE) == 0.5
        assert peer_selector._quality_to_score(PeerQuality.POOR) == 0.3
        assert peer_selector._quality_to_score(PeerQuality.BAD) == 0.1

    def test_update_average(self, peer_selector):
        """Test running average update."""
        current_avg = 100.0
        new_value = 200.0
        
        updated_avg = peer_selector._update_average(current_avg, new_value)
        
        assert updated_avg > current_avg
        assert updated_avg < new_value  # Should be weighted average

    @pytest.mark.asyncio
    async def test_estimate_latency(self, peer_selector):
        """Test latency estimation."""
        latency = await peer_selector._estimate_latency("192.168.1.1")
        
        assert 0.01 <= latency <= 0.5  # Should be between 10ms and 500ms

    @pytest.mark.asyncio
    async def test_estimate_bandwidth(self, peer_selector):
        """Test bandwidth estimation."""
        bandwidth = await peer_selector._estimate_bandwidth("192.168.1.1")
        
        assert 100 * 1024 <= bandwidth <= 10 * 1024 * 1024  # Should be between 100KB/s and 10MB/s

    @pytest.mark.asyncio
    async def test_online_learning_insufficient_samples(self, peer_selector):
        """Test online learning with insufficient samples."""
        peer_selector.performance_history["peer1"] = [0.5, 0.6]  # Only 2 samples
        
        # Should not raise exception
        await peer_selector._online_learning("peer1", {})

    @pytest.mark.asyncio
    async def test_online_learning_improving_performance(self, peer_selector):
        """Test online learning with improving performance."""
        # Add performance history showing improvement
        peer_selector.performance_history["peer1"] = [
            0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2
        ]
        
        with patch.object(peer_selector, '_adjust_weights_positive') as mock_adjust:
            await peer_selector._online_learning("peer1", {})
            mock_adjust.assert_called_once_with("peer1")

    @pytest.mark.asyncio
    async def test_online_learning_degrading_performance(self, peer_selector):
        """Test online learning with degrading performance."""
        # Add performance history showing degradation
        peer_selector.performance_history["peer1"] = [
            1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3
        ]
        
        with patch.object(peer_selector, '_adjust_weights_negative') as mock_adjust:
            await peer_selector._online_learning("peer1", {})
            mock_adjust.assert_called_once_with("peer1")

    def test_adjust_weights_positive(self, peer_selector):
        """Test positive weight adjustment."""
        initial_weights = peer_selector.feature_weights.copy()
        
        peer_selector._adjust_weights_positive("peer1")
        
        # Check that positive features had weights increased
        for feature in ["avg_download_speed", "successful_connections", "response_time"]:
            if feature in peer_selector.feature_weights:
                assert peer_selector.feature_weights[feature] >= initial_weights[feature]

    def test_adjust_weights_negative(self, peer_selector):
        """Test negative weight adjustment."""
        initial_weights = peer_selector.feature_weights.copy()
        
        peer_selector._adjust_weights_negative("peer1")
        
        # Check that negative features had weights decreased (or stayed at minimum)
        for feature in ["error_rate", "timeout_rate", "latency"]:
            if feature in peer_selector.feature_weights:
                # For negative weights, they should be at least 0.0 after adjustment
                assert peer_selector.feature_weights[feature] >= 0.0
                # The weight should be less than or equal to the initial weight
                # (accounting for the max(0.0, ...) constraint)
                if initial_weights[feature] <= 0.0:
                    assert peer_selector.feature_weights[feature] == 0.0
                else:
                    assert peer_selector.feature_weights[feature] <= initial_weights[feature]

    def test_initialize_feature_weights(self, peer_selector):
        """Test feature weights initialization."""
        assert "connection_count" in peer_selector.feature_weights
        assert "successful_connections" in peer_selector.feature_weights
        assert "avg_download_speed" in peer_selector.feature_weights
        assert "error_rate" in peer_selector.feature_weights
        assert "latency" in peer_selector.feature_weights
        
        # Check that weights are reasonable
        for weight in peer_selector.feature_weights.values():
            assert -1.0 <= weight <= 1.0
