"""Unit tests for proxy authentication.

Tests authentication header generation, challenge parsing, and credential encryption.
Target: 95%+ code coverage for ccbt/proxy/auth.py.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

from ccbt.proxy.auth import (
    CredentialStore,
    ProxyAuth,
    generate_basic_auth_header,
    parse_proxy_authenticate,
)
from ccbt.proxy.exceptions import ProxyAuthError, ProxyConfigurationError

# Try to import cryptography
try:
    from cryptography.fernet import Fernet

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    Fernet = None  # type: ignore[assignment, misc]


class TestGenerateBasicAuthHeader:
    """Tests for generate_basic_auth_header function."""

    def test_generate_basic_auth_header_simple(self):
        """Test generating Basic auth header with simple credentials."""
        header = generate_basic_auth_header("user", "pass")
        assert header.startswith("Basic ")
        
        # Decode and verify
        encoded = header[6:]  # Remove "Basic "
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "user:pass"

    def test_generate_basic_auth_header_special_chars(self):
        """Test generating Basic auth header with special characters."""
        header = generate_basic_auth_header("user@domain", "p@ss:w0rd!")
        assert header.startswith("Basic ")
        
        encoded = header[6:]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "user@domain:p@ss:w0rd!"

    def test_generate_basic_auth_header_unicode(self):
        """Test generating Basic auth header with Unicode characters."""
        header = generate_basic_auth_header("用户名", "密码")
        assert header.startswith("Basic ")
        
        encoded = header[6:]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "用户名:密码"

    def test_generate_basic_auth_header_empty(self):
        """Test generating Basic auth header with empty strings."""
        header = generate_basic_auth_header("", "")
        assert header.startswith("Basic ")
        
        encoded = header[6:]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == ":"


class TestParseProxyAuthenticate:
    """Tests for parse_proxy_authenticate function."""

    def test_parse_proxy_authenticate_basic(self):
        """Test parsing Basic Proxy-Authenticate header."""
        header = "Basic"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"

    def test_parse_proxy_authenticate_with_realm_quoted(self):
        """Test parsing Proxy-Authenticate with quoted realm."""
        header = 'Basic realm="Proxy Server"'
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        assert result["realm"] == "Proxy Server"

    def test_parse_proxy_authenticate_with_realm_unquoted(self):
        """Test parsing Proxy-Authenticate with unquoted realm."""
        header = "Basic realm=ProxyServer"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        assert result["realm"] == "ProxyServer"

    def test_parse_proxy_authenticate_digest(self):
        """Test parsing Digest Proxy-Authenticate header."""
        header = "Digest realm=\"test\""
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Digest"
        assert result["realm"] == "test"

    def test_parse_proxy_authenticate_no_params(self):
        """Test parsing Proxy-Authenticate without parameters."""
        header = "Basic"
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        assert "realm" not in result


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required for credential encryption tests",
)
class TestCredentialStore:
    """Tests for CredentialStore class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_credential_store_init(self, temp_config_dir):
        """Test CredentialStore initialization."""
        store = CredentialStore(config_dir=temp_config_dir)
        assert store.config_dir == temp_config_dir
        assert store.key_file == temp_config_dir / ".proxy_key"
        assert store.key is not None
        assert store.cipher is not None

    def test_credential_store_init_default_dir(self):
        """Test CredentialStore initialization with default directory."""
        with patch("ccbt.proxy.auth.Path.home") as mock_home:
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_home.return_value = Path(tmpdir)
                store = CredentialStore()
                assert store.config_dir == Path(tmpdir) / ".config" / "ccbt"

    def test_credential_store_key_creation(self, temp_config_dir):
        """Test encryption key creation."""
        import sys
        store = CredentialStore(config_dir=temp_config_dir)
        assert store.key_file.exists()
        # File permissions check only works on Unix-like systems
        if sys.platform != "win32":
            assert store.key_file.stat().st_mode & 0o077 == 0  # Only owner can read/write

    def test_credential_store_key_reuse(self, temp_config_dir):
        """Test encryption key reuse from existing file."""
        # Create first store (generates key)
        store1 = CredentialStore(config_dir=temp_config_dir)
        key1 = store1.key

        # Create second store (should reuse key)
        store2 = CredentialStore(config_dir=temp_config_dir)
        key2 = store2.key

        assert key1 == key2

    def test_credential_store_key_regeneration_on_error(self, temp_config_dir):
        """Test key regeneration when read fails."""
        # Create initial store
        store1 = CredentialStore(config_dir=temp_config_dir)
        
        # Corrupt the key file
        store1.key_file.write_bytes(b"corrupt")
        
        # Create new store (should regenerate key)
        store2 = CredentialStore(config_dir=temp_config_dir)
        assert store2.key != b"corrupt"
        assert store2.key is not None

    def test_encrypt_credentials(self, temp_config_dir):
        """Test credential encryption."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("user", "pass")
        
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        # Should be base64-encoded
        try:
            base64.b64decode(encrypted)
        except Exception:
            pytest.fail("Encrypted value should be base64-encoded")

    def test_decrypt_credentials(self, temp_config_dir):
        """Test credential decryption."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("user", "pass")
        
        username, password = store.decrypt_credentials(encrypted)
        assert username == "user"
        assert password == "pass"

    def test_encrypt_decrypt_roundtrip_special_chars(self, temp_config_dir):
        """Test encrypt/decrypt roundtrip with special characters."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("user@domain", "p@ss:w0rd!")
        
        username, password = store.decrypt_credentials(encrypted)
        assert username == "user@domain"
        assert password == "p@ss:w0rd!"

    def test_decrypt_credentials_invalid(self, temp_config_dir):
        """Test decrypting invalid encrypted data."""
        store = CredentialStore(config_dir=temp_config_dir)
        
        with pytest.raises(Exception):  # Should raise ProxyAuthError
            store.decrypt_credentials("invalid_base64_data")

    def test_decrypt_credentials_wrong_key(self, temp_config_dir):
        """Test decrypting with wrong key."""
        store1 = CredentialStore(config_dir=temp_config_dir)
        encrypted = store1.encrypt_credentials("user", "pass")
        
        # Create new store with different key
        with tempfile.TemporaryDirectory() as tmpdir2:
            store2 = CredentialStore(config_dir=Path(tmpdir2))
            with pytest.raises(Exception):  # Should raise ProxyAuthError
                store2.decrypt_credentials(encrypted)


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required for ProxyAuth tests",
)
class TestProxyAuth:
    """Tests for ProxyAuth class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_handle_challenge_basic_with_credentials(self, temp_config_dir):
        """Test handling Basic challenge with provided credentials."""
        auth = ProxyAuth()
        header = await auth.handle_challenge("Basic realm=\"Proxy\"", "user", "pass")
        
        assert header is not None
        assert header.startswith("Basic ")
        
        # Verify it's valid Basic auth
        encoded = header[6:]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "user:pass"

    @pytest.mark.asyncio
    async def test_handle_challenge_basic_no_credentials(self, temp_config_dir):
        """Test handling Basic challenge without credentials."""
        auth = ProxyAuth()
        header = await auth.handle_challenge("Basic realm=\"Proxy\"")
        
        # Should return None if no credentials provided
        assert header is None

    @pytest.mark.asyncio
    async def test_handle_challenge_unsupported_scheme(self, temp_config_dir):
        """Test handling unsupported authentication scheme."""
        auth = ProxyAuth()
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            header = await auth.handle_challenge("Digest realm=\"Proxy\"", "user", "pass")
            assert header is None
            mock_logger.warning.assert_called_once()

    def test_update_credentials(self, temp_config_dir):
        """Test updating credentials."""
        auth = ProxyAuth()
        with patch("ccbt.proxy.auth.logger") as mock_logger:
            auth.update_credentials("newuser", "newpass")
            mock_logger.debug.assert_called_once()


