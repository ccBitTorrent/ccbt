"""Unit tests for BEP 51: DHT Infohash Indexing.

Tests infohash indexing, index key calculation, entry encoding/decoding.
Target: 95%+ code coverage for ccbt/discovery/dht_indexing.py
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from ccbt.discovery.dht import AsyncDHTClient
from ccbt.discovery.dht_indexing import (
    DHTIndexEntry,
    DHTInfohashSample,
    calculate_index_key,
    decode_index_entry,
    encode_index_entry,
    update_index_entry,
)
from ccbt.discovery.dht_storage import DHTMutableData

pytestmark = [pytest.mark.unit, pytest.mark.discovery]

# Constants
SHA1_HASH_SIZE = 20  # SHA-1 produces 20-byte hashes
MAX_SAMPLES = 8  # Maximum samples per index entry


class TestCalculateIndexKey:
    """Test calculate_index_key function."""

    def test_calculate_index_key_basic(self):
        """Test calculating index key from query string."""
        key = calculate_index_key("test torrent")

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE

    def test_calculate_index_key_normalized(self):
        """Test that index key is normalized (lowercase, trimmed)."""
        key1 = calculate_index_key("Test Torrent")
        key2 = calculate_index_key("test torrent")
        key3 = calculate_index_key("  test torrent  ")

        # All should produce same key (normalized)
        assert key1 == key2 == key3

    def test_calculate_index_key_empty(self):
        """Test calculating key for empty string."""
        key = calculate_index_key("")

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE

    def test_calculate_index_key_unicode(self):
        """Test calculating key with Unicode characters."""
        key = calculate_index_key("测试种子")

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE


class TestDHTInfohashSample:
    """Test DHTInfohashSample dataclass."""

    def test_infohash_sample_creation(self):
        """Test creating infohash sample."""
        test_size = 12345
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test Torrent",
            size=test_size,
        )

        assert sample.info_hash == b"\x01" * 20
        assert sample.name == "Test Torrent"
        assert sample.size == test_size
        assert isinstance(sample.created_time, float)

    def test_infohash_sample_default_time(self):
        """Test that created_time defaults to current time."""
        before = time.time()
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test",
            size=1000,
        )
        after = time.time()

        assert before <= sample.created_time <= after


class TestDHTIndexEntry:
    """Test DHTIndexEntry dataclass."""

    def test_index_entry_creation(self):
        """Test creating index entry."""
        sample1 = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test 1",
            size=1000,
        )
        sample2 = DHTInfohashSample(
            info_hash=b"\x02" * 20,
            name="Test 2",
            size=2000,
        )
        entry = DHTIndexEntry(samples=[sample1, sample2])
        expected_samples_count = 2

        assert len(entry.samples) == expected_samples_count
        assert entry.samples[0] == sample1
        assert entry.samples[1] == sample2
        assert isinstance(entry.updated_time, float)

    def test_index_entry_empty(self):
        """Test creating empty index entry."""
        entry = DHTIndexEntry()

        assert len(entry.samples) == 0
        assert isinstance(entry.updated_time, float)


class TestUpdateIndexEntry:
    """Test update_index_entry function."""

    def test_update_empty_entry(self):
        """Test updating empty index entry."""
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test",
            size=1000,
        )

        entry = update_index_entry(b"\x01" * 20, sample, None)

        assert len(entry.samples) == 1
        assert entry.samples[0] == sample

    def test_update_existing_entry(self):
        """Test updating existing index entry."""
        existing_sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test 1",
            size=1000,
        )
        existing_entry = DHTIndexEntry(samples=[existing_sample])

        new_sample = DHTInfohashSample(
            info_hash=b"\x02" * 20,
            name="Test 2",
            size=2000,
        )

        updated = update_index_entry(b"\x01" * 20, new_sample, existing_entry)
        expected_samples_count = 2

        assert len(updated.samples) == expected_samples_count
        assert existing_sample in updated.samples
        assert new_sample in updated.samples

    def test_update_duplicate_infohash(self):
        """Test updating with duplicate infohash (should not add)."""
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test",
            size=1000,
        )
        entry = DHTIndexEntry(samples=[sample])

        # Add same sample again
        updated = update_index_entry(b"\x01" * 20, sample, entry)

        # Should still have only one sample
        assert len(updated.samples) == 1

    def test_update_max_samples(self):
        """Test updating entry with max samples limit."""
        # Create entry with max_samples
        samples = [
            DHTInfohashSample(
                info_hash=bytes([i] * 20),
                name=f"Test {i}",
                size=1000 + i,
            )
            for i in range(10)
        ]
        entry = DHTIndexEntry(samples=samples[:8])  # Start with 8 samples

        # Add one more (should keep only max_samples=8)
        new_sample = DHTInfohashSample(
            info_hash=bytes([9] * 20),
            name="Test 9",
            size=9000,
        )
        updated = update_index_entry(b"\x01" * 20, new_sample, entry, max_samples=8)

        # Should have at most MAX_SAMPLES samples (most recent)
        assert len(updated.samples) <= MAX_SAMPLES


class TestEncodeIndexEntry:
    """Test encode_index_entry function."""

    def test_encode_index_entry_basic(self):
        """Test encoding index entry."""
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test Torrent",
            size=12345,
            created_time=1234567890.0,
        )
        entry = DHTIndexEntry(samples=[sample], updated_time=1234567890.0)

        public_key = b"\x02" * 32
        private_key = b"\x03" * 32
        seq = 1

        encoded = encode_index_entry(entry, public_key, private_key, seq)

        assert encoded.data is not None
        assert encoded.public_key == public_key
        assert encoded.seq == seq
        assert encoded.signature is not None

    def test_encode_index_entry_multiple_samples(self):
        """Test encoding entry with multiple samples."""
        samples = [
            DHTInfohashSample(
                info_hash=bytes([i] * 20),
                name=f"Test {i}",
                size=1000 + i,
            )
            for i in range(5)
        ]
        entry = DHTIndexEntry(samples=samples)

        public_key = b"\x02" * 32
        private_key = b"\x03" * 32
        seq = 1

        encoded = encode_index_entry(entry, public_key, private_key, seq)

        assert encoded.data is not None
        assert encoded.signature is not None

    def test_encode_index_entry_with_salt(self):
        """Test encoding entry with salt."""
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test",
            size=1000,
        )
        entry = DHTIndexEntry(samples=[sample])

        public_key = b"\x02" * 32
        private_key = b"\x03" * 32
        seq = 1
        salt = b"test_salt"

        encoded = encode_index_entry(entry, public_key, private_key, seq, salt=salt)

        assert encoded.salt == salt


class TestDecodeIndexEntry:
    """Test decode_index_entry function."""

    def test_decode_index_entry_basic(self):
        """Test decoding index entry."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
        except ImportError:
            pytest.skip("cryptography library not available")

        # Generate valid Ed25519 key pair
        private_key_obj = ed25519.Ed25519PrivateKey.generate()
        public_key_obj = private_key_obj.public_key()
        private_key = private_key_obj.private_bytes_raw()
        public_key = public_key_obj.public_bytes_raw()

        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test Torrent",
            size=12345,
            created_time=1234567890.0,
        )
        entry = DHTIndexEntry(samples=[sample], updated_time=1234567890.0)

        seq = 1

        # Encode first
        encoded = encode_index_entry(entry, public_key, private_key, seq)

        # Then decode
        decoded = decode_index_entry(encoded)

        assert len(decoded.samples) == 1
        assert decoded.samples[0].info_hash == sample.info_hash
        assert decoded.samples[0].name == sample.name
        assert decoded.samples[0].size == sample.size

    def test_decode_index_entry_invalid_signature(self):
        """Test decoding entry with invalid signature."""
        # Create encoded entry
        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test",
            size=1000,
        )
        entry = DHTIndexEntry(samples=[sample])

        public_key = b"\x02" * 32
        private_key = b"\x03" * 32
        seq = 1

        encoded = encode_index_entry(entry, public_key, private_key, seq)

        # Corrupt signature
        corrupted = DHTMutableData(
            data=encoded.data,
            public_key=encoded.public_key,
            seq=encoded.seq,
            signature=b"\x00" * 64,  # Invalid signature
            salt=encoded.salt,
        )

        # Should raise ValueError due to invalid signature
        with pytest.raises(ValueError, match="Invalid signature"):
            decode_index_entry(corrupted)

    def test_decode_index_entry_malformed_data(self):
        """Test decoding malformed index entry data."""
        # Create entry with invalid bencoded data
        # This will fail during decoding
        invalid_data = DHTMutableData(
            data=b"invalid bencode data",
            public_key=b"\x02" * 32,
            seq=1,
            signature=b"\x00" * 64,
            salt=b"",
        )

        # Should raise ValueError when decoding fails
        with pytest.raises((ValueError, Exception)):
            decode_index_entry(invalid_data)


