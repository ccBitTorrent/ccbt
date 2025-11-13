"""Diffie-Hellman key exchange for BEP 3 encryption.

from __future__ import annotations

Implements DH key exchange with 768-bit or 1024-bit groups as specified
in BEP 3. Provides key derivation using SHA-1 hash function.
"""

from __future__ import annotations

import hashlib
from typing import NamedTuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh


class DHKeyPair(NamedTuple):
    """Diffie-Hellman key pair."""

    private_key: dh.DHPrivateKey
    public_key: dh.DHPublicKey


class DHPeerExchange:
    """Diffie-Hellman key exchange for peer connections."""

    # Standard DH parameters (768-bit and 1024-bit)
    # These are common parameters used in BitTorrent encryption
    _DH_768_PARAMS = None
    _DH_1024_PARAMS = None

    def __init__(self, key_size: int = 768):
        """Initialize DH exchange with key size.

        Args:
            key_size: DH key size in bits (768 or 1024)

        Raises:
            ValueError: If key_size is not 768 or 1024

        """
        if key_size not in (768, 1024):
            msg = f"DH key size must be 768 or 1024 bits, got {key_size}"
            raise ValueError(msg)

        self.key_size = key_size
        self._parameters = self._get_dh_parameters(key_size)

    @classmethod
    def _get_dh_parameters(cls, key_size: int) -> dh.DHParameters:
        """Get DH parameters for specified key size.

        Args:
            key_size: DH key size in bits (768 or 1024)

        Returns:
            DH parameters

        """
        # Generate parameters on first use and cache
        if key_size == 768:
            if cls._DH_768_PARAMS is None:
                # Generate 768-bit parameters
                # Note: In production, use well-known parameters for compatibility
                cls._DH_768_PARAMS = dh.generate_parameters(
                    generator=2, key_size=768, backend=default_backend()
                )
            return cls._DH_768_PARAMS

        if key_size == 1024:
            if cls._DH_1024_PARAMS is None:
                # Generate 1024-bit parameters
                cls._DH_1024_PARAMS = dh.generate_parameters(
                    generator=2, key_size=1024, backend=default_backend()
                )
            return cls._DH_1024_PARAMS

        msg = f"Unsupported key size: {key_size}"
        raise ValueError(msg)

    def generate_keypair(self) -> DHKeyPair:
        """Generate DH public/private key pair.

        Returns:
            DH key pair (private_key, public_key)

        """
        private_key = self._parameters.generate_private_key()
        public_key = private_key.public_key()
        return DHKeyPair(private_key=private_key, public_key=public_key)

    def compute_shared_secret(
        self, private_key: dh.DHPrivateKey, peer_public_key: dh.DHPublicKey
    ) -> bytes:
        """Compute shared secret from peer's public key.

        Args:
            private_key: Our private key
            peer_public_key: Peer's public key

        Returns:
            Shared secret as bytes

        """
        return private_key.exchange(peer_public_key)

    def derive_encryption_key(
        self,
        shared_secret: bytes,
        info_hash: bytes,
        pad: bytes | None = None,
    ) -> bytes:
        """Derive encryption key from shared secret.

        Per BEP 3: key = SHA1(secret + S + info_hash)
        Where S is a pad (typically 0x00 bytes for RC4, or IV for AES).

        Args:
            shared_secret: Shared secret from DH exchange
            info_hash: Torrent info hash (20 bytes)
            pad: Optional padding/IV (typically 0x00 for RC4)

        Returns:
            Derived encryption key (20 bytes from SHA-1)

        """
        if len(info_hash) != 20:
            msg = f"Info hash must be 20 bytes, got {len(info_hash)}"
            raise ValueError(msg)

        if pad is None:
            pad = b"\x00" * 20  # Default padding for RC4

        # BEP 3 key derivation: SHA1(secret + S + info_hash)
        # Where S is the pad
        # Note: SHA-1 is required by BEP 3 specification for key derivation
        # See BEP 3: key = SHA1(secret + S + info_hash)
        digest = hashlib.sha1()  # nosec B324 - Required by BEP 3 spec
        digest.update(shared_secret)
        digest.update(pad)
        digest.update(info_hash)
        return digest.digest()

    def get_public_key_bytes(self, keypair: DHKeyPair) -> bytes:
        """Get public key as raw bytes (for BEP 3 handshake).

        BEP 3 uses raw integer representation as bytes.

        Args:
            keypair: DH key pair

        Returns:
            Public key bytes (size depends on key_size)

        """
        # Extract public key value as integer, then convert to bytes
        public_numbers = keypair.public_key.public_numbers()
        public_value = public_numbers.y  # y is the public value

        # Calculate number of bytes needed (round up)
        num_bytes = (self.key_size + 7) // 8

        # Convert to big-endian bytes
        return public_value.to_bytes(num_bytes, byteorder="big")

    def public_key_from_bytes(
        self, public_bytes: bytes, private_key: dh.DHPrivateKey
    ) -> dh.DHPublicKey:
        """Reconstruct public key from raw bytes.

        Args:
            public_bytes: Public key as raw bytes (big-endian integer)
            private_key: Our private key (provides parameters)

        Returns:
            Reconstructed public key

        """
        # Convert bytes to integer
        public_value = int.from_bytes(public_bytes, byteorder="big")

        # Create public numbers using our private key's parameters
        parameter_numbers = private_key.parameters().parameter_numbers()
        public_numbers = dh.DHPublicNumbers(public_value, parameter_numbers)

        # Create public key
        return public_numbers.public_key(default_backend())
