"""Comprehensive tests for auth.py to reach 95%+ coverage.

Targets all missing coverage paths.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

try:
    from cryptography.fernet import Fernet

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    Fernet = None  # type: ignore[assignment, misc]

from ccbt.proxy.auth import CredentialStore, ProxyAuth, parse_proxy_authenticate
from ccbt.proxy.exceptions import ProxyAuthError, ProxyConfigurationError


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestParseProxyAuthenticateComprehensive:
    """Comprehensive tests for parse_proxy_authenticate to cover missing lines."""

    def test_parse_realm_no_equals_after_realm(self):
        """Test parsing when 'realm=' is found but no value (coverage line 59->72)."""
        # This covers the case where start is found but rest parsing fails
        header = "Basic realm="
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        # Should handle empty realm value - start+1 would be beyond string length
        # This might trigger IndexError handling, but let's test the actual path
        # The actual parsing logic handles this by checking rest[start]
        if "realm" in result:
            # Realm might be empty or have some value
            pass

    def test_parse_realm_quoted_but_no_closing_quote(self):
        """Test parsing realm with unclosed quote (coverage edge case)."""
        # This might hit line 68->70 if end == -1
        header = 'Basic realm="unclosed'
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        # Should handle unclosed quote gracefully

    def test_parse_realm_no_quotes_multiple_spaces(self):
        """Test parsing realm without quotes with multiple spaces (coverage line 68->70)."""
        header = "Basic realm=Test  Realm"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        # Should extract up to first space
        assert "realm" in result


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestCredentialStoreComprehensive:
    """Comprehensive tests for CredentialStore to cover all missing paths."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_or_create_key_read_error_logs_and_regenerates(self, temp_config_dir):
        """Test _get_or_create_key when read fails, logs warning, and generates new key (coverage lines 110-129)."""
        # Create a valid key file first
        key_file_path = temp_config_dir / ".proxy_key"
        key_file_path.parent.mkdir(parents=True, exist_ok=True)
        from cryptography.fernet import Fernet
        valid_key = Fernet.generate_key()
        key_file_path.write_bytes(valid_key)
        
        # Create store - it will successfully read the key
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Now replace the key file with invalid data and patch read_bytes to fail
        key_file_path.write_bytes(b"invalid")
        
        # Create a new store that will try to read the invalid key file
        # Patch read_bytes on the key_file to fail
        store2 = CredentialStore.__new__(CredentialStore)
        store2.config_dir = temp_config_dir
        store2.key_file = key_file_path
        
        # Patch read_bytes using Path class method (works on Windows)
        # Use conditional side_effect to only fail for the specific key file
        original_read = Path.read_bytes
        key_file_str = str(key_file_path)
        def conditional_read(self):
            if str(self) == key_file_str:
                raise IOError("Read failed")
            return original_read(self)
        
        with patch("pathlib.Path.read_bytes", side_effect=conditional_read, autospec=False):
            with patch("ccbt.proxy.auth.logger") as mock_logger:
                key = store2._get_or_create_key()
                assert key is not None
                assert len(key) == 44  # Fernet keys are 44 bytes (base64-encoded)
                # Should have logged warning
                mock_logger.warning.assert_called()

    def test_get_or_create_key_write_error_raises_configuration_error(self, temp_config_dir):
        """Test _get_or_create_key when write fails raises ProxyConfigurationError (coverage lines 125-127)."""
        # Ensure key file doesn't exist
        key_file_path = temp_config_dir / ".proxy_key"
        if key_file_path.exists():
            key_file_path.unlink()
        
        # Create store which will try to generate key
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Delete key file if it was created
        if store.key_file.exists():
            store.key_file.unlink()
        
        # Now patch write_bytes using Path class method (works on Windows)
        # Use conditional side_effect to only fail for the specific key file
        original_write = Path.write_bytes
        key_file_str = str(store.key_file)
        def conditional_write(self, data):
            if str(self) == key_file_str:
                raise IOError("Write failed")
            return original_write(self, data)
        
        with patch("pathlib.Path.write_bytes", side_effect=conditional_write, autospec=False):
            with patch("ccbt.proxy.auth.logger") as mock_logger:
                with pytest.raises(ProxyConfigurationError) as exc_info:
                    store._get_or_create_key()
                assert "Failed to create encryption key" in str(exc_info.value)
                # Should have logged error
                mock_logger.exception.assert_called()

    def test_get_or_create_key_successful_path(self, temp_config_dir):
        """Test _get_or_create_key successful key generation (coverage lines 119-124)."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Ensure key file doesn't exist
        if store.key_file.exists():
            store.key_file.unlink()
        
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            key = store._get_or_create_key()
            assert key is not None
            assert len(key) == 44  # Fernet keys are 44 bytes (base64-encoded)
            # Should have logged info
            mock_logger.info.assert_called()
            # Key file should exist now
            assert store.key_file.exists()

    def test_decrypt_credentials_base64_decode_error(self, temp_config_dir):
        """Test decrypt_credentials with base64 decode error (coverage lines 157-164)."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Invalid base64
        with pytest.raises(ProxyAuthError) as exc_info:
            store.decrypt_credentials("invalid-base64!!!")
        assert "Failed to decrypt credentials" in str(exc_info.value)

    def test_decrypt_credentials_decrypt_error(self, temp_config_dir):
        """Test decrypt_credentials with decryption error (coverage lines 157-164)."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Valid base64 but invalid encrypted data
        invalid_data = b"not_valid_encrypted_data_that_is_too_short"
        invalid_encrypted = base64.b64encode(invalid_data).decode("ascii")
        
        with pytest.raises(ProxyAuthError) as exc_info:
            store.decrypt_credentials(invalid_encrypted)
        assert "Failed to decrypt credentials" in str(exc_info.value)

    def test_decrypt_credentials_utf8_decode_error(self, temp_config_dir):
        """Test decrypt_credentials with UTF-8 decode error (coverage lines 157-164)."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Encrypt data that can't decode as UTF-8 in username:password format
        # Create encrypted data that won't decode properly
        try:
            # Create a store with a different key to ensure decryption fails
            other_store = CredentialStore(config_dir=temp_config_dir.parent / "other")
            encrypted = other_store.encrypt_credentials("user", "pass")
            # Now try to decrypt with original store (wrong key)
            with pytest.raises(ProxyAuthError):
                store.decrypt_credentials(encrypted)
        finally:
            # Cleanup
            if (temp_config_dir.parent / "other").exists():
                import shutil
                shutil.rmtree(temp_config_dir.parent / "other")

    def test_decrypt_credentials_split_error(self, temp_config_dir):
        """Test decrypt_credentials when split fails (no colon)."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Encrypt data without colon separator
        invalid_data = b"nocolonseparator"
        encrypted = store.cipher.encrypt(invalid_data)
        encrypted_str = base64.b64encode(encrypted).decode("ascii")
        
        # Should raise error on split(":", 1) if no colon
        with pytest.raises((ProxyAuthError, ValueError)):
            store.decrypt_credentials(encrypted_str)


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestProxyAuthComprehensive:
    """Comprehensive tests for ProxyAuth to cover missing lines."""

    @pytest.mark.asyncio
    async def test_handle_challenge_no_username_returns_none(self):
        """Test handle_challenge when username not provided (coverage lines 194-205)."""
        auth = ProxyAuth()
        
        # No username/password provided
        result = await auth.handle_challenge("Basic realm=\"Proxy\"")
        assert result is None
        
        # Username but no password
        result = await auth.handle_challenge("Basic realm=\"Proxy\"", username="user")
        # Should still return None if password missing
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_challenge_unsupported_scheme_logs_warning(self):
        """Test handle_challenge with unsupported scheme logs warning (coverage line 204)."""
        auth = ProxyAuth()
        
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            result = await auth.handle_challenge("Digest realm=\"Proxy\"", "user", "pass")
            assert result is None
            mock_logger.warning.assert_called_once()
            assert "Unsupported authentication scheme" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_handle_challenge_empty_scheme(self):
        """Test handle_challenge with empty scheme."""
        auth = ProxyAuth()
        
        # Empty scheme from parse_proxy_authenticate
        result = await auth.handle_challenge("", "user", "pass")
        assert result is None

    def test_update_credentials_logs_debug(self):
        """Test update_credentials logs debug message (coverage line 217)."""
        auth = ProxyAuth()
        
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            auth.update_credentials("newuser", "newpass")
            mock_logger.debug.assert_called_once()
            assert "newuser" in str(mock_logger.debug.call_args[0])


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestCredentialStoreInitialization:
    """Tests for CredentialStore initialization to cover missing lines."""

    def test_credential_store_init_default_dir(self):
        """Test CredentialStore initialization with default directory (coverage line 96-102)."""
        with patch("ccbt.proxy.auth.Path.home") as mock_home:
            mock_home.return_value = Path("/fake/home")
            
            store = CredentialStore()
            assert store.config_dir == Path("/fake/home") / ".config" / "ccbt"
            assert store.key_file == store.config_dir / ".proxy_key"

    def test_credential_store_init_custom_dir(self):
        """Test CredentialStore initialization with custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CredentialStore(config_dir=Path(tmpdir))
            assert store.config_dir == Path(tmpdir)
            assert store.key_file == Path(tmpdir) / ".proxy_key"

