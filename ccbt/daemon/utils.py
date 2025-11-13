"""Utility functions for daemon operations.

from __future__ import annotations

Provides helper functions for API key generation and validation.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from ccbt.utils.logging_config import get_logger

logger = get_logger(__name__)


def generate_api_key() -> str:
    """Generate a secure random API key.

    Returns:
        A 32-byte hex-encoded API key string

    """
    return secrets.token_hex(32)


def validate_api_key(api_key: str) -> bool:
    """Validate API key format.

    Args:
        api_key: API key to validate

    Returns:
        True if valid format, False otherwise

    """
    if not api_key:
        return False
    # API key should be 64 hex characters (32 bytes)
    if len(api_key) != 64:
        return False
    try:
        bytes.fromhex(api_key)
        return True
    except ValueError:
        return False


def migrate_api_key_to_ed25519(key_dir: Path | str | None = None) -> bool:
    """Migrate from api_key to Ed25519 keys.

    Generates Ed25519 keys if they don't exist and api_key does.
    This enables backward compatibility during transition.

    Args:
        key_dir: Directory to store Ed25519 keys (defaults to ~/.ccbt/keys)

    Returns:
        True if migration completed or keys already exist, False on error

    """
    try:
        from ccbt.security.key_manager import Ed25519KeyManager

        key_manager = Ed25519KeyManager(key_dir=key_dir)

        # Check if Ed25519 keys already exist
        if (
            key_manager.private_key_file.exists()
            and key_manager.public_key_file.exists()
        ):
            logger.debug("Ed25519 keys already exist, no migration needed")
            return True

        # Generate new Ed25519 keys
        logger.info("Migrating from api_key to Ed25519 keys...")
        key_manager.get_or_create_keypair()
        logger.info("Successfully migrated to Ed25519 keys")
        return True
    except Exception as e:
        logger.warning("Failed to migrate to Ed25519 keys: %s", e)
        return False
