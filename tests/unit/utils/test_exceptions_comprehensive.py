"""Comprehensive tests for exceptions.py to achieve 99% coverage.

Covers:
- CCBTError initialization with/without details
- CCBTError __str__ method with/without details
- All exception hierarchy classes instantiate correctly
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit]

from ccbt.utils.exceptions import (
    CCBTError,
    CCBTTimeoutError,
    BencodeError,
    CheckpointCorruptedError,
    CheckpointError,
    CheckpointNotFoundError,
    CheckpointVersionError,
    ConfigurationError,
    DHTError,
    DiskError,
    FileSystemError,
    HandshakeError,
    MessageError,
    NetworkError,
    PeerConnectionError,
    PeerValidationError,
    PreallocationError,
    ProtocolError,
    RateLimitError,
    ResourceError,
    SecurityError,
    TorrentError,
    TrackerError,
    ValidationError,
)


class TestCCBTError:
    """Test CCBTError base exception class."""

    def test_init_with_message_only(self):
        """Test CCBTError.__init__() with message only (lines 17-20)."""
        error = CCBTError("Test error message")
        
        assert error.message == "Test error message"
        assert error.details == {}

    def test_init_with_message_and_details(self):
        """Test CCBTError.__init__() with message and details dict (lines 17-21)."""
        details = {"key1": "value1", "key2": 42}
        error = CCBTError("Test error message", details=details)
        
        assert error.message == "Test error message"
        assert error.details == details

    def test_init_with_details_none(self):
        """Test CCBTError.__init__() with details=None (defaults to empty dict)."""
        error = CCBTError("Test error message", details=None)
        
        assert error.message == "Test error message"
        assert error.details == {}

    def test_str_without_details(self):
        """Test CCBTError.__str__() without details (returns message only, lines 23-27)."""
        error = CCBTError("Test error message")
        
        str_repr = str(error)
        assert str_repr == "Test error message"

    def test_str_with_details(self):
        """Test CCBTError.__str__() with details (formats correctly, lines 23-26)."""
        details = {"key1": "value1", "key2": 42}
        error = CCBTError("Test error message", details=details)
        
        str_repr = str(error)
        assert str_repr == "Test error message (Details: {'key1': 'value1', 'key2': 42})"

    def test_str_with_empty_details(self):
        """Test CCBTError.__str__() with empty details dict (returns message only)."""
        error = CCBTError("Test error message", details={})
        
        str_repr = str(error)
        assert str_repr == "Test error message"


class TestExceptionHierarchy:
    """Test all exception hierarchy classes instantiate correctly."""

    def test_network_error(self):
        """Test NetworkError can be instantiated."""
        error = NetworkError("Network error")
        assert isinstance(error, CCBTError)
        assert error.message == "Network error"

    def test_tracker_error(self):
        """Test TrackerError can be instantiated."""
        error = TrackerError("Tracker error")
        assert isinstance(error, NetworkError)
        assert isinstance(error, CCBTError)

    def test_peer_connection_error(self):
        """Test PeerConnectionError can be instantiated."""
        error = PeerConnectionError("Connection error")
        assert isinstance(error, NetworkError)

    def test_dht_error(self):
        """Test DHTError can be instantiated."""
        error = DHTError("DHT error")
        assert isinstance(error, NetworkError)

    def test_disk_error(self):
        """Test DiskError can be instantiated."""
        error = DiskError("Disk error")
        assert isinstance(error, CCBTError)

    def test_file_system_error(self):
        """Test FileSystemError can be instantiated."""
        error = FileSystemError("File system error")
        assert isinstance(error, DiskError)

    def test_preallocation_error(self):
        """Test PreallocationError can be instantiated."""
        error = PreallocationError("Preallocation error")
        assert isinstance(error, DiskError)

    def test_protocol_error(self):
        """Test ProtocolError can be instantiated."""
        error = ProtocolError("Protocol error")
        assert isinstance(error, CCBTError)

    def test_handshake_error(self):
        """Test HandshakeError can be instantiated."""
        error = HandshakeError("Handshake error")
        assert isinstance(error, ProtocolError)

    def test_message_error(self):
        """Test MessageError can be instantiated."""
        error = MessageError("Message error")
        assert isinstance(error, ProtocolError)

    def test_validation_error(self):
        """Test ValidationError can be instantiated."""
        error = ValidationError("Validation error")
        assert isinstance(error, CCBTError)

    def test_configuration_error(self):
        """Test ConfigurationError can be instantiated."""
        error = ConfigurationError("Configuration error")
        assert isinstance(error, ValidationError)

    def test_torrent_error(self):
        """Test TorrentError can be instantiated."""
        error = TorrentError("Torrent error")
        assert isinstance(error, ValidationError)

    def test_bencode_error(self):
        """Test BencodeError can be instantiated."""
        error = BencodeError("Bencode error")
        assert isinstance(error, ValidationError)

    def test_resource_error(self):
        """Test ResourceError can be instantiated."""
        error = ResourceError("Resource error")
        assert isinstance(error, CCBTError)

    def test_ccbt_timeout_error(self):
        """Test CCBTTimeoutError can be instantiated."""
        error = CCBTTimeoutError("Timeout error")
        assert isinstance(error, CCBTError)

    def test_security_error(self):
        """Test SecurityError can be instantiated."""
        error = SecurityError("Security error")
        assert isinstance(error, CCBTError)

    def test_peer_validation_error(self):
        """Test PeerValidationError can be instantiated."""
        error = PeerValidationError("Peer validation error")
        assert isinstance(error, SecurityError)

    def test_rate_limit_error(self):
        """Test RateLimitError can be instantiated."""
        error = RateLimitError("Rate limit error")
        assert isinstance(error, SecurityError)

    def test_checkpoint_error(self):
        """Test CheckpointError can be instantiated."""
        error = CheckpointError("Checkpoint error")
        assert isinstance(error, CCBTError)

    def test_checkpoint_not_found_error(self):
        """Test CheckpointNotFoundError can be instantiated."""
        error = CheckpointNotFoundError("Checkpoint not found")
        assert isinstance(error, CheckpointError)

    def test_checkpoint_corrupted_error(self):
        """Test CheckpointCorruptedError can be instantiated."""
        error = CheckpointCorruptedError("Checkpoint corrupted")
        assert isinstance(error, CheckpointError)

    def test_checkpoint_version_error(self):
        """Test CheckpointVersionError can be instantiated."""
        error = CheckpointVersionError("Checkpoint version error")
        assert isinstance(error, CheckpointError)

    def test_all_exceptions_inherit_str_behavior(self):
        """Test all exceptions inherit __str__ behavior from CCBTError."""
        # Test with details
        network_err = NetworkError("Net error", details={"code": 500})
        assert "(Details: {'code': 500})" in str(network_err)
        
        # Test without details
        disk_err = DiskError("Disk error")
        assert str(disk_err) == "Disk error"

