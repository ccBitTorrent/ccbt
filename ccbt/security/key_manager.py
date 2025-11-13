"""Ed25519 Key Manager for ccBitTorrent.

from __future__ import annotations

Provides secure generation, storage, and management of Ed25519 key pairs
for cryptographic authentication and signing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    Fernet = None  # type: ignore[assignment, misc]
    ed25519 = None  # type: ignore[assignment, misc]
    Encoding = None  # type: ignore[assignment, misc]
    PrivateFormat = None  # type: ignore[assignment, misc]
    PublicFormat = None  # type: ignore[assignment, misc]
    NoEncryption = None  # type: ignore[assignment, misc]

from ccbt.utils.logging_config import get_logger

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

logger = get_logger(__name__)


class Ed25519KeyManagerError(Exception):
    """Base exception for Ed25519 key manager errors."""


class Ed25519KeyManager:
    """Manages Ed25519 key pairs with secure storage.

    Generates, stores, and manages Ed25519 key pairs for cryptographic
    authentication. Private keys are encrypted using Fernet before storage.
    """

    def __init__(self, key_dir: Path | str | None = None):
        """Initialize key manager.

        Args:
            key_dir: Directory to store keys (defaults to ~/.ccbt/keys)

        Raises:
            Ed25519KeyManagerError: If cryptography library not available

        """
        if not CRYPTOGRAPHY_AVAILABLE:
            msg = (
                "cryptography library is required for Ed25519 keys. "
                "Install with: pip install cryptography"
            )
            raise Ed25519KeyManagerError(msg)

        if key_dir is None:
            key_dir = Path.home() / ".ccbt" / "keys"
        elif isinstance(key_dir, str):
            key_dir = Path(key_dir).expanduser()

        self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)

        # Key file paths
        self.private_key_file = self.key_dir / "ed25519_private_key.enc"
        self.public_key_file = self.key_dir / "ed25519_public_key.pem"
        self.encryption_key_file = Path.home() / ".ccbt" / ".key_encryption_key"

        # Initialize encryption cipher
        self.cipher = self._get_or_create_encryption_key()

        # Key pair (loaded on demand)
        self._private_key: Ed25519PrivateKey | None = None
        self._public_key: Ed25519PublicKey | None = None

    def _get_or_create_encryption_key(self) -> Fernet:
        """Get or create encryption key for private key storage.

        Returns:
            Fernet cipher instance

        Raises:
            Ed25519KeyManagerError: If key creation fails

        """
        if Fernet is None:
            msg = "Fernet encryption not available"
            raise Ed25519KeyManagerError(msg)

        encryption_key_dir = self.encryption_key_file.parent
        encryption_key_dir.mkdir(parents=True, exist_ok=True)

        if self.encryption_key_file.exists():
            try:
                key = self.encryption_key_file.read_bytes()
                # Validate key
                try:
                    return Fernet(key)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Invalid encryption key in file, regenerating: %s", e
                    )
                    self.encryption_key_file.unlink()
            except Exception as e:
                logger.warning("Failed to read encryption key: %s", e)

        # Generate new key
        key = Fernet.generate_key()
        try:
            self.encryption_key_file.write_bytes(key)
            self.encryption_key_file.chmod(0o600)  # Read/write for owner only
            logger.info("Generated new key encryption key")
        except Exception as e:
            logger.exception("Failed to write encryption key")
            msg = f"Failed to create encryption key: {e}"
            raise Ed25519KeyManagerError(msg) from e

        return Fernet(key)

    def generate_keypair(self) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Generate new Ed25519 key pair.

        Returns:
            Tuple of (private_key, public_key)

        Raises:
            Ed25519KeyManagerError: If key generation fails

        """
        if ed25519 is None:
            msg = "Ed25519 not available"
            raise Ed25519KeyManagerError(msg)

        try:
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            self._private_key = private_key
            self._public_key = public_key
            logger.info("Generated new Ed25519 key pair")
            return private_key, public_key
        except Exception as e:
            msg = f"Failed to generate Ed25519 key pair: {e}"
            raise Ed25519KeyManagerError(msg) from e

    def save_keypair(
        self,
        private_key: Ed25519PrivateKey | None = None,
        public_key: Ed25519PublicKey | None = None,
    ) -> None:
        """Save key pair to secure storage.

        Args:
            private_key: Private key to save (uses cached if None)
            public_key: Public key to save (uses cached if None)

        Raises:
            Ed25519KeyManagerError: If save fails

        """
        if private_key is None:
            private_key = self._private_key
        if public_key is None:
            public_key = self._public_key

        if private_key is None or public_key is None:
            msg = "No key pair to save"
            raise Ed25519KeyManagerError(msg)

        try:
            # Encrypt and save private key
            private_key_bytes = private_key.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
            encrypted_private = self.cipher.encrypt(private_key_bytes)
            self.private_key_file.write_bytes(encrypted_private)
            self.private_key_file.chmod(0o600)  # Read/write for owner only

            # Save public key in PEM format (plaintext is safe)
            public_key_pem = public_key.public_bytes(
                encoding=Encoding.PEM,
                format=PublicFormat.SubjectPublicKeyInfo,
            )
            self.public_key_file.write_bytes(public_key_pem)
            self.public_key_file.chmod(0o644)  # Readable by owner and group

            logger.info("Saved Ed25519 key pair to secure storage")
        except Exception as e:
            logger.exception("Failed to save key pair")
            msg = f"Failed to save key pair: {e}"
            raise Ed25519KeyManagerError(msg) from e

    def load_keypair(self) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Load key pair from secure storage.

        Returns:
            Tuple of (private_key, public_key)

        Raises:
            Ed25519KeyManagerError: If keys not found or load fails

        """
        if ed25519 is None:
            msg = "Ed25519 not available"
            raise Ed25519KeyManagerError(msg)

        if not self.private_key_file.exists() or not self.public_key_file.exists():
            msg = "Key pair not found in storage"
            raise Ed25519KeyManagerError(msg)

        try:
            # Load and decrypt private key
            encrypted_private = self.private_key_file.read_bytes()
            private_key_bytes = self.cipher.decrypt(encrypted_private)
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
                private_key_bytes
            )

            # Load public key (saved as PEM format)
            public_key_bytes = self.public_key_file.read_bytes()
            try:
                # Try loading as PEM (this is how we save it)
                from cryptography.hazmat.primitives.serialization import (
                    load_pem_public_key,
                )

                public_key = load_pem_public_key(public_key_bytes)
                if not isinstance(public_key, ed25519.Ed25519PublicKey):
                    raise ValueError("Not an Ed25519 public key")
            except Exception as pem_error:
                # Fall back to raw bytes (32 bytes) for backward compatibility
                # This handles the case where the key was saved in raw format
                try:
                    if len(public_key_bytes) == 32:
                        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
                            public_key_bytes
                        )
                    else:
                        # If neither PEM nor raw 32 bytes, re-raise the original PEM error
                        raise ValueError(
                            f"Invalid public key format: {len(public_key_bytes)} bytes. "
                            f"PEM load error: {pem_error}"
                        ) from pem_error
                except Exception as raw_error:
                    # If raw loading also fails, raise with both errors
                    raise ValueError(
                        f"Failed to load public key as PEM or raw bytes. "
                        f"PEM error: {pem_error}, Raw error: {raw_error}"
                    ) from raw_error

            self._private_key = private_key
            self._public_key = public_key

            logger.info("Loaded Ed25519 key pair from secure storage")
            return private_key, public_key
        except Exception as e:
            logger.exception("Failed to load key pair")
            msg = f"Failed to load key pair: {e}"
            raise Ed25519KeyManagerError(msg) from e

    def get_or_create_keypair(
        self,
    ) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Get existing key pair or generate new one.

        Returns:
            Tuple of (private_key, public_key)

        """
        if self._private_key is not None and self._public_key is not None:
            return self._private_key, self._public_key

        try:
            return self.load_keypair()
        except Ed25519KeyManagerError:
            # Keys don't exist, generate new ones
            private_key, public_key = self.generate_keypair()
            self.save_keypair(private_key, public_key)
            return private_key, public_key

    def get_public_key_bytes(self) -> bytes:
        """Get public key as raw 32-byte format.

        Returns:
            32-byte public key

        Raises:
            Ed25519KeyManagerError: If key not available

        """
        if self._public_key is None:
            _, self._public_key = self.get_or_create_keypair()

        if self._public_key is None:
            msg = "Public key not available"
            raise Ed25519KeyManagerError(msg)

        return self._public_key.public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )

    def get_public_key_hex(self) -> str:
        """Get public key as hex string for configuration.

        Returns:
            Hex-encoded public key (64 characters)

        Raises:
            Ed25519KeyManagerError: If key not available

        """
        return self.get_public_key_bytes().hex()

    def get_private_key_bytes(self) -> bytes:
        """Get private key as raw 32-byte format.

        Returns:
            32-byte private key

        Raises:
            Ed25519KeyManagerError: If key not available or extraction fails

        """
        if self._private_key is None:
            self._private_key, _ = self.get_or_create_keypair()

        if self._private_key is None:
            msg = "Private key not available"
            raise Ed25519KeyManagerError(msg)

        try:
            # Extract private key bytes using same encoding as save_keypair()
            return self._private_key.private_bytes(
                encoding=Encoding.Raw,
                format=PrivateFormat.Raw,
                encryption_algorithm=NoEncryption(),
            )
        except Exception as e:
            msg = f"Failed to extract private key bytes: {e}"
            raise Ed25519KeyManagerError(msg) from e

    def sign_message(self, message: bytes) -> bytes:
        """Sign a message with the private key.

        Args:
            message: Message bytes to sign

        Returns:
            Signature bytes (64 bytes)

        Raises:
            Ed25519KeyManagerError: If signing fails

        """
        if self._private_key is None:
            self._private_key, _ = self.get_or_create_keypair()

        if self._private_key is None:
            msg = "Private key not available"
            raise Ed25519KeyManagerError(msg)

        try:
            return self._private_key.sign(message)
        except Exception as e:
            msg = f"Failed to sign message: {e}"
            raise Ed25519KeyManagerError(msg) from e

    @staticmethod
    def verify_signature(message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature against a message and public key.

        Args:
            message: Original message bytes
            signature: Signature bytes (64 bytes)
            public_key: Public key bytes (32 bytes)

        Returns:
            True if signature is valid, False otherwise

        """
        if not CRYPTOGRAPHY_AVAILABLE or ed25519 is None:
            logger.warning("Cryptography not available, cannot verify signature")
            return False

        try:
            public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
            public_key_obj.verify(signature, message)
            return True
        except Exception as e:
            logger.debug("Signature verification failed: %s", e)
            return False

    def rotate_keypair(self) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Generate new key pair and save it (key rotation).

        Returns:
            Tuple of (new_private_key, new_public_key)

        Raises:
            Ed25519KeyManagerError: If rotation fails

        """
        # Backup old keys if they exist
        if self.private_key_file.exists():
            backup_file = self.private_key_file.with_suffix(".enc.backup")
            try:
                import shutil

                shutil.copy2(self.private_key_file, backup_file)
                logger.info("Backed up old private key")
            except Exception as e:
                logger.warning("Failed to backup old key: %s", e)

        # Generate and save new key pair
        private_key, public_key = self.generate_keypair()
        self.save_keypair(private_key, public_key)
        logger.info("Rotated Ed25519 key pair")
        return private_key, public_key
