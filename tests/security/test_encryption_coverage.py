"""Additional tests for encryption.py to achieve 100% coverage.

Covers previously untested code paths and edge cases.
"""

from __future__ import annotations

import struct
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ccbt.security.encryption import (
    EncryptionConfig,
    EncryptionManager,
    EncryptionMode,
    EncryptionSession,
    EncryptionType,
)

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.mark.asyncio
async def test_encryption_config_from_security_config_with_none():
    """Test EncryptionConfig.from_security_config with None security_config."""
    # This should use global config
    with patch("ccbt.config.config.get_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.security.encryption_mode = "preferred"
        mock_config.security.encryption_allowed_ciphers = ["rc4", "aes"]
        mock_get_config.return_value = mock_config

        config = EncryptionConfig.from_security_config(None)
        assert config.mode == EncryptionMode.PREFERRED
        assert EncryptionType.RC4 in config.allowed_ciphers


@pytest.mark.asyncio
async def test_encryption_config_from_security_config_with_chacha20():
    """Test EncryptionConfig.from_security_config with chacha20 cipher."""
    mock_security_config = MagicMock()
    mock_security_config.encryption_mode = "preferred"
    mock_security_config.encryption_allowed_ciphers = ["rc4", "aes", "chacha20"]

    config = EncryptionConfig.from_security_config(mock_security_config)
    assert EncryptionType.CHACHA20 in config.allowed_ciphers


@pytest.mark.asyncio
async def test_encryption_config_from_security_config_empty_allowed():
    """Test EncryptionConfig.from_security_config with empty allowed_ciphers."""
    mock_security_config = MagicMock()
    mock_security_config.encryption_mode = "preferred"
    mock_security_config.encryption_allowed_ciphers = []

    config = EncryptionConfig.from_security_config(mock_security_config)
    # Should fallback to default
    assert len(config.allowed_ciphers) > 0
    assert EncryptionType.RC4 in config.allowed_ciphers
    assert EncryptionType.AES in config.allowed_ciphers


@pytest.mark.asyncio
async def test_encryption_manager_init_with_security_config():
    """Test EncryptionManager.__init__ with security_config parameter."""
    mock_security_config = MagicMock()
    mock_security_config.encryption_mode = "required"
    mock_security_config.encryption_allowed_ciphers = ["aes"]

    manager = EncryptionManager(security_config=mock_security_config)
    assert manager.config.mode == EncryptionMode.REQUIRED
    assert EncryptionType.AES in manager.config.allowed_ciphers


@pytest.mark.asyncio
async def test_encryption_manager_init_with_exception():
    """Test EncryptionManager.__init__ when get_config raises exception."""
    with patch("ccbt.config.config.get_config", side_effect=Exception("Config error")):
        manager = EncryptionManager()
        # Should fallback to defaults
        assert manager.config is not None
        assert manager.config.mode == EncryptionMode.PREFERRED


@pytest.mark.asyncio
async def test_initiate_encryption_exception_path():
    """Test initiate_encryption exception handling (lines 213-229)."""
    manager = EncryptionManager()

    # Mock _create_encryption_session to raise exception
    async def failing_create(*_args, **_kwargs):
        raise ValueError("Test exception")

    manager._create_encryption_session = failing_create

    with patch("ccbt.security.encryption.emit_event", new_callable=AsyncMock) as mock_emit:
        success, handshake_data = await manager.initiate_encryption("peer_ex", "1.1.1.1")

        assert success is False
        assert handshake_data == b""
        assert manager.stats["sessions_failed"] >= 1
        # Should emit error event
        assert mock_emit.called


@pytest.mark.asyncio
async def test_complete_handshake_verification_fails():
    """Test complete_handshake when verification fails (lines 266-267)."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_vf", "2.2.2.2")

    # Invalid response that will fail verification
    invalid_response = b"\x01\xFF"  # Invalid cipher type

    result = await manager.complete_handshake("peer_vf", invalid_response)
    assert result is False


@pytest.mark.asyncio
async def test_complete_handshake_exception_path():
    """Test complete_handshake exception handling (lines 269-284)."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_ex2", "3.3.3.3")

    # Mock _verify_handshake_response to raise exception
    async def failing_verify(*_args, **_kwargs):
        raise RuntimeError("Verification error")

    manager._verify_handshake_response = failing_verify

    with patch("ccbt.security.encryption.emit_event", new_callable=AsyncMock) as mock_emit:
        result = await manager.complete_handshake("peer_ex2", b"response")

        assert result is False
        assert manager.stats["handshake_failures"] >= 1
        # Should emit error event
        assert mock_emit.called


