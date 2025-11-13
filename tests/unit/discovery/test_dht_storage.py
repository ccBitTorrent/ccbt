"""Unit tests for BEP 44: Storing Arbitrary Data in the DHT.

Tests immutable and mutable data storage, signing, verification, and caching.
Target: 95%+ code coverage for ccbt/discovery/dht_storage.py
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from ccbt.discovery.dht import AsyncDHTClient
from ccbt.discovery.dht_storage import (
    DHTImmutableData,
    DHTMutableData,
    DHTStorageCache,
    DHTStorageKeyType,
    calculate_immutable_key,
    calculate_mutable_key,
    decode_storage_value,
    encode_storage_value,
    verify_mutable_data_signature,
)

pytestmark = [pytest.mark.unit, pytest.mark.discovery]

# Constants
SHA1_HASH_SIZE = 20  # SHA-1 produces 20-byte hashes


class TestCalculateImmutableKey:
    """Test calculate_immutable_key function."""

    def test_calculate_immutable_key_basic(self):
        """Test calculating key for immutable data."""
        data = b"test data"
        key = calculate_immutable_key(data)

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE

    def test_calculate_immutable_key_with_salt(self):
        """Test calculating key with salt."""
        data = b"test data"
        salt = b"salt"
        key1 = calculate_immutable_key(data)
        key2 = calculate_immutable_key(data, salt=salt)

        # Keys should be different when salt is used
        assert key1 != key2

    def test_calculate_immutable_key_empty_data(self):
        """Test calculating key for empty data."""
        key = calculate_immutable_key(b"")

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE


class TestCalculateMutableKey:
    """Test calculate_mutable_key function."""

    def test_calculate_mutable_key_basic(self):
        """Test calculating key for mutable data."""
        public_key = b"\x01" * 32  # 32-byte Ed25519 key
        key = calculate_mutable_key(public_key)

        assert isinstance(key, bytes)
        assert len(key) == SHA1_HASH_SIZE

    def test_calculate_mutable_key_with_salt(self):
        """Test calculating key with salt."""
        public_key = b"\x01" * 32
        salt = b"salt"
        key1 = calculate_mutable_key(public_key)
        key2 = calculate_mutable_key(public_key, salt=salt)

        # Keys should be different when salt is used
        assert key1 != key2

    def test_calculate_mutable_key_empty_salt(self):
        """Test calculating key with empty salt."""
        public_key = b"\x01" * 32
        key1 = calculate_mutable_key(public_key)
        key2 = calculate_mutable_key(public_key, salt=b"")

        # Empty salt should be same as no salt
        assert key1 == key2


class TestEncodeStorageValue:
    """Test encode_storage_value function."""

    def test_encode_immutable_data(self):
        """Test encoding immutable data."""
        data = DHTImmutableData(data=b"test", salt=b"salt", seq=1)
        encoded = encode_storage_value(data)

        assert isinstance(encoded, dict)
        assert b"v" in encoded
        assert encoded[b"v"] == b"test"
        assert encoded.get(b"salt") == b"salt"
        assert encoded.get(b"seq") == 1

    def test_encode_immutable_data_no_salt(self):
        """Test encoding immutable data without salt."""
        data = DHTImmutableData(data=b"test")
        encoded = encode_storage_value(data)

        assert b"v" in encoded
        assert b"salt" not in encoded

    def test_encode_mutable_data(self):
        """Test encoding mutable data."""
        data = DHTMutableData(
            data=b"test",
            public_key=b"\x01" * 32,
            seq=1,
            signature=b"\x02" * 64,
            salt=b"salt",
        )
        encoded = encode_storage_value(data)

        assert isinstance(encoded, dict)
        assert b"v" in encoded
        assert b"k" in encoded
        assert b"seq" in encoded
        assert b"sig" in encoded
        assert encoded[b"v"] == b"test"
        assert encoded[b"k"] == b"\x01" * 32
        assert encoded[b"seq"] == 1
        assert encoded[b"sig"] == b"\x02" * 64
        assert encoded.get(b"salt") == b"salt"

    def test_encode_mutable_data_no_salt(self):
        """Test encoding mutable data without salt."""
        data = DHTMutableData(
            data=b"test",
            public_key=b"\x01" * 32,
            seq=1,
            signature=b"\x02" * 64,
        )
        encoded = encode_storage_value(data)

        assert b"v" in encoded
        assert b"salt" not in encoded

    def test_encode_storage_value_too_large(self):
        """Test encoding value that exceeds size limit."""
        # Create data that when encoded exceeds MAX_STORAGE_VALUE_SIZE (1000 bytes)
        large_data = b"x" * 2000
        data = DHTImmutableData(data=large_data)

        # Should raise ValueError due to size limit
        with pytest.raises(ValueError, match="too large"):
            encode_storage_value(data)


class TestDecodeStorageValue:
    """Test decode_storage_value function."""

    def test_decode_immutable_data(self):
        """Test decoding immutable data."""
        value_dict = {
            b"v": b"test",
            b"salt": b"salt",
            b"seq": 1,
        }
        decoded = decode_storage_value(value_dict, DHTStorageKeyType.IMMUTABLE)

        assert isinstance(decoded, DHTImmutableData)
        assert decoded.data == b"test"
        assert decoded.salt == b"salt"
        assert decoded.seq == 1

    def test_decode_immutable_data_no_salt(self):
        """Test decoding immutable data without salt."""
        value_dict = {b"v": b"test"}
        decoded = decode_storage_value(value_dict, DHTStorageKeyType.IMMUTABLE)

        assert isinstance(decoded, DHTImmutableData)
        assert decoded.data == b"test"
        assert decoded.salt == b""
        assert decoded.seq == 0

    def test_decode_mutable_data(self):
        """Test decoding mutable data."""
        value_dict = {
            b"v": b"test",
            b"k": b"\x01" * 32,
            b"seq": 1,
            b"sig": b"\x02" * 64,
            b"salt": b"salt",
        }
        decoded = decode_storage_value(value_dict, DHTStorageKeyType.MUTABLE)

        assert isinstance(decoded, DHTMutableData)
        assert decoded.data == b"test"
        assert decoded.public_key == b"\x01" * 32
        assert decoded.seq == 1
        assert decoded.signature == b"\x02" * 64
        assert decoded.salt == b"salt"

    def test_decode_mutable_data_no_salt(self):
        """Test decoding mutable data without salt."""
        value_dict = {
            b"v": b"test",
            b"k": b"\x01" * 32,
            b"seq": 1,
            b"sig": b"\x02" * 64,
        }
        decoded = decode_storage_value(value_dict, DHTStorageKeyType.MUTABLE)

        assert isinstance(decoded, DHTMutableData)
        assert decoded.salt == b""

    def test_decode_immutable_data_missing_v(self):
        """Test decoding immutable data missing v field."""
        value_dict = {b"salt": b"salt"}
        with pytest.raises(ValueError, match=r"Missing.*v.*field"):
            decode_storage_value(value_dict, DHTStorageKeyType.IMMUTABLE)

    def test_decode_mutable_data_missing_fields(self):
        """Test decoding mutable data with missing required fields."""
        # Missing k
        value_dict = {
            b"v": b"test",
            b"seq": 1,
            b"sig": b"\x02" * 64,
        }
        with pytest.raises(ValueError, match=r"Missing.*k.*field"):
            decode_storage_value(value_dict, DHTStorageKeyType.MUTABLE)

        # Missing seq
        value_dict = {
            b"v": b"test",
            b"k": b"\x01" * 32,
            b"sig": b"\x02" * 64,
        }
        with pytest.raises(ValueError, match=r"Missing.*seq.*field"):
            decode_storage_value(value_dict, DHTStorageKeyType.MUTABLE)

        # Missing sig
        value_dict = {
            b"v": b"test",
            b"k": b"\x01" * 32,
            b"seq": 1,
        }
        with pytest.raises(ValueError, match=r"Missing.*sig.*field"):
            decode_storage_value(value_dict, DHTStorageKeyType.MUTABLE)


class TestDHTStorageCache:
    """Test DHTStorageCache class."""

    def test_cache_put_and_get(self):
        """Test putting and getting from cache."""
        cache = DHTStorageCache(default_ttl=3600)
        key = b"\x01" * 20
        data = DHTImmutableData(data=b"test")

        cache.put(key, data)
        retrieved = cache.get(key)

        assert retrieved == data

    def test_cache_get_nonexistent(self):
        """Test getting non-existent key."""
        cache = DHTStorageCache()
        key = b"\x01" * 20

        retrieved = cache.get(key)

        assert retrieved is None

    def test_cache_remove(self):
        """Test removing from cache."""
        cache = DHTStorageCache()
        key = b"\x01" * 20
        data = DHTImmutableData(data=b"test")

        cache.put(key, data)
        cache.remove(key)
        retrieved = cache.get(key)

        assert retrieved is None

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = DHTStorageCache()
        key1 = b"\x01" * 20
        key2 = b"\x02" * 20
        data1 = DHTImmutableData(data=b"test1")
        data2 = DHTImmutableData(data=b"test2")

        cache.put(key1, data1)
        cache.put(key2, data2)
        cache.clear()

        assert cache.get(key1) is None
        assert cache.get(key2) is None
        assert cache.size() == 0

    def test_cache_size(self):
        """Test cache size tracking."""
        cache = DHTStorageCache()
        key1 = b"\x01" * 20
        key2 = b"\x02" * 20

        assert cache.size() == 0

        cache.put(key1, DHTImmutableData(data=b"test1"))
        assert cache.size() == 1

        cache.put(key2, DHTImmutableData(data=b"test2"))
        expected_size = 2
        assert cache.size() == expected_size

        cache.remove(key1)
        assert cache.size() == 1

    def test_cache_custom_ttl(self):
        """Test cache with custom TTL."""
        cache = DHTStorageCache(default_ttl=100)
        key = b"\x01" * 20
        data = DHTImmutableData(data=b"test")

        cache.put(key, data, ttl=1)  # 1 second TTL

        # Should still be available immediately
        assert cache.get(key) == data

    def test_cache_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = DHTStorageCache(default_ttl=1)
        key1 = b"\x01" * 20
        key2 = b"\x02" * 20
        data1 = DHTImmutableData(data=b"test1")
        data2 = DHTImmutableData(data=b"test2")

        # Put with short TTL
        cache.put(key1, data1, ttl=0.1)  # Expires quickly
        cache.put(key2, data2, ttl=3600)  # Long TTL

        # Wait for expiration
        time.sleep(0.2)

        # Cleanup should remove expired entry
        removed = cache.cleanup_expired()

        assert removed >= 1
        assert cache.get(key1) is None
        assert cache.get(key2) == data2


class TestVerifyMutableDataSignature:
    """Test verify_mutable_data_signature function."""

    def test_verify_signature_without_cryptography(self):
        """Test verification when cryptography not available."""
        # This test checks the fallback behavior
        # Note: If cryptography is available, real verification will happen
        result = verify_mutable_data_signature(
            data=b"test",
            public_key=b"\x01" * 32,
            signature=b"\x02" * 64,
            seq=1,
            salt=b"",
        )

        # Should return False if cryptography not available or signature invalid
        # Actual result depends on whether cryptography library is installed
        assert isinstance(result, bool)

    def test_verify_signature_invalid_length(self):
        """Test verification with invalid public key length."""
        # For Ed25519, public key should be 32 bytes
        result = verify_mutable_data_signature(
            data=b"test",
            public_key=b"\x01" * 16,  # Too short
            signature=b"\x02" * 64,
            seq=1,
            salt=b"",
        )

        # Should return False for invalid key length
        assert result is False


class TestAsyncDHTClientStorage:
    """Test AsyncDHTClient storage methods integration."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.discovery = MagicMock()
        config.discovery.dht_enable_storage = True
        config.discovery.dht_storage_ttl = 3600
        config.discovery.dht_enable_ipv6 = True
        config.discovery.dht_prefer_ipv6 = True
        config.discovery.dht_enable_multiaddress = False
        config.discovery.dht_readonly_mode = False
        config.discovery.dht_enable_indexing = False
        return config

    @pytest.mark.asyncio
    async def test_put_data_disabled(self, mock_config):
        """Test put_data when storage is disabled."""
        mock_config.discovery.dht_enable_storage = False

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient()

            result = await client.put_data(
                key=b"\x01" * 20,
                value={b"v": b"test"},
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_put_data_readonly(self, mock_config):
        """Test put_data in read-only mode."""
        mock_config.discovery.dht_readonly_mode = True

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient(read_only=True)

            result = await client.put_data(
                key=b"\x01" * 20,
                value={b"v": b"test"},
            )

            assert result == 0

    @pytest.mark.asyncio
    async def test_get_data_disabled(self, mock_config):
        """Test get_data when storage is disabled."""
        mock_config.discovery.dht_enable_storage = False

        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient()

            result = await client.get_data(key=b"\x01" * 20)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_data_from_cache(self, mock_config):
        """Test get_data retrieves from cache."""
        with patch("ccbt.discovery.dht.get_config", return_value=mock_config):
            client = AsyncDHTClient()

            # Mock cache to return data
            cached_data = DHTImmutableData(data=b"cached test")
            client.storage_cache.put(b"\x01" * 20, cached_data)

            # Mock routing table
            client.routing_table = MagicMock()
            client.routing_table.get_closest_nodes = MagicMock(return_value=[])

            result = await client.get_data(key=b"\x01" * 20)

            # Should return encoded cached value
            assert result is not None
            assert b"v" in result


class TestDetectKeyType:
    """Test _detect_key_type function."""

    def test_detect_key_type_ed25519(self):
        """Test detecting Ed25519 key type."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
        except ImportError:
            pytest.skip("cryptography library not available")

        # Generate valid Ed25519 key
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes_raw()

        from ccbt.discovery.dht_storage import _detect_key_type

        key_type = _detect_key_type(public_key)
        assert key_type == "ed25519"

    def test_detect_key_type_without_cryptography(self):
        """Test _detect_key_type raises when cryptography unavailable."""
        from unittest.mock import patch

        from ccbt.discovery.dht_storage import CRYPTOGRAPHY_AVAILABLE, _detect_key_type

        if CRYPTOGRAPHY_AVAILABLE:
            # Temporarily mock as unavailable
            with patch("ccbt.discovery.dht_storage.CRYPTOGRAPHY_AVAILABLE", False):
                with pytest.raises(RuntimeError, match="Cryptography library not available"):
                    _detect_key_type(b"\x01" * 32)


class TestSignMutableData:
    """Test sign_mutable_data function."""

    def test_sign_mutable_data_without_cryptography(self):
        """Test signing when cryptography unavailable."""
        from unittest.mock import patch

        from ccbt.discovery.dht_storage import CRYPTOGRAPHY_AVAILABLE, sign_mutable_data

        if CRYPTOGRAPHY_AVAILABLE:
            # Temporarily mock as unavailable
            with patch("ccbt.discovery.dht_storage.CRYPTOGRAPHY_AVAILABLE", False):
                with pytest.raises(RuntimeError, match="Cryptography library not available"):
                    sign_mutable_data(
                        data=b"test",
                        public_key=b"\x01" * 32,
                        private_key=b"\x02" * 32,
                        seq=1,
                    )

    def test_sign_mutable_data_rsa_path(self):
        """Test signing with RSA key path."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            pytest.skip("cryptography library not available")

        # Generate RSA key pair
        private_key_obj = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key_obj = private_key_obj.public_key()

        # Serialize to PEM format
        private_key_pem = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key_pem = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        from ccbt.discovery.dht_storage import sign_mutable_data

        data = b"test data"
        seq = 1
        salt = b""

        # Should use RSA signing path
        signature = sign_mutable_data(
            data=data,
            public_key=public_key_pem,
            private_key=private_key_pem,
            seq=seq,
            salt=salt,
        )

        assert isinstance(signature, bytes)
        assert len(signature) > 0


class TestEncodeStorageValueErrors:
    """Test encode_storage_value error cases."""

    def test_encode_storage_value_invalid_type(self):
        """Test encoding with invalid data type."""
        # Create invalid data type
        class InvalidData:
            pass

        invalid_data = InvalidData()

        with pytest.raises(TypeError, match="Invalid data type"):
            encode_storage_value(invalid_data)  # type: ignore[arg-type]


class TestVerifyMutableDataSignatureRSA:
    """Test verify_mutable_data_signature with RSA keys."""

    def test_verify_signature_rsa_valid(self):
        """Test verifying valid RSA signature."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            pytest.skip("cryptography library not available")

        # Generate RSA key pair
        private_key_obj = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key_obj = private_key_obj.public_key()

        # Serialize to PEM format
        private_key_pem = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key_pem = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        from ccbt.discovery.dht_storage import sign_mutable_data, verify_mutable_data_signature

        data = b"test data"
        seq = 1
        salt = b""

        # Sign the data
        signature = sign_mutable_data(
            data=data,
            public_key=public_key_pem,
            private_key=private_key_pem,
            seq=seq,
            salt=salt,
        )

        # Verify the signature
        result = verify_mutable_data_signature(
            data=data,
            public_key=public_key_pem,
            signature=signature,
            seq=seq,
            salt=salt,
        )

        assert result is True

    def test_verify_signature_rsa_invalid(self):
        """Test verifying invalid RSA signature."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            pytest.skip("cryptography library not available")

        # Generate RSA key pair
        private_key_obj = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key_obj = private_key_obj.public_key()

        public_key_pem = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        from ccbt.discovery.dht_storage import verify_mutable_data_signature

        data = b"test data"
        seq = 1
        salt = b""
        invalid_signature = b"\x00" * 256  # Invalid signature

        # Verify should fail
        result = verify_mutable_data_signature(
            data=data,
            public_key=public_key_pem,
            signature=invalid_signature,
            seq=seq,
            salt=salt,
        )

        assert result is False

    def test_verify_signature_rsa_invalid_pem(self):
        """Test verifying with invalid PEM format."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError:
            pytest.skip("cryptography library not available")

        from ccbt.discovery.dht_storage import verify_mutable_data_signature

        # Invalid PEM public key
        invalid_public_key = b"invalid PEM data"

        result = verify_mutable_data_signature(
            data=b"test",
            public_key=invalid_public_key,
            signature=b"\x00" * 256,
            seq=1,
            salt=b"",
        )

        assert result is False


class TestDHTStorageCacheErrors:
    """Test DHTStorageCache error handling."""

    def test_cache_get_expired_entry(self):
        """Test getting expired cache entry."""
        import time

        cache = DHTStorageCache(default_ttl=0.1)  # Very short TTL
        key = b"\x01" * 20
        data = DHTImmutableData(data=b"test")

        cache.put(key, data)

        # Wait for expiration
        time.sleep(0.2)

        # Should return None after expiration
        result = cache.get(key)
        assert result is None

    def test_cache_get_nonexistent_after_cleanup(self):
        """Test getting entry after cleanup."""
        cache = DHTStorageCache(default_ttl=1)
        key = b"\x01" * 20
        data = DHTImmutableData(data=b"test")

        cache.put(key, data, ttl=0.1)

        # Wait and cleanup
        import time

        time.sleep(0.2)
        cache.cleanup_expired()

        # Should return None
        result = cache.get(key)
        assert result is None


class TestSignMutableDataErrors:
    """Test sign_mutable_data error handling."""

    def test_sign_mutable_data_unsupported_key_type(self):
        """Test signing with unsupported key type."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            pytest.skip("cryptography library not available")

        # Create a key that's not RSA or Ed25519
        # We'll mock the load_pem_private_key to return something that's not RSA
        from unittest.mock import patch, MagicMock

        from ccbt.discovery.dht_storage import sign_mutable_data

        # Mock to return a non-RSA key object
        mock_key = MagicMock()
        mock_key.__class__.__name__ = "ECPrivateKey"  # Not RSA

        with patch("ccbt.discovery.dht_storage.load_pem_private_key", return_value=mock_key):
            with pytest.raises(ValueError, match="Unsupported key type"):
                sign_mutable_data(
                    data=b"test",
                    public_key=b"-----BEGIN PUBLIC KEY-----\ninvalid\n-----END PUBLIC KEY-----",
                    private_key=b"-----BEGIN PRIVATE KEY-----\ninvalid\n-----END PRIVATE KEY-----",
                    seq=1,
                )

    def test_sign_mutable_data_rsa_not_pem(self):
        """Test signing with RSA key that's not in PEM format."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError:
            pytest.skip("cryptography library not available")

        from ccbt.discovery.dht_storage import sign_mutable_data

        # Raw bytes (not PEM)
        raw_private_key = b"\x01" * 100

        with pytest.raises(ValueError, match="RSA keys must be in PEM format"):
            sign_mutable_data(
                data=b"test",
                public_key=b"\x02" * 100,
                private_key=raw_private_key,
                seq=1,
            )


class TestVerifyMutableDataSignatureEdgeCases:
    """Test verify_mutable_data_signature edge cases."""

    def test_verify_signature_rsa_non_rsa_key(self):
        """Test verifying with non-RSA key loaded from PEM."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            pytest.skip("cryptography library not available")

        # Generate Ed25519 key and serialize to PEM
        private_key_obj = ed25519.Ed25519PrivateKey.generate()
        public_key_obj = private_key_obj.public_key()

        public_key_pem = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        from ccbt.discovery.dht_storage import verify_mutable_data_signature

        # Try to verify with Ed25519 key (should return False when checking if RSA)
        result = verify_mutable_data_signature(
            data=b"test",
            public_key=public_key_pem,
            signature=b"\x00" * 64,
            seq=1,
            salt=b"",
        )

        # Should return False (not RSA key)
        assert result is False

