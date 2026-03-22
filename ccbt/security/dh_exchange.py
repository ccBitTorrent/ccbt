"""Diffie-Hellman key material for BEP 3 MSE/PE peer obfuscation.

768-bit or 1024-bit groups and SHA-1-based derivation as used in the
ecosystem MSE/PE handshake. This establishes shared stream keys for
interoperability, not authenticated peer identity.
"""

from __future__ import annotations

import hashlib
from typing import Literal, NamedTuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dh


class DHKeyPair(NamedTuple):
    """Diffie-Hellman key pair."""

    private_key: dh.DHPrivateKey
    public_key: dh.DHPublicKey


class DHPeerExchange:
    """Diffie-Hellman key exchange for peer connections."""

    # Well-known Oakley MODP group values used by BEP 3 and compatible
    # clients.
    _DH_768_PRIME_HEX = (
        "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA"
        "63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51"
        "C245E485B576625E7EC6F44C42E9A63A3620FFFFFFFFFFFFFFFF"
    )
    _DH_1024_PRIME_HEX = (
        "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA"
        "63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51"
        "C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5"
        "AE9F24117C4B1FE649286651ECE65381FFFFFFFFFFFFFFFF"
    )
    _DH_GENERATOR = 2
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
        # Load embedded well-known Oakley parameters on first use and cache.
        if key_size == 768:
            if cls._DH_768_PARAMS is None:
                dh_numbers = dh.DHParameterNumbers(
                    p=int(cls._DH_768_PRIME_HEX, 16), g=cls._DH_GENERATOR
                )
                cls._DH_768_PARAMS = dh_numbers.parameters(default_backend())
            return cls._DH_768_PARAMS

        if key_size == 1024:
            if cls._DH_1024_PARAMS is None:
                dh_numbers = dh.DHParameterNumbers(
                    p=int(cls._DH_1024_PRIME_HEX, 16), g=cls._DH_GENERATOR
                )
                cls._DH_1024_PARAMS = dh_numbers.parameters(default_backend())
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
        direction: Literal["outbound", "inbound"] = "outbound",
    ) -> bytes:
        """Derive directional encryption key material from shared secret.

        MSE/PE uses directional labels:
        - Outbound stream (our-to-peer): HASH("keyA" + S + SKEY)
        - Inbound stream (peer-to-our): HASH("keyB" + S + SKEY)

        Args:
            shared_secret: Shared secret from DH exchange
            info_hash: Torrent info hash (20 bytes)
            direction: Cipher direction from local perspective.

        Returns:
            Derived encryption key (20 bytes from SHA-1)

        """
        if len(info_hash) != 20:
            msg = f"Info hash must be 20 bytes, got {len(info_hash)}"
            raise ValueError(msg)

        if direction not in {"outbound", "inbound"}:
            msg = f"Direction must be 'outbound' or 'inbound', got {direction}"
            raise ValueError(msg)

        # Directional key derivation required by BEP 3 and compatible peers.
        # We preserve legacy `derive_encryption_key` naming for compatibility while
        # making direction explicit.
        label = b"keyA" if direction == "outbound" else b"keyB"
        digest = hashlib.sha1()  # nosec B324 - Required by BEP 3 spec
        digest.update(label)
        digest.update(shared_secret)
        digest.update(info_hash)
        return digest.digest()

    def derive_stream_keys(
        self, shared_secret: bytes, info_hash: bytes
    ) -> tuple[bytes, bytes]:
        """Derive both directional keys for a negotiated session.

        Returns:
            (outbound_key, inbound_key)
        """
        outbound_key = self.derive_encryption_key(
            shared_secret, info_hash, direction="outbound"
        )
        inbound_key = self.derive_encryption_key(
            shared_secret, info_hash, direction="inbound"
        )
        return outbound_key, inbound_key

    def derive_transcript_keys(
        self, shared_secret: bytes, info_hash: bytes
    ) -> tuple[bytes, bytes]:
        """Compatibility wrapper for directional key derivation.

        Mirrors historical naming used by the MSE transcript implementation and
        returns (keyA, keyB).
        """
        key_a = self.derive_encryption_key(
            shared_secret, info_hash, direction="outbound"
        )
        key_b = self.derive_encryption_key(
            shared_secret, info_hash, direction="inbound"
        )
        return key_a, key_b

    def req1_hash(self, shared_secret: bytes) -> bytes:
        r"""Compute HASH(\"req1\" + S) for transcript validation."""
        digest = hashlib.sha1()  # nosec B324 - Required by BEP 3
        digest.update(b"req1")
        digest.update(shared_secret)
        return digest.digest()

    def req2_hash(self, info_hash: bytes) -> bytes:
        r"""Compute HASH(\"req2\" + SKEY)."""
        if len(info_hash) != 20:
            msg = f"Info hash must be 20 bytes, got {len(info_hash)}"
            raise ValueError(msg)

        digest = hashlib.sha1()  # nosec B324 - Required by BEP 3
        digest.update(b"req2")
        digest.update(info_hash)
        return digest.digest()

    def req3_hash(self, shared_secret: bytes) -> bytes:
        r"""Compute HASH(\"req3\" + S)."""
        digest = hashlib.sha1()  # nosec B324 - Required by BEP 3
        digest.update(b"req3")
        digest.update(shared_secret)
        return digest.digest()

    def verification_constant(self) -> bytes:
        """Return the verification constant used in transcript exchanges."""
        return b"\x00" * 8

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
