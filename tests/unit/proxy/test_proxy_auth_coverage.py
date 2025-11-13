"""Additional tests for proxy auth to improve coverage.

Targets missing coverage paths in ccbt/proxy/auth.py.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

try:
    from cryptography.fernet import Fernet

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    Fernet = None  # type: ignore[assignment, misc]

from ccbt.proxy.auth import (
    CredentialStore,
    ProxyAuth,
    parse_proxy_authenticate,
)
from ccbt.proxy.exceptions import ProxyAuthError, ProxyConfigurationError


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestParseProxyAuthenticateCoverage:
    """Additional tests for parse_proxy_authenticate edge cases."""

    def test_parse_realm_no_quotes_with_space(self):
        """Test parsing realm without quotes that has space."""
        header = "Basic realm=Test Realm"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        # Should extract up to space
        assert "realm" in result

    def test_parse_realm_no_quotes_no_space(self):
        """Test parsing realm without quotes, no trailing space."""
        header = "Basic realm=TestRealm"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        assert result["realm"] == "TestRealm"

    def test_parse_no_realm_param(self):
        """Test parsing header without realm parameter."""
        header = "Basic"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        assert "realm" not in result or result.get("realm") is None


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestCredentialStoreCoverage:
    """Additional tests to cover CredentialStore edge cases."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_credential_store_init_custom_dir(self, temp_config_dir):
        """Test CredentialStore with custom config directory."""
        store = CredentialStore(config_dir=temp_config_dir)
        assert store.config_dir == temp_config_dir
        assert store.key_file == temp_config_dir / ".proxy_key"

    def test_get_or_create_key_file_exists_read_error(self, temp_config_dir):
        """Test _get_or_create_key when file exists but read fails."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Create key file
        store.key_file.write_bytes(b"dummy key")
        
        # Mock read_bytes using Path class method (works on Windows)
        original_read = Path.read_bytes
        key_file_str = str(store.key_file)
        
        def conditional_read(self):
            if str(self) == key_file_str:
                raise IOError("Read failed")
            return original_read(self)
        
        with patch("pathlib.Path.read_bytes", side_effect=conditional_read, autospec=False):
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.chmod"):
                with patch("ccbt.proxy.auth.Fernet") as mock_fernet:
                    mock_fernet.generate_key.return_value = b"new_key_1234567890123456789012345678"
                    # Should generate new key
                    key = store._get_or_create_key()
                    assert key is not None
                    assert len(key) > 0

    def test_get_or_create_key_write_error(self, temp_config_dir):
        """Test _get_or_create_key when write fails."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Delete key file if exists
        if store.key_file.exists():
            store.key_file.unlink()
        
        # Mock write_bytes using Path class method (works on Windows)
        original_write = Path.write_bytes
        key_file_str = str(store.key_file)
        
        def conditional_write(self, data):
            if str(self) == key_file_str:
                raise IOError("Write failed")
            return original_write(self, data)
        
        with patch("pathlib.Path.write_bytes", side_effect=conditional_write, autospec=False):
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.chmod"):
                with patch("ccbt.proxy.auth.Fernet") as mock_fernet:
                    mock_fernet.generate_key.return_value = b"new_key_1234567890123456789012345678"
                    # Should raise ProxyConfigurationError on write failure
                    with pytest.raises(ProxyConfigurationError):
                        store._get_or_create_key()

    def test_encrypt_credentials(self, temp_config_dir):
        """Test encrypt_credentials method."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("user", "pass")
        assert encrypted is not None
        assert len(encrypted) > 0
        # Should be base64-encoded
        try:
            base64.b64decode(encrypted)
        except Exception:
            pytest.fail("Encrypted credentials should be base64-encoded")

    def test_decrypt_credentials_success(self, temp_config_dir):
        """Test decrypt_credentials successful path."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("user", "pass")
        username, password = store.decrypt_credentials(encrypted)
        assert username == "user"
        assert password == "pass"

    def test_decrypt_credentials_base64_error(self, temp_config_dir):
        """Test decrypt_credentials with base64 decode error."""
        store = CredentialStore(config_dir=temp_config_dir)
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials("invalid-base64!!!")

    def test_decrypt_credentials_decrypt_error(self, temp_config_dir):
        """Test decrypt_credentials with decryption error."""
        store = CredentialStore(config_dir=temp_config_dir)
        # Create invalid encrypted data (wrong key)
        invalid_data = b"not_valid_encrypted"
        invalid_encrypted = base64.b64encode(invalid_data).decode("ascii")
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials(invalid_encrypted)

    def test_decrypt_credentials_decode_error(self, temp_config_dir):
        """Test decrypt_credentials with UTF-8 decode error."""
        store = CredentialStore(config_dir=temp_config_dir)
        # Encrypt non-UTF8 data
        invalid_data = b"\xff\xfe\xfd"
        encrypted = store.cipher.encrypt(invalid_data)
        encrypted_str = base64.b64encode(encrypted).decode("ascii")
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials(encrypted_str)


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestProxyAuthCoverage:
    """Additional tests to cover ProxyAuth edge cases."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_proxy_auth_init_with_store(self, temp_config_dir):
        """Test ProxyAuth initialization with provided credential store."""
        store = CredentialStore(config_dir=temp_config_dir)
        auth = ProxyAuth(credential_store=store)
        assert auth.credential_store is store

    @pytest.mark.asyncio
    async def test_handle_challenge_no_username_password(self):
        """Test handle_challenge when no credentials provided."""
        auth = ProxyAuth()
        result = await auth.handle_challenge("Basic realm=\"Proxy\"")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_challenge_unsupported_scheme(self):
        """Test handle_challenge with unsupported scheme."""
        auth = ProxyAuth()
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            result = await auth.handle_challenge("Digest realm=\"Proxy\"", "user", "pass")
            assert result is None
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_challenge_empty_scheme(self):
        """Test handle_challenge with empty scheme."""
        auth = ProxyAuth()
        result = await auth.handle_challenge("", "user", "pass")
        assert result is None

    def test_update_credentials_logs(self):
        """Test update_credentials logs correctly."""
        auth = ProxyAuth()
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            auth.update_credentials("newuser", "newpass")
            mock_logger.debug.assert_called_once()
            assert "newuser" in str(mock_logger.debug.call_args)