@pytest.mark.asyncio
async def test_encrypt_data_no_cipher_suite():
    """Test encrypt_data when cipher suite is None (lines 307-308)."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_nc", "4.4.4.4")
    session = manager.encryption_sessions["peer_nc"]
    session.handshake_complete = True

    # Remove cipher for this encryption type
    manager.cipher_suites[session.encryption_type] = None

    success, result = await manager.encrypt_data("peer_nc", b"data")
    assert success is False
    assert result == b"data"


@pytest.mark.asyncio
async def test_encrypt_data_exception_path():
    """Test encrypt_data exception handling (lines 318-331)."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_ex3", "5.5.5.5")
    session = manager.encryption_sessions["peer_ex3"]
    session.handshake_complete = True

    # Mock _encrypt_with_cipher to raise exception
    async def failing_encrypt(*_args, **_kwargs):
        raise RuntimeError("Encryption error")

    manager._encrypt_with_cipher = failing_encrypt

    with patch("ccbt.security.encryption.emit_event", new_callable=AsyncMock) as mock_emit:
        success, result = await manager.encrypt_data("peer_ex3", b"data")

        assert success is False
        assert result == b"data"
        # Should emit error event
        assert mock_emit.called


@pytest.mark.asyncio
async def test_decrypt_data_no_cipher_suite():
    """Test decrypt_data when cipher suite is None (lines 360-361)."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_nc2", "6.6.6.6")
    session = manager.encryption_sessions["peer_nc2"]
    session.handshake_complete = True

    # Remove cipher for this encryption type
    manager.cipher_suites[session.encryption_type] = None

    success, result = await manager.decrypt_data("peer_nc2", b"encrypted")
    assert success is False
    assert result == b"encrypted"


@pytest.mark.asyncio
async def test_decrypt_data_exception_path():
    """Test decrypt_data exception handling (lines 375-388)."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_ex4", "7.7.7.7")
    session = manager.encryption_sessions["peer_ex4"]
    session.handshake_complete = True

    # Mock _decrypt_with_cipher to raise exception
    async def failing_decrypt(*_args, **_kwargs):
        raise RuntimeError("Decryption error")

    manager._decrypt_with_cipher = failing_decrypt

    with patch("ccbt.security.encryption.emit_event", new_callable=AsyncMock) as mock_emit:
        success, result = await manager.decrypt_data("peer_ex4", b"encrypted")

        assert success is False
        assert result == b"encrypted"
        # Should emit error event
        assert mock_emit.called


@pytest.mark.asyncio
async def test_select_encryption_type_no_allowed_ciphers():
    """Test _select_encryption_type with no allowed ciphers (lines 500-502)."""
    manager = EncryptionManager()
    manager.config.allowed_ciphers = []

    selected = manager._select_encryption_type()
    assert selected == EncryptionType.RC4


@pytest.mark.asyncio
async def test_select_encryption_type_no_available_in_preferred():
    """Test _select_encryption_type with no available ciphers in preferred order (lines 511-513)."""
    manager = EncryptionManager()
    manager.config.allowed_ciphers = [EncryptionType.NONE]  # Not in preferred_order

    selected = manager._select_encryption_type()
    assert selected == EncryptionType.NONE


@pytest.mark.asyncio
async def test_select_encryption_type_with_peer_capabilities():
    """Test _select_encryption_type with peer capabilities (lines 516-522)."""
    manager = EncryptionManager()
    manager.config.allowed_ciphers = [
        EncryptionType.CHACHA20,
        EncryptionType.AES,
        EncryptionType.RC4,
    ]

    # Peer supports only AES
    selected = manager._select_encryption_type(peer_capabilities=[EncryptionType.AES])
    # Should still prefer CHACHA20 if available, but if peer doesn't support it, fallback to AES
    # Actually, the logic matches first available cipher that peer supports
    # So if CHACHA20 is in allowed and preferred_order, it should be selected
    # But if peer doesn't support CHACHA20, it should match AES
    assert selected in [EncryptionType.CHACHA20, EncryptionType.AES]


