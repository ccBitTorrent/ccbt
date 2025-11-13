"""Test EncryptionManager initialization paths for coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_init_with_security_config():
    """Test EncryptionManager.__init__ with security_config parameter.

    Covers line 148 in encryption.py.
    """
    from ccbt.security.encryption import EncryptionManager

    # Create mock security_config
    mock_security_config = MagicMock()
    mock_security_config.encryption_mode = "required"
    mock_security_config.encryption_allowed_ciphers = ["rc4", "aes"]
    mock_security_config.encryption_prefer_rc4 = True
    mock_security_config.encryption_allow_plain_fallback = False

    # Initialize with security_config (should use line 148)
    manager = EncryptionManager(security_config=mock_security_config)

    assert manager.config is not None
    assert manager.config.mode.value == "required"
    assert len(manager.config.allowed_ciphers) > 0