class TestCredentialStoreWithoutCryptography:
    """Tests for CredentialStore when cryptography is not available."""

    @pytest.mark.skipif(
        HAS_CRYPTOGRAPHY,
        reason="This test only runs when cryptography is not available",
    )
    def test_credential_store_init_without_cryptography(self):
        """Test CredentialStore raises error when cryptography not available."""
        with pytest.raises(Exception):  # Should raise ProxyConfigurationError
            CredentialStore()


@pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography library required",
)
class TestCredentialStoreEdgeCases:
    """Tests for CredentialStore edge cases."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_encrypt_decrypt_empty_password(self, temp_config_dir):
        """Test encrypting/decrypting with empty password."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("user", "")
        username, password = store.decrypt_credentials(encrypted)
        assert username == "user"
        assert password == ""

    def test_encrypt_decrypt_empty_username(self, temp_config_dir):
        """Test encrypting/decrypting with empty username."""
        store = CredentialStore(config_dir=temp_config_dir)
        encrypted = store.encrypt_credentials("", "pass")
        username, password = store.decrypt_credentials(encrypted)
        assert username == ""
        assert password == "pass"

    def test_decrypt_credentials_invalid_base64(self, temp_config_dir):
        """Test decrypting invalid base64 data."""
        store = CredentialStore(config_dir=temp_config_dir)
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials("not-base64!!!")
    
    def test_decrypt_credentials_wrong_format(self, temp_config_dir):
        """Test decrypting data that doesn't contain colon separator."""
        store = CredentialStore(config_dir=temp_config_dir)
        # Encrypt something that won't decode to user:pass format
        invalid_data = b"no-colon-here"
        encrypted = store.cipher.encrypt(invalid_data)
        encrypted_str = base64.b64encode(encrypted).decode("ascii")
        with pytest.raises(ProxyAuthError):
            store.decrypt_credentials(encrypted_str)

    def test_key_file_permissions_error(self, temp_config_dir):
        """Test handling permission errors when creating key file."""
        import sys
        
        store = CredentialStore(config_dir=temp_config_dir)
        # Delete key file
        store.key_file.unlink()
        
        # Windows handles permissions differently, so skip on Windows
        if sys.platform == "win32":
            pytest.skip("Windows file permissions work differently")
        
        # Make directory read-only (on Unix-like systems)
        try:
            temp_config_dir.chmod(0o444)  # Read-only
            # Should handle gracefully or raise appropriate error
            with pytest.raises((ProxyConfigurationError, PermissionError)):
                CredentialStore(config_dir=temp_config_dir)
        finally:
            temp_config_dir.chmod(0o755)  # Restore


class TestParseProxyAuthenticateEdgeCases:
    """Tests for parse_proxy_authenticate edge cases."""

    def test_parse_empty_string(self):
        """Test parsing empty Proxy-Authenticate header."""
        result = parse_proxy_authenticate("")
        assert result["scheme"] == ""

    def test_parse_realm_with_multiple_spaces(self):
        """Test parsing realm with multiple spaces."""
        header = 'Basic realm="Test Realm"'
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Basic"
        assert result["realm"] == "Test Realm"

    def test_parse_realm_unclosed_quote(self):
        """Test parsing realm with unclosed quote."""
        header = 'Basic realm="Test'
        result = parse_proxy_authenticate(header)
        # Should handle gracefully - might not extract realm correctly
        assert result["scheme"] == "Basic"

    def test_parse_complex_header(self):
        """Test parsing complex authentication header."""
        header = 'Digest realm="Test", qop="auth"'
        result = parse_proxy_authenticate(header)
        assert result["scheme"] == "Digest"
        # Our parser only extracts realm for now
        assert "realm" in result

