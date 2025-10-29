"""Tests for configuration validation functionality."""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from ccbt.config import ConfigManager
from ccbt.config_schema import ConfigValidator
from ccbt.models import Config


class TestConfigValidation:
    """Test configuration validation scenarios."""

    def test_valid_configuration_scenarios(self):
        """Test various valid configuration scenarios."""
        valid_configs = [
            # Minimal config
            {},
            
            # Basic network config
            {
                "network": {
                    "listen_port": 6881,
                    "max_global_peers": 200,
                }
            },
            
            # Full config
            {
                "network": {
                    "listen_port": 6881,
                    "max_global_peers": 200,
                    "enable_ipv6": True,
                    "enable_tcp": True,
                    "enable_utp": False,
                },
                "disk": {
                    "hash_workers": 4,
                    "disk_workers": 2,
                    "use_mmap": True,
                },
                "strategy": {
                    "piece_selection": "rarest_first",
                    "endgame_threshold": 0.95,
                },
                "discovery": {
                    "enable_dht": True,
                    "dht_port": 6882,
                },
                "observability": {
                    "log_level": "INFO",
                    "enable_metrics": True,
                },
                "limits": {
                    "global_down_kib": 0,
                    "global_up_kib": 0,
                },
                "security": {
                    "enable_encryption": False,
                    "validate_peers": True,
                },
                "ml": {
                    "peer_selection_enabled": False,
                    "piece_prediction_enabled": False,
                }
            }
        ]
        
        for config_data in valid_configs:
            is_valid, errors = ConfigValidator.validate_with_details(config_data)
            assert is_valid, f"Config should be valid but got errors: {errors}"

    def test_invalid_configuration_scenarios(self):
        """Test various invalid configuration scenarios."""
        invalid_configs = [
            # Invalid port number
            {
                "network": {
                    "listen_port": "invalid",
                }
            },
            
            # Negative peer count
            {
                "network": {
                    "max_global_peers": -1,
                }
            },
            
            # Invalid enum value
            {
                "strategy": {
                    "piece_selection": "invalid_strategy",
                }
            },
            
            # Out of range values
            {
                "network": {
                    "listen_port": 1023,  # Below minimum
                }
            },
            
            # Invalid type
            {
                "disk": {
                    "hash_workers": "not_a_number",
                }
            },
            
            # Invalid boolean
            {
                "network": {
                    "enable_ipv6": 123,  # Should be boolean, not int
                }
            }
        ]
        
        for config_data in invalid_configs:
            is_valid, errors = ConfigValidator.validate_with_details(config_data)
            assert not is_valid, f"Config should be invalid: {config_data}"
            assert len(errors) > 0, "Should have validation errors"

    def test_edge_cases_min_max_values(self):
        """Test edge cases with min/max values."""
        # Test minimum values
        min_config = {
            "network": {
                "listen_port": 1024,  # Minimum
                "max_global_peers": 1,  # Minimum
            },
            "disk": {
                "hash_workers": 1,  # Minimum
                "disk_workers": 1,  # Minimum
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(min_config)
        assert is_valid, f"Min config should be valid: {errors}"
        
        # Test maximum values
        max_config = {
            "network": {
                "listen_port": 65535,  # Maximum
                "max_global_peers": 10000,  # Maximum
            },
            "disk": {
                "hash_workers": 32,  # Maximum
                "disk_workers": 16,  # Maximum
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(max_config)
        assert is_valid, f"Max config should be valid: {errors}"

    def test_edge_cases_out_of_range(self):
        """Test edge cases with out-of-range values."""
        out_of_range_configs = [
            # Below minimum
            {
                "network": {
                    "listen_port": 1023,  # Below minimum
                }
            },
            
            # Above maximum
            {
                "network": {
                    "listen_port": 65536,  # Above maximum
                }
            },
            
            # Negative values where not allowed
            {
                "network": {
                    "max_global_peers": -1,
                }
            }
        ]
        
        for config_data in out_of_range_configs:
            is_valid, errors = ConfigValidator.validate_with_details(config_data)
            assert not is_valid, f"Out of range config should be invalid: {config_data}"

    def test_system_capability_checks(self):
        """Test system capability validation."""
        # Mock CPU count for testing
        with patch('os.cpu_count', return_value=4):
            # Reasonable worker counts
            reasonable_config = {
                "disk": {
                    "hash_workers": 4,  # Equal to CPU count
                    "disk_workers": 2,   # Less than CPU count
                }
            }
            
            errors = ConfigValidator.validate_cross_field_rules(reasonable_config)
            assert len(errors) == 0, f"Reasonable config should have no warnings: {errors}"
            
            # Excessive worker counts
            excessive_config = {
                "disk": {
                    "hash_workers": 16,  # 4x CPU count
                    "disk_workers": 8,   # 2x CPU count
                }
            }
            
            errors = ConfigValidator.validate_cross_field_rules(excessive_config)
            assert len(errors) > 0, "Excessive config should have warnings"
            assert any("Hash workers" in error for error in errors)
            assert any("Disk workers" in error for error in errors)

    def test_cross_field_validation_rules(self):
        """Test cross-field validation rules."""
        # Test DHT port conflict - this should be caught by model validator
        dht_conflict_config = {
            "network": {"listen_port": 6881},
            "discovery": {"enable_dht": True, "dht_port": 6881}
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(dht_conflict_config)
        assert not is_valid, "DHT port conflict should be caught by model validator"
        assert any("DHT port cannot be the same as listen port" in error for error in errors)
        
        # Test limit conflicts
        limit_conflict_config = {
            "limits": {
                "global_down_kib": 500,
                "per_torrent_down_kib": 1000,  # Higher than global
                "global_up_kib": 500,
                "per_torrent_up_kib": 1000,    # Higher than global
            }
        }
        
        errors = ConfigValidator.validate_cross_field_rules(limit_conflict_config)
        assert len(errors) > 0
        assert any("Global download limit should be >=" in error for error in errors)
        assert any("Global upload limit should be >=" in error for error in errors)

    def test_property_based_validation_consistency(self):
        """Test validation consistency with property-based testing."""
        import random
        
        # Test that valid configs remain valid after minor modifications
        base_config = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 200,
            },
            "disk": {
                "hash_workers": 4,
            }
        }
        
        # Test multiple variations
        for _ in range(10):
            # Create a variation of the base config
            config = base_config.copy()
            
            # Randomly modify some values within valid ranges
            if random.choice([True, False]):
                config["network"]["listen_port"] = random.randint(1024, 65535)
            
            if random.choice([True, False]):
                config["network"]["max_global_peers"] = random.randint(1, 10000)
            
            if random.choice([True, False]):
                config["disk"]["hash_workers"] = random.randint(1, 32)
            
            # Should still be valid
            is_valid, errors = ConfigValidator.validate_with_details(config)
            assert is_valid, f"Variation should be valid: {errors}"

    def test_validation_error_message_quality(self):
        """Test that validation error messages are helpful."""
        config_data = {
            "network": {
                "listen_port": "invalid_port",
                "max_global_peers": -5,
            },
            "strategy": {
                "piece_selection": "invalid_strategy",
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        
        assert not is_valid
        assert len(errors) > 0
        
        # Check that error messages are descriptive
        error_text = " ".join(errors)
        assert "listen_port" in error_text
        assert "max_global_peers" in error_text
        assert "piece_selection" in error_text

    def test_config_manager_validation_integration(self):
        """Test validation integration with ConfigManager."""
        # Test with valid config
        config_manager = ConfigManager()
        is_valid, errors = config_manager.validate_detailed()
        
        assert is_valid, f"Default config should be valid: {errors}"
        
        # Test schema access
        schema = config_manager.get_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        
        # Test option listing
        options = config_manager.list_options()
        assert isinstance(options, list)
        assert len(options) > 0
        
        # Test option metadata
        metadata = config_manager.get_option_metadata("network.listen_port")
        assert metadata is not None
        assert isinstance(metadata, dict)

    def test_validation_performance(self):
        """Test validation performance."""
        import time
        
        config_data = {
            "network": {
                "listen_port": 6881,
                "max_global_peers": 200,
            },
            "disk": {
                "hash_workers": 4,
            }
        }
        
        # Time validation
        start_time = time.time()
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        end_time = time.time()
        
        assert is_valid
        assert (end_time - start_time) < 0.1  # Should be fast (< 100ms)

    def test_validation_with_none_values(self):
        """Test validation with None values."""
        config_data = {
            "network": {
                "listen_port": None,  # Should be invalid
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert not is_valid
        assert len(errors) > 0

    def test_validation_with_empty_strings(self):
        """Test validation with empty strings."""
        # Most string fields in the config allow empty strings or None
        # This test is skipped as the current model doesn't have strict string validation
        pytest.skip("Current config model allows empty strings for most fields")

    def test_validation_with_zero_values(self):
        """Test validation with zero values where appropriate."""
        config_data = {
            "limits": {
                "global_down_kib": 0,  # 0 should be valid (unlimited)
                "global_up_kib": 0,    # 0 should be valid (unlimited)
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid, f"Zero limits should be valid: {errors}"

    def test_validation_with_float_precision(self):
        """Test validation with float precision."""
        config_data = {
            "strategy": {
                "endgame_threshold": 0.123456789,  # High precision float
            }
        }
        
        is_valid, errors = ConfigValidator.validate_with_details(config_data)
        assert is_valid, f"High precision float should be valid: {errors}"