@pytest.mark.asyncio
async def test_select_encryption_type_peer_capabilities_no_match():
    """Test _select_encryption_type with peer capabilities that don't match."""
    manager = EncryptionManager()
    manager.config.allowed_ciphers = [EncryptionType.CHACHA20, EncryptionType.AES]

    # Peer supports only RC4 (not in our allowed list)
    selected = manager._select_encryption_type(peer_capabilities=[EncryptionType.RC4])
    # Should return first available cipher from preferred order (CHACHA20)
    assert selected == EncryptionType.CHACHA20


@pytest.mark.asyncio
async def test_generate_handshake_with_chacha20():
    """Test _generate_handshake with CHACHA20 encryption type."""
    manager = EncryptionManager()
    session = EncryptionSession(
        peer_id="peer_chacha20",
        ip="8.8.8.8",
        encryption_type=EncryptionType.CHACHA20,
        key=bytes(range(32)),  # 32 bytes for ChaCha20
        created_at=time.time(),
        last_activity=time.time(),
    )

    handshake = await manager._generate_handshake(session)
    assert len(handshake) >= 2
    # Should contain version and CHACHA20 cipher type
    version, cipher_type = struct.unpack("!BB", handshake[:2])
    assert version == 1
    from ccbt.security.mse_handshake import CipherType

    assert cipher_type == int(CipherType.CHACHA20)


@pytest.mark.asyncio
async def test_verify_handshake_response_struct_error():
    """Test _verify_handshake_response with struct.error (lines 623-626)."""
    manager = EncryptionManager()
    session = EncryptionSession(
        peer_id="peer_struct",
        ip="9.9.9.9",
        encryption_type=EncryptionType.RC4,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )

    # Invalid response that will cause struct.error
    invalid_response = b"\x01"  # Too short, will cause struct.error on unpack

    result = await manager._verify_handshake_response(session, invalid_response)
    assert result is False


@pytest.mark.asyncio
async def test_verify_handshake_response_invalid_cipher_type():
    """Test _verify_handshake_response with invalid CipherType value (lines 619-621)."""
    manager = EncryptionManager()
    session = EncryptionSession(
        peer_id="peer_inv",
        ip="10.10.10.10",
        encryption_type=EncryptionType.RC4,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )

    # Response with invalid cipher type value (not in CipherType enum)
    invalid_response = struct.pack("!BB", 1, 255)  # 255 is not a valid CipherType

    result = await manager._verify_handshake_response(session, invalid_response)
    assert result is False


@pytest.mark.asyncio
async def test_encrypt_with_cipher_exception():
    """Test _encrypt_with_cipher exception handling (lines 650-654)."""
    manager = EncryptionManager()

    # Use a cipher class that will fail
    class FailingCipher:
        def __init__(self, key):
            raise ValueError("Invalid key")

    with pytest.raises(RuntimeError, match="Encryption failed"):
        await manager._encrypt_with_cipher(FailingCipher, b"key", b"data")


@pytest.mark.asyncio
async def test_decrypt_with_cipher_exception():
    """Test _decrypt_with_cipher exception handling (lines 677-681)."""
    manager = EncryptionManager()

    # Use a cipher class that will fail
    class FailingCipher:
        def __init__(self, key):
            raise ValueError("Invalid key")

    with pytest.raises(RuntimeError, match="Decryption failed"):
        await manager._decrypt_with_cipher(FailingCipher, b"key", b"encrypted")


@pytest.mark.asyncio
async def test_get_encryption_statistics_with_division():
    """Test get_encryption_statistics with encryption_rate calculation (lines 416-417)."""
    manager = EncryptionManager()

    # Set up some stats
    manager.stats["bytes_encrypted"] = 100
    manager.stats["bytes_decrypted"] = 50

    stats = manager.get_encryption_statistics()
    assert stats["encryption_rate"] == 100 / (100 + 50)


@pytest.mark.asyncio
async def test_get_encryption_statistics_zero_bytes():
    """Test get_encryption_statistics with zero bytes (division by zero protection)."""
    manager = EncryptionManager()

    # No bytes encrypted or decrypted
    manager.stats["bytes_encrypted"] = 0
    manager.stats["bytes_decrypted"] = 0

    stats = manager.get_encryption_statistics()
    # Should handle division by zero (max(1, ...))
    assert stats["encryption_rate"] == 0.0


