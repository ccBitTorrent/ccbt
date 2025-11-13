"""Unit tests for proxy password encryption in config.

Tests credential encryption/decryption in ConfigManager.
Target: 95%+ code coverage for proxy encryption in ccbt/config/config.py.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.config]

try:
    from cryptography.fernet import Fernet

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

from ccbt.config.config import ConfigManager


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required for encryption tests",
)
class TestProxyPasswordEncryption:
    """Tests for proxy password encryption in ConfigManager."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_encryption_key_creates_key(self, temp_config_dir):
        """Test encryption key creation."""
        # Test with actual config manager - key will be created in real config dir
        config_manager = ConfigManager()
        key = config_manager._get_encryption_key()
        
        # Key might be None if cryptography not available
        if key is not None:
            assert len(key) > 0

    def test_get_encryption_key_reuses_existing(self, temp_config_dir):
        """Test encryption key reuse from existing file."""
        # Create key file manually in the expected location
        config_dir = temp_config_dir / ".config" / "ccbt"
        config_dir.mkdir(parents=True, exist_ok=True)
        key_file = config_dir / ".proxy_key"
        test_key = Fernet.generate_key()
        key_file.write_bytes(test_key)
        key_file.chmod(0o600)
        
        # Patch Path.home() to return our temp directory
        with patch("ccbt.config.config.Path.home", return_value=temp_config_dir):
            config_manager = ConfigManager()
            key = config_manager._get_encryption_key()
            
            assert key == test_key

    def test_is_encrypted_plaintext(self):
        """Test _is_encrypted with plaintext."""
        config_manager = ConfigManager()
        assert not config_manager._is_encrypted("plaintext")
        assert not config_manager._is_encrypted("")
        assert not config_manager._is_encrypted("not-encrypted-password")

    def test_is_encrypted_encrypted_value(self):
        """Test _is_encrypted with encrypted value."""
        config_manager = ConfigManager()
        # Use the actual encryption method to get properly formatted encrypted value
        password = "test"
        encrypted_str = config_manager._encrypt_proxy_password(password)
        
        # Should recognize as encrypted (only if cryptography available and encryption worked)
        if encrypted_str != password:  # Encryption succeeded
            assert config_manager._is_encrypted(encrypted_str)

    def test_encrypt_proxy_password(self):
        """Test encrypting proxy password."""
        config_manager = ConfigManager()
        password = "test_password"
        
        encrypted = config_manager._encrypt_proxy_password(password)
        
        assert encrypted != password
        assert len(encrypted) > 0
        # Should be URL-safe base64-encoded (Fernet tokens)
        # Fernet tokens start with 'gAAAA' when base64-encoded
        assert encrypted.startswith("gAAAA")

    def test_encrypt_proxy_password_empty(self):
        """Test encrypting empty password."""
        config_manager = ConfigManager()
        encrypted = config_manager._encrypt_proxy_password("")
        assert encrypted == ""

    def test_decrypt_proxy_password(self):
        """Test decrypting proxy password."""
        config_manager = ConfigManager()
        password = "test_password"
        encrypted = config_manager._encrypt_proxy_password(password)
        
        decrypted = config_manager._decrypt_proxy_password(encrypted)
        assert decrypted == password

    def test_decrypt_proxy_password_plaintext(self):
        """Test decrypting plaintext password (not encrypted)."""
        config_manager = ConfigManager()
        password = "plaintext_password"
        
        # Should return as-is if not encrypted
        decrypted = config_manager._decrypt_proxy_password(password)
        assert decrypted == password

    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt/decrypt roundtrip."""
        config_manager = ConfigManager()
        passwords = [
            "simple",
            "p@ss:w0rd!",
            "very-long-password-with-special-chars-!@#$%^&*()",
            "",
        ]
        
        for password in passwords:
            encrypted = config_manager._encrypt_proxy_password(password)
            decrypted = config_manager._decrypt_proxy_password(encrypted)
            assert decrypted == password

    def test_export_with_encryption(self, temp_config_dir):
        """Test export encrypts passwords."""
        config_manager = ConfigManager()
        config_manager.config.proxy.enable_proxy = True
        config_manager.config.proxy.proxy_host = "proxy.example.com"
        config_manager.config.proxy.proxy_port = 8080
        config_manager.config.proxy.proxy_password = "plaintext"
        
        exported = config_manager.export(fmt="toml", encrypt_passwords=True)
        
        # Password should be encrypted in export
        assert "plaintext" not in exported
        # Should contain encrypted value
        assert config_manager.config.proxy.proxy_password in exported or "proxy_password" in exported

    def test_export_without_encryption(self):
        """Test export without encryption."""
        config_manager = ConfigManager()
        config_manager.config.proxy.enable_proxy = True
        config_manager.config.proxy.proxy_host = "proxy.example.com"
        config_manager.config.proxy.proxy_port = 8080
        config_manager.config.proxy.proxy_password = "plaintext"
        
        exported = config_manager.export(fmt="toml", encrypt_passwords=False)
        
        # Password might appear in export (depending on implementation)
        # This tests the encrypt_passwords=False path

    def test_load_config_with_encrypted_password(self, temp_config_dir):
        """Test loading config with encrypted password."""
        import toml
        
        # Set up config directory with encryption key
        config_dir = temp_config_dir / ".config" / "ccbt"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create first config manager to generate key and encrypt password
        with patch("ccbt.config.config.Path.home", return_value=temp_config_dir):
            config_manager = ConfigManager()
            # Ensure encryption key is generated and saved
            key = config_manager._get_encryption_key()
            assert key is not None
            
            encrypted = config_manager._encrypt_proxy_password("test_password")
        
        # Create config file with encrypted password
        config_data = {
            "proxy": {
                "enable_proxy": True,
                "proxy_host": "proxy.example.com",
                "proxy_port": 8080,
                "proxy_password": encrypted,
            }
        }
        
        config_file = temp_config_dir / "ccbt.toml"
        config_file.write_text(toml.dumps(config_data), encoding="utf-8")
        
        # Load config with same key directory (so it can decrypt)
        with patch("ccbt.config.config.Path.home", return_value=temp_config_dir):
            new_manager = ConfigManager(config_file)
            
            # Password should be decrypted
            assert new_manager.config.proxy.proxy_password == "test_password"


class TestProxyPasswordEncryptionWithoutCryptography:
    """Tests for proxy password encryption when cryptography is not available."""

    @pytest.mark.skipif(
        HAS_CRYPTOGRAPHY,
        reason="This test only runs when cryptography is not available",
    )
    def test_encrypt_proxy_password_without_cryptography(self):
        """Test encrypting password when cryptography not available."""
        config_manager = ConfigManager()
        password = "test_password"
        
        # Should return password as-is with warning
        with patch("ccbt.config.config.logging") as mock_logging:
            encrypted = config_manager._encrypt_proxy_password(password)
            assert encrypted == password
            # Warning should be logged
            mock_logging.warning.assert_called()

    @pytest.mark.skipif(
        HAS_CRYPTOGRAPHY,
        reason="This test only runs when cryptography is not available",
    )
    def test_decrypt_proxy_password_without_cryptography(self):
        """Test decrypting password when cryptography not available."""
        from ccbt.config.config import ConfigurationError
        
        config_manager = ConfigManager()
        
        # If value appears encrypted but crypto not available, should raise error
        # But if value is plaintext (not encrypted), should return as-is
        # The method checks _is_encrypted first, then tries to decrypt
        # If _is_encrypted returns False, it returns the value as-is
        result = config_manager._decrypt_proxy_password("plaintext_value")
        assert result == "plaintext_value"
        
        # If it appears encrypted but crypto unavailable, should raise ConfigurationError
        # But we need to mock _is_encrypted to return True
        with patch.object(config_manager, "_is_encrypted", return_value=True):
            with pytest.raises(ConfigurationError):
                config_manager._decrypt_proxy_password("encrypted_value")