class TestAsyncDHTClientIndexing:
    """Test AsyncDHTClient indexing methods integration."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.discovery = MagicMock()
        config.discovery.dht_enable_storage = True
        config.discovery.dht_storage_ttl = 3600
        config.discovery.dht_enable_indexing = True
        config.discovery.dht_index_samples_per_key = 8
        config.discovery.dht_enable_ipv6 = True
        config.discovery.dht_prefer_ipv6 = True
        config.discovery.dht_enable_multiaddress = False
        config.discovery.dht_readonly_mode = False
        return config

    @pytest.mark.asyncio
    async def test_index_infohash_disabled_storage(self, mock_config):
        """Test index_infohash when storage is disabled."""
        mock_config.discovery.dht_enable_storage = False

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient()

            result = await client.index_infohash(
                info_hash=b"\x01" * 20,
                name="Test Torrent",
                size=12345,
                public_key=b"\x02" * 32,
                private_key=b"\x03" * 32,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_query_infohash_index_disabled(self, mock_config):
        """Test query_infohash_index when disabled."""
        mock_config.discovery.dht_enable_storage = False

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient()

            result = await client.query_infohash_index("test")

            assert result == []

    @pytest.mark.asyncio
    async def test_query_infohash_index_no_results(self, mock_config):
        """Test query_infohash_index with no results."""
        from unittest.mock import AsyncMock

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient()

            # Mock routing table and get_data to return None
            client.routing_table = MagicMock()
            client.routing_table.get_closest_nodes = MagicMock(return_value=[])
            client.get_data = AsyncMock(return_value=None)

            result = await client.query_infohash_index("nonexistent")

            assert result == []


class TestStoreInfohashSample:
    """Test store_infohash_sample function."""

    def test_store_infohash_sample_valid(self):
        """Test storing valid infohash sample."""
        from ccbt.discovery.dht_indexing import store_infohash_sample

        info_hash = b"\x01" * 20
        name = "Test Torrent"
        size = 12345
        public_key = b"\x02" * 32
        private_key = b"\x03" * 32

        key = store_infohash_sample(
            info_hash=info_hash,
            name=name,
            size=size,
            public_key=public_key,
            private_key=private_key,
        )

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE

    def test_store_infohash_sample_invalid_length(self):
        """Test storing infohash sample with invalid hash length."""
        from ccbt.discovery.dht_indexing import store_infohash_sample

        invalid_hash = b"\x01" * 19  # Wrong length
        with pytest.raises(ValueError, match="Info hash must be 20 bytes"):
            store_infohash_sample(
                info_hash=invalid_hash,
                name="Test",
                size=1000,
                public_key=b"\x02" * 32,
                private_key=b"\x03" * 32,
            )


class TestQueryIndexFunction:
    """Test query_index function."""

    def test_query_index_returns_empty(self):
        """Test query_index returns empty list (stub function)."""
        from ccbt.discovery.dht_indexing import query_index

        results = query_index("test query", max_results=10)

        # Function is a stub, returns empty list
        assert results == []


class TestDecodeIndexEntryEdgeCases:
    """Test decode_index_entry edge cases and error handling."""

    def test_decode_index_entry_with_decoding_error(self):
        """Test decode_index_entry handles decoding errors gracefully."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
        except ImportError:
            pytest.skip("cryptography library not available")

        sample = DHTInfohashSample(
            info_hash=b"\x01" * 20,
            name="Test",
            size=1000,
        )
        entry = DHTIndexEntry(samples=[sample])

        private_key_obj = ed25519.Ed25519PrivateKey.generate()
        public_key_obj = private_key_obj.public_key()
        private_key = private_key_obj.private_bytes_raw()
        public_key = public_key_obj.public_bytes_raw()

        seq = 1
        encoded = encode_index_entry(entry, public_key, private_key, seq)

        # Corrupt the data bytes to cause decoding error
        corrupted = DHTMutableData(
            data=b"invalid bencoded data that will fail",
            public_key=encoded.public_key,
            seq=encoded.seq,
            signature=encoded.signature,
            salt=encoded.salt,
        )

        # Should raise ValueError when bencode decoding fails
        with pytest.raises((ValueError, Exception)):
            decode_index_entry(corrupted)

    def test_decode_index_entry_invalid_sample_data(self):
        """Test decode_index_entry handles invalid sample data."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
        except ImportError:
            pytest.skip("cryptography library not available")

        # Create entry with problematic sample data
        from ccbt.core.bencode import BencodeEncoder

        # Create data with invalid sample entry (not a dict)
        entry_data = {
            b"samples": [b"invalid sample data"],  # Should be dict, not bytes
            b"updated": int(time.time()),
        }
        data_bytes = BencodeEncoder().encode(entry_data)

        private_key_obj = ed25519.Ed25519PrivateKey.generate()
        public_key_obj = private_key_obj.public_key()
        private_key = private_key_obj.private_bytes_raw()
        public_key = public_key_obj.public_bytes_raw()

        from ccbt.discovery.dht_storage import sign_mutable_data

        signature = sign_mutable_data(data_bytes, public_key, private_key, 1)

        invalid_entry = DHTMutableData(
            data=data_bytes,
            public_key=public_key,
            seq=1,
            signature=signature,
            salt=b"",
        )

        # Should handle invalid sample gracefully (skip it)
        decoded = decode_index_entry(invalid_entry)
        assert len(decoded.samples) == 0  # Invalid sample should be skipped

    def test_decode_index_entry_sample_decode_error(self):
        """Test decode_index_entry handles sample decode errors."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
        except ImportError:
            pytest.skip("cryptography library not available")

        # Create entry with sample that has invalid name encoding
        from ccbt.core.bencode import BencodeEncoder

        entry_data = {
            b"samples": [
                {
                    b"h": b"\x01" * 20,  # Valid hash
                    b"n": b"\xff\xfe\xfd",  # Invalid UTF-8 sequence
                    b"s": 1000,
                    b"t": int(time.time()),
                }
            ],
            b"updated": int(time.time()),
        }
        data_bytes = BencodeEncoder().encode(entry_data)

        private_key_obj = ed25519.Ed25519PrivateKey.generate()
        public_key_obj = private_key_obj.public_key()
        private_key = private_key_obj.private_bytes_raw()
        public_key = public_key_obj.public_bytes_raw()

        from ccbt.discovery.dht_storage import sign_mutable_data

        signature = sign_mutable_data(data_bytes, public_key, private_key, 1)

        invalid_entry = DHTMutableData(
            data=data_bytes,
            public_key=public_key,
            seq=1,
            signature=signature,
            salt=b"",
        )

        # Should handle decode error gracefully (skip invalid sample)
        decoded = decode_index_entry(invalid_entry)
        assert len(decoded.samples) == 0  # Invalid sample should be skipped

    def test_decode_index_entry_invalid_hash_length(self):
        """Test decode_index_entry with invalid hash length."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
        except ImportError:
            pytest.skip("cryptography library not available")

        # Create entry with sample that has wrong hash length
        from ccbt.core.bencode import BencodeEncoder

        entry_data = {
            b"samples": [
                {
                    b"h": b"\x01" * 19,  # Invalid length (19 bytes, should be 20)
                    b"n": b"Test",
                    b"s": 1000,
                    b"t": int(time.time()),
                }
            ],
            b"updated": int(time.time()),
        }
        data_bytes = BencodeEncoder().encode(entry_data)

        private_key_obj = ed25519.Ed25519PrivateKey.generate()
        public_key_obj = private_key_obj.public_key()
        private_key = private_key_obj.private_bytes_raw()
        public_key = public_key_obj.public_bytes_raw()

        from ccbt.discovery.dht_storage import sign_mutable_data

        signature = sign_mutable_data(data_bytes, public_key, private_key, 1)

        invalid_entry = DHTMutableData(
            data=data_bytes,
            public_key=public_key,
            seq=1,
            signature=signature,
            salt=b"",
        )

        # Should handle invalid hash length gracefully (skip sample)
        decoded = decode_index_entry(invalid_entry)
        assert len(decoded.samples) == 0  # Invalid hash length should skip sample