@pytest.mark.asyncio
async def test_cleanup_old_sessions_multiple():
    """Test cleanup_old_sessions with multiple sessions."""
    manager = EncryptionManager()

    # Create multiple old sessions
    for i in range(5):
        await manager.initiate_encryption(f"old_peer_{i}", f"{i}.{i}.{i}.{i}")
        session = manager.encryption_sessions[f"old_peer_{i}"]
        session.last_activity = time.time() - 7200  # 2 hours ago

    # Create one new session
    await manager.initiate_encryption("new_peer", "10.10.10.10")

    # Cleanup sessions older than 1 hour
    manager.cleanup_old_sessions(max_age_seconds=3600)

    # All old sessions should be removed
    for i in range(5):
        assert f"old_peer_{i}" not in manager.encryption_sessions
    # New session should remain
    assert "new_peer" in manager.encryption_sessions


@pytest.mark.asyncio
async def test_generate_handshake_with_aes():
    """Test _generate_handshake with AES encryption type."""
    manager = EncryptionManager()
    session = EncryptionSession(
        peer_id="peer_aes",
        ip="11.11.11.11",
        encryption_type=EncryptionType.AES,
        key=b"key12345678901234",  # 16 bytes
        created_at=time.time(),
        last_activity=time.time(),
    )

    handshake = await manager._generate_handshake(session)
    assert len(handshake) >= 2 + 16  # Version + cipher type + key material


@pytest.mark.asyncio
async def test_generate_handshake_default_fallback():
    """Test _generate_handshake with unknown encryption type (fallback to RC4)."""
    manager = EncryptionManager()
    # Create session with encryption type not in map (should use default)
    session = EncryptionSession(
        peer_id="peer_unknown",
        ip="12.12.12.12",
        encryption_type=EncryptionType.NONE,  # Not in cipher_type_map
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )

    handshake = await manager._generate_handshake(session)
    # Should still generate handshake (fallback to RC4)
    assert len(handshake) >= 2


@pytest.mark.asyncio
async def test_verify_handshake_response_wrong_cipher_type():
    """Test _verify_handshake_response with wrong cipher type."""
    manager = EncryptionManager()
    session = EncryptionSession(
        peer_id="peer_wrong",
        ip="13.13.13.13",
        encryption_type=EncryptionType.AES,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )

    # Response with RC4 cipher type but session expects AES
    from ccbt.security.mse_handshake import CipherType

    response = struct.pack("!BB", 1, int(CipherType.RC4))

    result = await manager._verify_handshake_response(session, response)
    assert result is False  # Wrong cipher type


@pytest.mark.asyncio
async def test_verify_handshake_response_cipher_not_in_map():
    """Test _verify_handshake_response with cipher type not in map (fallback)."""
    manager = EncryptionManager()
    session = EncryptionSession(
        peer_id="peer_fallback",
        ip="14.14.14.14",
        encryption_type=EncryptionType.RC4,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )

    # Use a valid but unmapped cipher type value (should fallback to RC4)
    # Since we only have RC4, AES, CHACHA20, any other value should fail
    # But the logic uses .get() with RC4 as default, so it might match
    # Let's test with a valid but different type
    from ccbt.security.mse_handshake import CipherType

    # Test with CHACHA20 when session expects RC4
    response = struct.pack("!BB", 1, int(CipherType.CHACHA20))

    result = await manager._verify_handshake_response(session, response)
    assert result is False  # Different cipher types


@pytest.mark.asyncio
async def test_complete_handshake_emits_event():
    """Test complete_handshake emits handshake completed event."""
    manager = EncryptionManager()
    await manager.initiate_encryption("peer_event", "15.15.15.15")
    session = manager.encryption_sessions["peer_event"]

    import struct
    from ccbt.security.mse_handshake import CipherType

    cipher_type_map = {
        EncryptionType.RC4: CipherType.RC4,
        EncryptionType.AES: CipherType.AES,
        EncryptionType.CHACHA20: CipherType.CHACHA20,
    }

    response = struct.pack("!BB", 1, int(cipher_type_map[session.encryption_type]))

    with patch("ccbt.security.encryption.emit_event", new_callable=AsyncMock) as mock_emit:
        result = await manager.complete_handshake("peer_event", response)

        assert result is True
        # Should emit handshake completed event
        assert mock_emit.called

