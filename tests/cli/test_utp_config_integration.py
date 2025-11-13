"""Tests for uTP configuration integration with CLI overrides."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from ccbt.cli.main import _apply_utp_overrides
from ccbt.config.config import Config, ConfigManager, get_config


class TestUTPConfigOverrides:
    """Test uTP configuration CLI overrides."""

    def test_apply_utp_overrides_prefer_over_tcp(self):
        """Test applying prefer_over_tcp override."""
        config = get_config()
        original_value = config.network.utp.prefer_over_tcp
        
        try:
            options = {"utp_prefer_over_tcp": True}
            _apply_utp_overrides(config, options)
            assert config.network.utp.prefer_over_tcp is True
            
            options = {"utp_prefer_over_tcp": False}
            _apply_utp_overrides(config, options)
            assert config.network.utp.prefer_over_tcp is False
        finally:
            config.network.utp.prefer_over_tcp = original_value

    def test_apply_utp_overrides_connection_timeout(self):
        """Test applying connection_timeout override."""
        config = get_config()
        original_value = config.network.utp.connection_timeout
        
        try:
            options = {"utp_connection_timeout": 45.0}
            _apply_utp_overrides(config, options)
            assert config.network.utp.connection_timeout == 45.0
        finally:
            config.network.utp.connection_timeout = original_value

    def test_apply_utp_overrides_max_window_size(self):
        """Test applying max_window_size override."""
        config = get_config()
        original_value = config.network.utp.max_window_size
        
        try:
            options = {"utp_max_window_size": 32768}
            _apply_utp_overrides(config, options)
            assert config.network.utp.max_window_size == 32768
        finally:
            config.network.utp.max_window_size = original_value

    def test_apply_utp_overrides_mtu(self):
        """Test applying MTU override."""
        config = get_config()
        original_value = config.network.utp.mtu
        
        try:
            options = {"utp_mtu": 1500}
            _apply_utp_overrides(config, options)
            assert config.network.utp.mtu == 1500
        finally:
            config.network.utp.mtu = original_value

    def test_apply_utp_overrides_rates(self):
        """Test applying rate overrides."""
        config = get_config()
        original_values = {
            "initial_rate": config.network.utp.initial_rate,
            "min_rate": config.network.utp.min_rate,
            "max_rate": config.network.utp.max_rate,
        }
        
        try:
            options = {
                "utp_initial_rate": 2000,
                "utp_min_rate": 1024,
                "utp_max_rate": 2000000,
            }
            _apply_utp_overrides(config, options)
            assert config.network.utp.initial_rate == 2000
            assert config.network.utp.min_rate == 1024
            assert config.network.utp.max_rate == 2000000
        finally:
            for key, value in original_values.items():
                setattr(config.network.utp, key, value)

    def test_apply_utp_overrides_ack_interval(self):
        """Test applying ACK interval override."""
        config = get_config()
        original_value = config.network.utp.ack_interval
        
        try:
            options = {"utp_ack_interval": 0.2}
            _apply_utp_overrides(config, options)
            assert config.network.utp.ack_interval == 0.2
        finally:
            config.network.utp.ack_interval = original_value

    def test_apply_utp_overrides_retransmit_timeout_factor(self):
        """Test applying retransmit timeout factor override."""
        config = get_config()
        original_value = config.network.utp.retransmit_timeout_factor
        
        try:
            options = {"utp_retransmit_timeout_factor": 5.0}
            _apply_utp_overrides(config, options)
            assert config.network.utp.retransmit_timeout_factor == 5.0
        finally:
            config.network.utp.retransmit_timeout_factor = original_value

    def test_apply_utp_overrides_max_retransmits(self):
        """Test applying max_retransmits override."""
        config = get_config()
        original_value = config.network.utp.max_retransmits
        
        try:
            options = {"utp_max_retransmits": 15}
            _apply_utp_overrides(config, options)
            assert config.network.utp.max_retransmits == 15
        finally:
            config.network.utp.max_retransmits = original_value

    def test_apply_utp_overrides_no_options(self):
        """Test that applying no overrides doesn't change values."""
        config = get_config()
        original_values = {
            "prefer_over_tcp": config.network.utp.prefer_over_tcp,
            "mtu": config.network.utp.mtu,
            "connection_timeout": config.network.utp.connection_timeout,
        }
        
        options = {}
        _apply_utp_overrides(config, options)
        
        assert config.network.utp.prefer_over_tcp == original_values["prefer_over_tcp"]
        assert config.network.utp.mtu == original_values["mtu"]
        assert config.network.utp.connection_timeout == original_values["connection_timeout"]


class TestUTPEnvironmentVariables:
    """Test uTP configuration from environment variables."""

    def test_utp_mtu_env_var(self):
        """Test that UTP MTU can be set via environment variable."""
        with patch.dict(os.environ, {"CCBT_UTP_MTU": "1500"}):
            config_manager = ConfigManager()
            assert config_manager.config.network.utp.mtu == 1500

    def test_utp_connection_timeout_env_var(self):
        """Test that UTP connection timeout can be set via environment variable."""
        with patch.dict(os.environ, {"CCBT_UTP_CONNECTION_TIMEOUT": "45.0"}):
            config_manager = ConfigManager()
            assert config_manager.config.network.utp.connection_timeout == 45.0

    def test_utp_prefer_over_tcp_env_var(self):
        """Test that UTP prefer_over_tcp can be set via environment variable."""
        with patch.dict(os.environ, {"CCBT_UTP_PREFER_OVER_TCP": "false"}):
            config_manager = ConfigManager()
            assert config_manager.config.network.utp.prefer_over_tcp is False

    def test_utp_all_env_vars(self):
        """Test that all UTP environment variables work."""
        env_vars = {
            "CCBT_UTP_PREFER_OVER_TCP": "false",
            "CCBT_UTP_CONNECTION_TIMEOUT": "45.0",
            "CCBT_UTP_MAX_WINDOW_SIZE": "32768",
            "CCBT_UTP_MTU": "1500",
            "CCBT_UTP_INITIAL_RATE": "2000",
            "CCBT_UTP_MIN_RATE": "1024",
            "CCBT_UTP_MAX_RATE": "2000000",
            "CCBT_UTP_ACK_INTERVAL": "0.2",
            "CCBT_UTP_RETRANSMIT_TIMEOUT_FACTOR": "5.0",
            "CCBT_UTP_MAX_RETRANSMITS": "15",
        }
        
        with patch.dict(os.environ, env_vars):
            config_manager = ConfigManager()
            assert config_manager.config.network.utp.prefer_over_tcp is False
            assert config_manager.config.network.utp.connection_timeout == 45.0
            assert config_manager.config.network.utp.max_window_size == 32768
            assert config_manager.config.network.utp.mtu == 1500
            assert config_manager.config.network.utp.initial_rate == 2000
            assert config_manager.config.network.utp.min_rate == 1024
            assert config_manager.config.network.utp.max_rate == 2000000
            assert config_manager.config.network.utp.ack_interval == 0.2
            assert config_manager.config.network.utp.retransmit_timeout_factor == 5.0
            assert config_manager.config.network.utp.max_retransmits == 15

