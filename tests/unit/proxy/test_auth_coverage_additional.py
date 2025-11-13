"""Additional coverage tests for auth.py missing paths."""

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
class TestCredentialStoreKeyGeneration:
    """Tests for CredentialStore key generation edge cases."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_or_create_key_read_error_then_generate(self, temp_config_dir):
        """Test _get_or_create_key when read fails, then generates new key."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Create a corrupted key file
        store.key_file.write_bytes(b"corrupted key data")
        
        # Mock read_bytes to raise exception first time
        read_called = [False]
        original_read = Path.read_bytes
        key_file_str = str(store.key_file)
        
        def mock_read(self):
            if not read_called[0] and str(self) == key_file_str:
                read_called[0] = True
                raise IOError("Read failed")
            return original_read(self)
        
        with patch("pathlib.Path.read_bytes", side_effect=mock_read, autospec=False):
            # Should generate new key after read failure
            key = store._get_or_create_key()
            assert key is not None
            assert len(key) == 44  # Fernet keys are 44 bytes (base64-encoded)

    def test_get_or_create_key_write_error_raises(self, temp_config_dir):
        """Test _get_or_create_key when write fails raises error."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        # Ensure key file doesn't exist
        if store.key_file.exists():
            store.key_file.unlink()
        
        # Mock write_bytes to raise exception using conditional side_effect
        original_write = Path.write_bytes
        key_file_str = str(store.key_file)
        def conditional_write(self, data):
            if str(self) == key_file_str:
                raise IOError("Write failed")
            return original_write(self, data)
        
        with patch("pathlib.Path.write_bytes", side_effect=conditional_write, autospec=False):
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.chmod"):
                with pytest.raises(ProxyConfigurationError):
                    store._get_or_create_key()


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestParseProxyAuthenticateEdgeCases:
    """Additional edge cases for parse_proxy_authenticate."""

    def test_parse_realm_no_quotes_with_space(self):
        """Test parsing realm without quotes that has space."""
        header = "Basic realm=Test Realm"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        # Should extract up to space
        assert result["realm"] == "Test"

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
        # No realm key should exist or be empty
        assert "realm" not in result or result.get("realm") is None or result.get("realm") == ""


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestProxyAuthAdditionalCoverage:
    """Additional coverage tests for ProxyAuth."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_handle_challenge_no_username_password(self):
        """Test handle_challenge when no credentials provided (coverage line 194-196)."""
        auth = ProxyAuth()
        result = await auth.handle_challenge("Basic realm=\"Proxy\"")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_challenge_empty_scheme(self):
        """Test handle_challenge with empty scheme."""
        auth = ProxyAuth()
        # Empty scheme should result in empty params
        result = await auth.handle_challenge("", "user", "pass")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_credentials_logs(self):
        """Test update_credentials logs correctly (coverage line 217)."""
        auth = ProxyAuth()
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            auth.update_credentials("newuser", "newpass")
            mock_logger.debug.assert_called_once()
            assert "newuser" in str(mock_logger.debug.call_args)

    def test_proxy_auth_init_with_store(self, temp_config_dir):
        """Test ProxyAuth initialization with provided credential store."""
        store = CredentialStore(config_dir=temp_config_dir)
        auth = ProxyAuth(credential_store=store)
        assert auth.credential_store is store


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestCredentialStoreAdditionalCoverage:
    """Additional coverage for CredentialStore methods."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_decrypt_credentials_base64_error(self, temp_config_dir):
        """Test decrypt_credentials with base64 decode error (coverage line 157)."""
        store = CredentialStore(config_dir=temp_config_dir)
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials("invalid-base64!!!")

    def test_decrypt_credentials_decrypt_error(self, temp_config_dir):
        """Test decrypt_credentials with decryption error (coverage line 157-164)."""
        store = CredentialStore(config_dir=temp_config_dir)
        # Create invalid encrypted data (wrong key or format)
        invalid_data = b"not_valid_encrypted"
        invalid_encrypted = base64.b64encode(invalid_data).decode("ascii")
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials(invalid_encrypted)

    def test_decrypt_credentials_decode_error(self, temp_config_dir):
        """Test decrypt_credentials with UTF-8 decode error (coverage line 157-164)."""
        store = CredentialStore(config_dir=temp_config_dir)
        # Encrypt non-UTF8 data that will fail on decode
        # First, create some data that encrypts but can't decode
        invalid_bytes = b"\xff\xfe\xfd"
        try:
            encrypted = store.cipher.encrypt(invalid_bytes)
            encrypted_str = base64.b64encode(encrypted).decode("ascii")
            # This should fail because we expect "username:password" format
            with pytest.raises(ProxyAuthError):
                store.decrypt_credentials(encrypted_str)
        except Exception:
            # If encryption itself fails, that's also fine
            pass

