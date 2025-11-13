"""Tests for ccbt.security.encryption.

Covers:
- Initialization and configuration
- Key generation
- Encryption session creation
- Handshake initiation and completion
- Data encryption and decryption
- Error handling
- Session management and cleanup
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]


@pytest.fixture
def encryption_manager():
    """Create an EncryptionManager instance."""
    from ccbt.security.encryption import EncryptionConfig, EncryptionManager
    
    return EncryptionManager()


@pytest.fixture
def encryption_manager_with_config():
    """Create an EncryptionManager with custom config."""
    from ccbt.security.encryption import EncryptionConfig, EncryptionManager, EncryptionMode, EncryptionType
    
    config = EncryptionConfig(
        mode=EncryptionMode.REQUIRED,
        allowed_ciphers=[EncryptionType.AES, EncryptionType.RC4],
        key_size=32,
        handshake_timeout=15.0,
    )
    return EncryptionManager(config)


@pytest.mark.asyncio
async def test_encryption_manager_init_default(encryption_manager):
    """Test EncryptionManager initialization with default config (lines 74-90)."""
    from ccbt.security.encryption import EncryptionMode, EncryptionType
    
    assert encryption_manager.config is not None
    assert encryption_manager.config.mode == EncryptionMode.PREFERRED
    assert encryption_manager.config.key_size == 16
    assert len(encryption_manager.encryption_sessions) == 0
    assert len(encryption_manager.cipher_suites) > 0
    assert encryption_manager.stats["sessions_created"] == 0
    assert encryption_manager.stats["sessions_failed"] == 0


@pytest.mark.asyncio
async def test_encryption_manager_init_custom_config(encryption_manager_with_config):
    """Test EncryptionManager initialization with custom config (lines 74-76)."""
    from ccbt.security.encryption import EncryptionMode, EncryptionType
    
    assert encryption_manager_with_config.config.mode == EncryptionMode.REQUIRED
    assert len(encryption_manager_with_config.config.allowed_ciphers) == 2
    assert encryption_manager_with_config.config.key_size == 32
    assert encryption_manager_with_config.config.handshake_timeout == 15.0


@pytest.mark.asyncio
async def test_encryption_config_post_init(encryption_manager):
    """Test EncryptionConfig __post_init__ (lines 50-53)."""
    from ccbt.security.encryption import EncryptionConfig, EncryptionType
    
    config = EncryptionConfig()
    assert len(config.allowed_ciphers) > 0
    assert EncryptionType.RC4 in config.allowed_ciphers
    assert EncryptionType.AES in config.allowed_ciphers


@pytest.mark.asyncio
async def test_initialize_cipher_suites(encryption_manager):
    """Test _initialize_cipher_suites (lines 448-457)."""
    from ccbt.security.encryption import EncryptionType

    # Verify cipher suites initialized
    assert EncryptionType.RC4 in encryption_manager.cipher_suites
    assert EncryptionType.AES in encryption_manager.cipher_suites
    assert EncryptionType.CHACHA20 in encryption_manager.cipher_suites


@pytest.mark.asyncio
async def test_initiate_encryption_success(encryption_manager):
    """Test initiate_encryption successful path (lines 92-145)."""
    success, handshake_data = await encryption_manager.initiate_encryption(
        peer_id="peer1",
        ip="1.2.3.4",
    )
    
    assert success is True
    assert len(handshake_data) > 0
    assert "peer1" in encryption_manager.encryption_sessions
    assert encryption_manager.stats["sessions_created"] >= 1


@pytest.mark.asyncio
async def test_initiate_encryption_failure(encryption_manager):
    """Test initiate_encryption exception handling (lines 127-143)."""
    # Mock _create_encryption_session to raise exception
    async def failing_create(*_args, **_kwargs):
        raise RuntimeError("Session creation failed")
    
    encryption_manager._create_encryption_session = failing_create
    
    success, handshake_data = await encryption_manager.initiate_encryption(
        peer_id="peer2",
        ip="2.3.4.5",
    )
    
    assert success is False
    assert handshake_data == b""
    assert encryption_manager.stats["sessions_failed"] >= 1


@pytest.mark.asyncio
async def test_initiate_encryption_emits_event(encryption_manager):
    """Test initiate_encryption emits event (lines 114-125)."""
    with patch("ccbt.security.encryption.emit_event", new_callable=AsyncMock) as mock_emit:
        await encryption_manager.initiate_encryption(
            peer_id="peer3",
            ip="3.4.5.6",
        )
        
        # Should emit encryption initiated event
        assert mock_emit.called
        call_args = mock_emit.call_args
        assert call_args is not None
        event = call_args[0][0]
        assert event.event_type == "encryption_initiated"


@pytest.mark.asyncio
async def test_create_encryption_session(encryption_manager):
    """Test _create_encryption_session (lines 371-390)."""
    from ccbt.security.encryption import EncryptionSession
    
    session = await encryption_manager._create_encryption_session(
        peer_id="peer4",
        ip="4.5.6.7",
    )
    
    assert isinstance(session, EncryptionSession)
    assert session.peer_id == "peer4"
    assert session.ip == "4.5.6.7"
    assert session.handshake_complete is False
    assert len(session.key) == encryption_manager.config.key_size
    assert session.created_at > 0
    assert session.last_activity > 0


@pytest.mark.asyncio
async def test_select_encryption_type(encryption_manager):
    """Test _select_encryption_type (lines 392-399)."""
    from ccbt.security.encryption import EncryptionType
    
    # With allowed ciphers
    encryption_type = encryption_manager._select_encryption_type()
    assert encryption_type in encryption_manager.config.allowed_ciphers
    
    # With empty allowed ciphers
    encryption_manager.config.allowed_ciphers = []
    encryption_type2 = encryption_manager._select_encryption_type()
    assert encryption_type2 == EncryptionType.RC4


@pytest.mark.asyncio
async def test_generate_encryption_key(encryption_manager):
    """Test _generate_encryption_key (lines 401-403)."""
    key = encryption_manager._generate_encryption_key()
    
    assert isinstance(key, bytes)
    assert len(key) == encryption_manager.config.key_size
    # Keys should be different
    key2 = encryption_manager._generate_encryption_key()
    assert key != key2


@pytest.mark.asyncio
async def test_generate_handshake(encryption_manager):
    """Test _generate_handshake (lines 405-419)."""
    from ccbt.security.encryption import EncryptionSession, EncryptionType
    
    session = EncryptionSession(
        peer_id="peer5",
        ip="5.6.7.8",
        encryption_type=EncryptionType.AES,
        key=b"test_key_12345678",  # 16 bytes
        created_at=time.time(),
        last_activity=time.time(),
    )
    
    handshake = await encryption_manager._generate_handshake(session)
    
    # Should include protocol version and encryption type + key
    # Handshake now uses first 16 bytes of key (aligned with MSE protocol)
    expected_min_length = 2 + min(16, len(session.key))
    assert len(handshake) >= expected_min_length


@pytest.mark.asyncio
async def test_complete_handshake_success(encryption_manager):
    """Test complete_handshake success path (lines 147-197)."""
    # First initiate encryption
    success, handshake_data = await encryption_manager.initiate_encryption(
        peer_id="peer6",
        ip="6.7.8.9",
    )
    assert success is True
    
    # Generate valid response (simplified)
    import struct
    from ccbt.security.encryption import EncryptionType
    
    session = encryption_manager.encryption_sessions["peer6"]
    response = struct.pack(
        "!BB",
        1,  # Version
        list(EncryptionType).index(session.encryption_type),
    )
    
    result = await encryption_manager.complete_handshake("peer6", response)
    
    assert result is True
    assert session.handshake_complete is True
    assert session.last_activity > 0


@pytest.mark.asyncio
async def test_complete_handshake_no_session(encryption_manager):
    """Test complete_handshake with no session (lines 157-158)."""
    result = await encryption_manager.complete_handshake("nonexistent", b"response")
    
    assert result is False


@pytest.mark.asyncio
async def test_complete_handshake_verification_failure(encryption_manager):
    """Test complete_handshake with invalid response (lines 430-443)."""
    # Initiate encryption
    await encryption_manager.initiate_encryption("peer7", "7.8.9.10")
    
    # Invalid response (wrong version)
    invalid_response = b"\x02\x00"  # Version 2 instead of 1
    
    result = await encryption_manager.complete_handshake("peer7", invalid_response)
    
    assert result is False


@pytest.mark.asyncio
async def test_complete_handshake_exception(encryption_manager):
    """Test complete_handshake exception handling (lines 180-195)."""
    # Initiate encryption
    await encryption_manager.initiate_encryption("peer8", "8.9.10.11")
    
    # Mock _verify_handshake_response to raise exception
    async def failing_verify(*_args, **_kwargs):
        raise RuntimeError("Verification failed")
    
    encryption_manager._verify_handshake_response = failing_verify
    
    result = await encryption_manager.complete_handshake("peer8", b"response")
    
    assert result is False
    assert encryption_manager.stats["handshake_failures"] >= 1


@pytest.mark.asyncio
async def test_verify_handshake_response_success(encryption_manager):
    """Test _verify_handshake_response success (lines 421-443)."""
    from ccbt.security.encryption import EncryptionSession, EncryptionType
    
    session = EncryptionSession(
        peer_id="peer9",
        ip="9.10.11.12",
        encryption_type=EncryptionType.RC4,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )
    
    import struct
    response = struct.pack(
        "!BB",
        1,  # Version 1
        list(EncryptionType).index(EncryptionType.RC4),
    )
    
    result = await encryption_manager._verify_handshake_response(session, response)
    
    assert result is True


@pytest.mark.asyncio
async def test_verify_handshake_response_short(encryption_manager):
    """Test _verify_handshake_response with short response (lines 430-431)."""
    from ccbt.security.encryption import EncryptionSession, EncryptionType
    
    session = EncryptionSession(
        peer_id="peer10",
        ip="10.11.12.13",
        encryption_type=EncryptionType.AES,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )
    
    result = await encryption_manager._verify_handshake_response(session, b"\x01")
    
    assert result is False


@pytest.mark.asyncio
async def test_verify_handshake_response_wrong_version(encryption_manager):
    """Test _verify_handshake_response wrong version (lines 436-437)."""
    from ccbt.security.encryption import EncryptionSession, EncryptionType
    
    session = EncryptionSession(
        peer_id="peer11",
        ip="11.12.13.14",
        encryption_type=EncryptionType.AES,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )
    
    import struct
    response = struct.pack("!BB", 2, 0)  # Wrong version
    
    result = await encryption_manager._verify_handshake_response(session, response)
    
    assert result is False


@pytest.mark.asyncio
async def test_verify_handshake_response_invalid_type_index(encryption_manager):
    """Test _verify_handshake_response invalid type index (lines 439-440)."""
    from ccbt.security.encryption import EncryptionSession, EncryptionType
    
    session = EncryptionSession(
        peer_id="peer12",
        ip="12.13.14.15",
        encryption_type=EncryptionType.AES,
        key=b"key12345678901234",
        created_at=time.time(),
        last_activity=time.time(),
    )
    
    import struct
    response = struct.pack("!BB", 1, 255)  # Invalid index
    
    result = await encryption_manager._verify_handshake_response(session, response)
    
    assert result is False


@pytest.mark.asyncio
async def test_encrypt_data_success(encryption_manager):
    """Test encrypt_data success path (lines 199-246)."""
    # Setup: initiate and complete handshake
    await encryption_manager.initiate_encryption("peer13", "13.14.15.16")
    session = encryption_manager.encryption_sessions["peer13"]
    
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer13", response)
    
    # Encrypt data
    data = b"test data to encrypt"
    initial_encrypted = encryption_manager.stats["bytes_encrypted"]
    
    success, encrypted = await encryption_manager.encrypt_data("peer13", data)
    
    assert success is True
    assert encryption_manager.stats["bytes_encrypted"] > initial_encrypted
    assert session.bytes_encrypted > 0
    assert session.last_activity >= session.created_at  # May be equal if called quickly


@pytest.mark.asyncio
async def test_encrypt_data_no_session(encryption_manager):
    """Test encrypt_data with no session (lines 209-210)."""
    data = b"test data"
    success, result = await encryption_manager.encrypt_data("nonexistent", data)
    
    assert success is False
    assert result == data  # Returns original data


@pytest.mark.asyncio
async def test_encrypt_data_handshake_incomplete(encryption_manager):
    """Test encrypt_data with incomplete handshake (lines 214-215)."""
    # Initiate but don't complete handshake
    await encryption_manager.initiate_encryption("peer14", "14.15.16.17")
    
    data = b"test data"
    success, result = await encryption_manager.encrypt_data("peer14", data)
    
    assert success is False
    assert result == data


@pytest.mark.asyncio
async def test_encrypt_data_no_cipher(encryption_manager):
    """Test encrypt_data with no cipher (lines 219-221)."""
    # Setup session with handshake complete
    await encryption_manager.initiate_encryption("peer15", "15.16.17.18")
    session = encryption_manager.encryption_sessions["peer15"]
    
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer15", response)
    
    # Remove cipher
    encryption_manager.cipher_suites.clear()
    
    data = b"test data"
    success, result = await encryption_manager.encrypt_data("peer15", data)
    
    assert success is False
    assert result == data


@pytest.mark.asyncio
async def test_encrypt_data_exception(encryption_manager):
    """Test encrypt_data exception handling (lines 231-244)."""
    # Setup session
    await encryption_manager.initiate_encryption("peer16", "16.17.18.19")
    session = encryption_manager.encryption_sessions["peer16"]
    
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer16", response)
    
    # Mock _encrypt_with_cipher to raise exception
    async def failing_encrypt(*_args, **_kwargs):
        raise RuntimeError("Encryption failed")
    
    encryption_manager._encrypt_with_cipher = failing_encrypt
    
    data = b"test data"
    success, result = await encryption_manager.encrypt_data("peer16", data)
    
    assert success is False
    assert result == data


@pytest.mark.asyncio
async def test_decrypt_data_success(encryption_manager):
    """Test decrypt_data success path (lines 248-303)."""
    # Setup: initiate and complete handshake
    await encryption_manager.initiate_encryption("peer17", "17.18.19.20")
    session = encryption_manager.encryption_sessions["peer17"]
    
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer17", response)
    
    # Decrypt data
    encrypted_data = b"encrypted data"
    initial_decrypted = encryption_manager.stats["bytes_decrypted"]
    
    success, decrypted = await encryption_manager.decrypt_data("peer17", encrypted_data)
    
    assert success is True
    assert encryption_manager.stats["bytes_decrypted"] > initial_decrypted
    assert session.bytes_decrypted > 0
    assert session.last_activity >= session.created_at  # May be equal if called quickly


@pytest.mark.asyncio
async def test_decrypt_data_no_session(encryption_manager):
    """Test decrypt_data with no session (lines 262-263)."""
    encrypted = b"encrypted"
    success, result = await encryption_manager.decrypt_data("nonexistent", encrypted)
    
    assert success is False
    assert result == encrypted


@pytest.mark.asyncio
async def test_decrypt_data_handshake_incomplete(encryption_manager):
    """Test decrypt_data with incomplete handshake (lines 267-268)."""
    await encryption_manager.initiate_encryption("peer18", "18.19.20.21")
    
    encrypted = b"encrypted"
    success, result = await encryption_manager.decrypt_data("peer18", encrypted)
    
    assert success is False
    assert result == encrypted


@pytest.mark.asyncio
async def test_decrypt_data_no_cipher(encryption_manager):
    """Test decrypt_data with no cipher (lines 272-274)."""
    # Setup session with handshake complete
    await encryption_manager.initiate_encryption("peer19", "19.20.21.22")
    session = encryption_manager.encryption_sessions["peer19"]
    
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer19", response)
    
    # Remove cipher
    encryption_manager.cipher_suites.clear()
    
    encrypted = b"encrypted"
    success, result = await encryption_manager.decrypt_data("peer19", encrypted)
    
    assert success is False
    assert result == encrypted


@pytest.mark.asyncio
async def test_decrypt_data_exception(encryption_manager):
    """Test decrypt_data exception handling (lines 288-301)."""
    # Setup session
    await encryption_manager.initiate_encryption("peer20", "20.21.22.23")
    session = encryption_manager.encryption_sessions["peer20"]
    
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer20", response)
    
    # Mock _decrypt_with_cipher to raise exception
    async def failing_decrypt(*_args, **_kwargs):
        raise RuntimeError("Decryption failed")
    
    encryption_manager._decrypt_with_cipher = failing_decrypt
    
    encrypted = b"encrypted"
    success, result = await encryption_manager.decrypt_data("peer20", encrypted)
    
    assert success is False
    assert result == encrypted


@pytest.mark.asyncio
async def test_encrypt_with_cipher(encryption_manager):
    """Test _encrypt_with_cipher method (lines 534-556)."""
    from ccbt.security.ciphers.rc4 import RC4Cipher
    
    data = b"test data"
    key = b"test_key_16bytes"  # 16 bytes for RC4
    
    encrypted = await encryption_manager._encrypt_with_cipher(
        RC4Cipher,
        key,
        data,
    )
    
    # Should be encrypted (different from plaintext)
    assert encrypted != data
    assert len(encrypted) == len(data)  # Stream cipher preserves length
    
    # Should be able to decrypt it back
    cipher = RC4Cipher(key)
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == data


@pytest.mark.asyncio
async def test_decrypt_with_cipher(encryption_manager):
    """Test _decrypt_with_cipher method (lines 558-583)."""
    from ccbt.security.ciphers.rc4 import RC4Cipher
    
    plaintext = b"test data to decrypt"
    key = b"test_key_16bytes"  # 16 bytes for RC4
    
    # First encrypt some data
    cipher = RC4Cipher(key)
    encrypted = cipher.encrypt(plaintext)
    
    # Now decrypt using the manager
    decrypted = await encryption_manager._decrypt_with_cipher(
        RC4Cipher,
        key,
        encrypted,
    )
    
    # Should match original plaintext
    assert decrypted == plaintext
    assert decrypted != encrypted


@pytest.mark.asyncio
async def test_is_peer_encrypted(encryption_manager):
    """Test is_peer_encrypted method (lines 305-311)."""
    # No session
    assert encryption_manager.is_peer_encrypted("nonexistent") is False
    
    # Session but handshake not complete
    await encryption_manager.initiate_encryption("peer21", "21.22.23.24")
    assert encryption_manager.is_peer_encrypted("peer21") is False
    
    # Complete handshake
    session = encryption_manager.encryption_sessions["peer21"]
    import struct
    from ccbt.security.encryption import EncryptionType
    
    response = struct.pack(
        "!BB",
        1,
        list(EncryptionType).index(session.encryption_type),
    )
    await encryption_manager.complete_handshake("peer21", response)
    
    assert encryption_manager.is_peer_encrypted("peer21") is True


@pytest.mark.asyncio
async def test_get_encryption_type(encryption_manager):
    """Test get_encryption_type method (lines 313-318)."""
    from ccbt.security.encryption import EncryptionType
    
    # No session
    assert encryption_manager.get_encryption_type("nonexistent") is None
    
    # With session
    await encryption_manager.initiate_encryption("peer22", "22.23.24.25")
    encryption_type = encryption_manager.get_encryption_type("peer22")
    
    assert encryption_type is not None
    assert encryption_type in [EncryptionType.RC4, EncryptionType.AES, EncryptionType.CHACHA20]


@pytest.mark.asyncio
async def test_get_encryption_statistics(encryption_manager):
    """Test get_encryption_statistics method (lines 320-331)."""
    # Setup some activity
    await encryption_manager.initiate_encryption("peer23", "23.24.25.26")
    
    stats = encryption_manager.get_encryption_statistics()
    
    # Verify all fields present
    assert "sessions_created" in stats
    assert "sessions_failed" in stats
    assert "bytes_encrypted" in stats
    assert "bytes_decrypted" in stats
    assert "handshake_failures" in stats
    assert "active_sessions" in stats
    assert "encryption_rate" in stats
    
    assert stats["sessions_created"] >= 1
    assert stats["active_sessions"] >= 1


@pytest.mark.asyncio
async def test_get_peer_encryption_info(encryption_manager):
    """Test get_peer_encryption_info method (lines 333-347)."""
    # No session
    info = encryption_manager.get_peer_encryption_info("nonexistent")
    assert info is None
    
    # With session
    await encryption_manager.initiate_encryption("peer24", "24.25.26.27")
    
    info = encryption_manager.get_peer_encryption_info("peer24")
    
    assert info is not None
    assert "encryption_type" in info
    assert "handshake_complete" in info
    assert "bytes_encrypted" in info
    assert "bytes_decrypted" in info
    assert "created_at" in info
    assert "last_activity" in info


@pytest.mark.asyncio
async def test_cleanup_old_sessions(encryption_manager):
    """Test cleanup_old_sessions method (lines 349-360)."""
    # Create old session
    await encryption_manager.initiate_encryption("old_peer", "1.1.1.1")
    old_session = encryption_manager.encryption_sessions["old_peer"]
    old_session.last_activity = time.time() - 7200  # 2 hours ago
    
    # Create new session
    await encryption_manager.initiate_encryption("new_peer", "2.2.2.2")
    new_session = encryption_manager.encryption_sessions["new_peer"]
    new_session.last_activity = time.time()
    
    # Cleanup sessions older than 1 hour
    encryption_manager.cleanup_old_sessions(max_age_seconds=3600)
    
    # Old session should be removed
    assert "old_peer" not in encryption_manager.encryption_sessions
    # New session should remain
    assert "new_peer" in encryption_manager.encryption_sessions

