"""Storing Arbitrary Data in the DHT (BEP 44).

Provides support for storing and retrieving arbitrary key-value data
in the DHT with support for both immutable and mutable data.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

try:
    from cryptography.hazmat.primitives import hashes as crypto_hashes
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
    from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
        load_pem_public_key,
    )

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:  # pragma: no cover
    # Import error path: cryptography library unavailable. Difficult to test without
    # complex import mocking. The library is a required dependency, so this path is defensive.
    CRYPTOGRAPHY_AVAILABLE = False


logger = logging.getLogger(__name__)

# Maximum size of bencoded value in bytes (BEP 44)
MAX_STORAGE_VALUE_SIZE = 1000


class DHTStorageKeyType(str, Enum):
    """Storage key type."""

    IMMUTABLE = "immutable"
    MUTABLE = "mutable"


@dataclass
class DHTImmutableData:
    """Immutable DHT storage data (BEP 44).

    Immutable items have keys derived from the SHA-1 hash of the data itself.
    """

    data: bytes
    salt: bytes = b""
    seq: int = 0


@dataclass
class DHTMutableData:
    """Mutable DHT storage data (BEP 44).

    Mutable items have keys derived from the public key and optional salt.
    Can be updated by increasing the sequence number and re-signing.
    """

    data: bytes
    public_key: bytes
    seq: int
    signature: bytes
    salt: bytes = b""


def calculate_immutable_key(data: bytes, salt: bytes = b"") -> bytes:
    """Calculate storage key for immutable data (BEP 44).

    Key is SHA-1 hash of the data (plus salt if provided).

    Args:
        data: Data to store
        salt: Optional salt (not typically used for immutable)

    Returns:
        20-byte key (SHA-1 hash)

    """
    # BEP 44: key = SHA-1(data) for immutable items
    # Note: SHA-1 is required by BEP 44 specification
    digest = hashlib.sha1()  # nosec B324 - Required by BEP 44 spec
    if salt:
        digest.update(salt)
    digest.update(data)
    return digest.digest()


def calculate_mutable_key(public_key: bytes, salt: bytes = b"") -> bytes:
    """Calculate storage key for mutable data (BEP 44).

    Key is SHA-1 hash of the public key (plus salt if provided).

    Args:
        public_key: Public key bytes
        salt: Optional salt

    Returns:
        20-byte key (SHA-1 hash)

    """
    # BEP 44: key = SHA-1(public_key + salt) for mutable items
    # Note: SHA-1 is required by BEP 44 specification
    digest = hashlib.sha1()  # nosec B324 - Required by BEP 44 spec
    digest.update(public_key)
    if salt:
        digest.update(salt)
    return digest.digest()


def _detect_key_type(public_key_bytes: bytes) -> str:
    """Detect the type of public key (Ed25519 or RSA).

    Args:
        public_key_bytes: Public key bytes

    Returns:
        'ed25519' or 'rsa'

    """
    if not CRYPTOGRAPHY_AVAILABLE:
        msg = "Cryptography library not available"
        raise RuntimeError(msg)

    try:
        # Try Ed25519 first (32 bytes)
        if len(public_key_bytes) == 32:
            # Could be Ed25519 raw public key
            ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            return "ed25519"
    except Exception:  # pragma: no cover
        # Defensive: Ed25519 key parsing failure. Very rare with valid keys.
        # Hard to trigger without invalid key data that should be caught earlier.
        pass

    try:
        # Try RSA (variable size, but typically PEM format)
        # For raw bytes, we'll assume RSA if not Ed25519
        # In practice, BEP 44 uses Ed25519 or RSA PEM format
        if len(public_key_bytes) > 32:
            # Likely RSA
            return "rsa"
    except Exception:  # pragma: no cover
        # Defensive: RSA detection exception. Very rare, kept for robustness.
        pass

    # Default to Ed25519 for standard 32-byte keys
    return "ed25519"


def sign_mutable_data(
    data: bytes,
    public_key: bytes,
    private_key: bytes,
    seq: int,
    salt: bytes = b"",
) -> bytes:
    """Sign mutable data for storage (BEP 44).

    Args:
        data: Data to sign
        public_key: Public key bytes
        private_key: Private key bytes
        seq: Sequence number
        salt: Optional salt

    Returns:
        Signature bytes

    Raises:
        RuntimeError: If cryptography library not available
        ValueError: If key format is invalid

    """
    if not CRYPTOGRAPHY_AVAILABLE:
        msg = "Cryptography library not available for signing"
        raise RuntimeError(msg)

    # Build message to sign: salt + seq + v (data)
    # BEP 44: sig = sign(salt + seq + v)
    message = salt + seq.to_bytes(8, "big") + data

    key_type = _detect_key_type(public_key)

    try:
        if key_type == "ed25519":
            # Ed25519 signing
            private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
            return private_key_obj.sign(message)
        # RSA signing
        # Try to load as PEM first, then raw
        try:
            private_key_obj = load_pem_private_key(private_key, password=None)
        except Exception:
            # If not PEM, assume it's raw RSA key (less common)
            msg = "RSA keys must be in PEM format for BEP 44"
            raise ValueError(msg) from None

        if isinstance(private_key_obj, rsa.RSAPrivateKey):
            return private_key_obj.sign(
                message,
                padding=rsa_padding.PKCS1v15(),
                algorithm=crypto_hashes.SHA256(),
            )
        msg = "Unsupported key type for signing"
        raise ValueError(msg)
    except Exception:
        logger.exception("Failed to sign mutable data")
        raise


def verify_mutable_data_signature(
    data: bytes,
    public_key: bytes,
    signature: bytes,
    seq: int,
    salt: bytes = b"",
) -> bool:
    """Verify signature for mutable data (BEP 44).

    Args:
        data: Data that was signed
        public_key: Public key bytes
        signature: Signature bytes
        seq: Sequence number
        salt: Optional salt

    Returns:
        True if signature is valid, False otherwise

    """
    if not CRYPTOGRAPHY_AVAILABLE:  # pragma: no cover
        # Early return when cryptography unavailable. Difficult to test without import mocking.
        # The library is a required dependency, so this path is defensive.
        logger.warning("Cryptography library not available, cannot verify signature")
        return False

    # Build message that was signed: salt + seq + v (data)
    message = salt + seq.to_bytes(8, "big") + data

    key_type = _detect_key_type(public_key)

    try:
        if key_type == "ed25519":
            # Ed25519 verification
            if len(public_key) != 32:
                return False
            public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
            public_key_obj.verify(signature, message)
            return True
        # RSA verification
        try:
            public_key_obj = load_pem_public_key(public_key)
        except Exception:  # pragma: no cover
            # Defensive: Non-PEM RSA key format. BEP 44 uses PEM format, so this
            # exception path handles edge cases with malformed or raw key data.
            return False

        if isinstance(public_key_obj, rsa.RSAPublicKey):
            public_key_obj.verify(
                signature,
                message,
                padding=rsa_padding.PKCS1v15(),
                algorithm=crypto_hashes.SHA256(),
            )
            return True
        return False
    except Exception as e:
        logger.debug("Signature verification failed: %s", e)
        return False


def encode_storage_value(
    data: DHTImmutableData | DHTMutableData,
) -> dict[bytes, Any]:
    """Encode storage value for DHT message (BEP 44).

    Args:
        data: Immutable or mutable data to encode

    Returns:
        Dictionary suitable for bencode encoding

    Raises:
        ValueError: If data is too large or invalid

    """
    from ccbt.core.bencode import BencodeEncoder

    if isinstance(data, DHTImmutableData):
        # Immutable: just encode the data
        value: dict[bytes, Any] = {b"v": data.data}
        if data.salt:
            value[b"salt"] = data.salt
        if data.seq:
            value[b"seq"] = data.seq
    elif isinstance(data, DHTMutableData):
        # Mutable: include public key, seq, signature, optional salt
        value = {
            b"v": data.data,
            b"k": data.public_key,
            b"seq": data.seq,
            b"sig": data.signature,
        }
        if data.salt:
            value[b"salt"] = data.salt
    else:
        msg = f"Invalid data type: {type(data)}"
        raise TypeError(msg)

    # Check size limit (1000 bytes for bencoded value)
    encoded = BencodeEncoder().encode(value)
    if len(encoded) > MAX_STORAGE_VALUE_SIZE:
        msg = f"Encoded value too large: {len(encoded)} > {MAX_STORAGE_VALUE_SIZE}"
        raise ValueError(msg)

    return value


def decode_storage_value(
    value_dict: dict[bytes, Any],
    key_type: DHTStorageKeyType,
) -> DHTImmutableData | DHTMutableData:
    """Decode storage value from DHT message (BEP 44).

    Args:
        value_dict: Dictionary from DHT response (v field)
        key_type: Type of storage key (immutable or mutable)

    Returns:
        Decoded immutable or mutable data

    Raises:
        ValueError: If data is invalid or missing required fields

    """
    if key_type == DHTStorageKeyType.IMMUTABLE:
        # Immutable: just has data
        data_bytes = value_dict.get(b"v")
        if not data_bytes:
            msg = "Missing 'v' field in immutable data"
            raise ValueError(msg)

        salt = value_dict.get(b"salt", b"")
        seq = value_dict.get(b"seq", 0)

        return DHTImmutableData(data=data_bytes, salt=salt, seq=seq)

    # MUTABLE
    # Mutable: requires v, k, seq, sig
    data_bytes = value_dict.get(b"v")
    public_key = value_dict.get(b"k")
    seq = value_dict.get(b"seq")
    signature = value_dict.get(b"sig")

    if not data_bytes:  # pragma: no cover
        # Defensive error check: Missing required 'v' field. This should be caught
        # by validation earlier, but kept as a safety check for malformed data.
        msg = "Missing 'v' field in mutable data"
        raise ValueError(msg)
    if not public_key:
        msg = "Missing 'k' field in mutable data"
        raise ValueError(msg)
    if seq is None:
        msg = "Missing 'seq' field in mutable data"
        raise ValueError(msg)
    if not signature:
        msg = "Missing 'sig' field in mutable data"
        raise ValueError(msg)

    salt = value_dict.get(b"salt", b"")

    return DHTMutableData(
        data=data_bytes,
        public_key=public_key,
        seq=seq,
        signature=signature,
        salt=salt,
    )


@dataclass
class DHTStorageCacheEntry:
    """Cache entry for stored DHT data."""

    key: bytes
    value: DHTImmutableData | DHTMutableData
    stored_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600.0)


class DHTStorageCache:
    """Local cache for DHT storage operations (BEP 44)."""

    def __init__(self, default_ttl: int = 3600):
        """Initialize storage cache.

        Args:
            default_ttl: Default time-to-live in seconds

        """
        self.cache: dict[bytes, DHTStorageCacheEntry] = {}
        self.default_ttl = default_ttl

    def get(self, key: bytes) -> DHTImmutableData | DHTMutableData | None:
        """Get cached value.

        Args:
            key: Storage key

        Returns:
            Cached value or None if not found or expired

        """
        entry = self.cache.get(key)
        if entry is None:
            return None

        # Check expiration
        if time.time() > entry.expires_at:
            del self.cache[key]
            return None

        return entry.value

    def put(
        self,
        key: bytes,
        value: DHTImmutableData | DHTMutableData,
        ttl: int | None = None,
    ) -> None:
        """Store value in cache.

        Args:
            key: Storage key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)

        """
        if ttl is None:
            ttl = self.default_ttl

        entry = DHTStorageCacheEntry(
            key=key,
            value=value,
            stored_at=time.time(),
            expires_at=time.time() + ttl,
        )
        self.cache[key] = entry

    def remove(self, key: bytes) -> None:
        """Remove cached value.

        Args:
            key: Storage key to remove

        """
        self.cache.pop(key, None)

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed

        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items() if current_time > entry.expires_at
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()

    def size(self) -> int:
        """Get number of cached entries.

        Returns:
            Number of entries in cache

        """
        return len(self.cache)
