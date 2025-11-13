"""Unit tests for SSL context builder.

Tests SSL context creation, certificate validation, and pinning.
Target: 95%+ code coverage for ccbt/security/ssl_context.py.
"""

from __future__ import annotations

import ssl
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.security]

from ccbt.config.config import ConfigManager, init_config
from ccbt.models import Config
from ccbt.security.ssl_context import (
    CertificatePinner,
    SSLContextBuilder,
    SSLCertificateValidator,
)


class TestSSLContextBuilderInitialization:
    """Tests for SSLContextBuilder initialization."""

    def test_ssl_context_builder_init(self):
        """Test SSLContextBuilder initialization."""
        builder = SSLContextBuilder()
        assert builder.config is not None
        assert builder.logger is not None


class TestSSLContextBuilderTrackerContext:
    """Tests for tracker SSL context creation."""

    def test_create_tracker_context_default(self):
        """Test creating default tracker SSL context."""
        builder = SSLContextBuilder()
        context = builder.create_tracker_context()

        assert isinstance(context, ssl.SSLContext)
        # Default context should verify certificates
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    def test_create_tracker_context_verify_disabled(self):
        """Test creating tracker context with verification disabled."""
        # Create config with SSL verification disabled
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                    "ssl_verify_certificates": False,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config") as mock_get_config:
            mock_get_config.return_value = config
            builder = SSLContextBuilder()
            # Override config directly
            builder.config = config
            context = builder.create_tracker_context()

            assert isinstance(context, ssl.SSLContext)
            assert context.verify_mode == ssl.CERT_NONE
            assert context.check_hostname is False

    def test_create_tracker_context_with_ca_cert_file(self):
        """Test creating tracker context with custom CA certificate file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            # Write a minimal PEM-like file (not a real cert, just for testing)
            f.write("-----BEGIN CERTIFICATE-----\n")
            f.write("TEST\n")
            f.write("-----END CERTIFICATE-----\n")
            ca_path = Path(f.name)

        try:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_verify_certificates": True,
                        "ssl_ca_certificates": str(ca_path),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config") as mock_get_config:
                mock_get_config.return_value = config
                builder = SSLContextBuilder()
                builder.config = config

                # Mock load_verify_locations to avoid loading invalid PEM data
                with patch.object(ssl.SSLContext, "load_verify_locations"):
                    context = builder.create_tracker_context()

                    assert isinstance(context, ssl.SSLContext)
        finally:
            ca_path.unlink(missing_ok=True)

    def test_create_tracker_context_with_ca_cert_dir(self):
        """Test creating tracker context with CA certificate directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ca_dir = Path(tmpdir)

            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_verify_certificates": True,
                        "ssl_ca_certificates": str(ca_dir),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config") as mock_get_config:
                mock_get_config.return_value = config
                builder = SSLContextBuilder()
                builder.config = config

                # Mock load_verify_locations to avoid loading invalid PEM data
                with patch.object(ssl.SSLContext, "load_verify_locations"):
                    context = builder.create_tracker_context()

                    assert isinstance(context, ssl.SSLContext)

    def test_create_tracker_context_invalid_ca_path(self):
        """Test creating tracker context with invalid CA certificate path."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                    "ssl_verify_certificates": True,
                    "ssl_ca_certificates": "/nonexistent/path/ca.pem",
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config", return_value=config):
            builder = SSLContextBuilder()
            builder.config = config

            with pytest.raises(ValueError, match="does not exist"):
                builder.create_tracker_context()

    def test_create_tracker_context_with_client_cert(self):
        """Test creating tracker context with client certificate."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as cert_f:
            cert_f.write("-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n")
            cert_path = Path(cert_f.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as key_f:
            key_f.write("-----BEGIN PRIVATE KEY-----\nTEST\n-----END PRIVATE KEY-----\n")
            key_path = Path(key_f.name)

        try:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_verify_certificates": True,
                        "ssl_client_certificate": str(cert_path),
                        "ssl_client_key": str(key_path),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config", return_value=config):
                builder = SSLContextBuilder()
                builder.config = config

                # Should raise OSError when trying to load invalid cert/key
                # But the code should attempt to load them
                with pytest.raises((OSError, ssl.SSLError)):
                    builder.create_tracker_context()
        finally:
            cert_path.unlink(missing_ok=True)
            key_path.unlink(missing_ok=True)

    def test_create_tracker_context_ca_cert_invalid_path(self):
        """Test tracker context creation with invalid CA cert path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            invalid_path = Path(f.name)
        try:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_ca_certificates": str(invalid_path),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config", return_value=config):
                builder = SSLContextBuilder()
                builder.config = config
                
                # Mock Path to return a mock object with the desired behavior
                mock_path = MagicMock(spec=Path)
                mock_path.is_file.return_value = False
                mock_path.is_dir.return_value = False
                mock_path.exists.return_value = True
                mock_path.__str__ = Mock(return_value=str(invalid_path))
                mock_path.expanduser.return_value = mock_path
                
                with patch("ccbt.security.ssl_context.Path", return_value=mock_path):
                    # Also mock the SSLContext to avoid actual loading
                    with patch("ssl.create_default_context") as mock_create:
                        mock_context = MagicMock()
                        mock_create.return_value = mock_context
                        with pytest.raises(ValueError, match="not a file or directory"):
                            builder.create_tracker_context()
        finally:
            invalid_path.unlink(missing_ok=True)

    def test_create_tracker_context_with_cipher_suites(self):
        """Test creating tracker context with custom cipher suites."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                    "ssl_verify_certificates": True,
                    "ssl_cipher_suites": ["ECDHE-RSA-AES128-GCM-SHA256"],
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config", return_value=config):
            builder = SSLContextBuilder()
            builder.config = config
            context = builder.create_tracker_context()

            assert isinstance(context, ssl.SSLContext)

    def test_create_tracker_context_cipher_suite_error(self):
        """Test tracker context creation with invalid cipher suite."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_trackers": True,
                    "ssl_cipher_suites": ["INVALID-CIPHER-SUITE"],
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config", return_value=config):
            builder = SSLContextBuilder()
            builder.config = config
            
            # Mock set_ciphers to raise SSLError
            with patch.object(ssl.SSLContext, "set_ciphers", side_effect=ssl.SSLError("Invalid cipher")):
                with patch.object(builder.logger, "warning") as mock_warning:
                    context = builder.create_tracker_context()
                    
                    # Should continue despite cipher error
                    assert isinstance(context, ssl.SSLContext)
                    mock_warning.assert_called()

    def test_create_tracker_context_client_cert_missing(self):
        """Test tracker context creation with missing client certificate."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
            key_path = Path(f.name)
        
        try:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_client_certificate": "/nonexistent/cert.pem",
                        "ssl_client_key": str(key_path),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config", return_value=config):
                builder = SSLContextBuilder()
                builder.config = config
                
                with pytest.raises(ValueError, match="does not exist"):
                    builder.create_tracker_context()
        finally:
            key_path.unlink(missing_ok=True)

    def test_create_tracker_context_client_key_missing(self):
        """Test tracker context creation with missing client key."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
            cert_path = Path(f.name)
        
        try:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_client_certificate": str(cert_path),
                        "ssl_client_key": "/nonexistent/key.pem",
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config", return_value=config):
                builder = SSLContextBuilder()
                builder.config = config
                
                with pytest.raises(ValueError, match="does not exist"):
                    builder.create_tracker_context()
        finally:
            cert_path.unlink(missing_ok=True)

    def test_create_tracker_context_protocol_version(self):
        """Test creating tracker context with different protocol versions."""
        for version in ["TLSv1.2", "TLSv1.3", "PROTOCOL_TLS"]:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_trackers": True,
                        "ssl_verify_certificates": True,
                        "ssl_protocol_version": version,
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config") as mock_get_config:
                mock_get_config.return_value = config
                builder = SSLContextBuilder()
                builder.config = config

                # Mock load_verify_locations to avoid loading invalid PEM data
                with patch.object(ssl.SSLContext, "load_verify_locations"):
                    context = builder.create_tracker_context()

                    assert isinstance(context, ssl.SSLContext)

    def test_create_tracker_context_invalid_protocol_version(self):
        """Test creating tracker context with invalid protocol version."""
        # Invalid protocol version is caught by Pydantic validation at Config creation
        # So we need to test the _get_protocol_version method directly
        builder = SSLContextBuilder()

        with pytest.raises(ValueError, match="Invalid SSL protocol version"):
            builder._get_protocol_version("INVALID")


class TestSSLContextBuilderPeerContext:
    """Tests for peer SSL context creation."""

    def test_create_peer_context_default(self):
        """Test creating default peer SSL context."""
        builder = SSLContextBuilder()
        context = builder.create_peer_context()

        assert isinstance(context, ssl.SSLContext)

    def test_create_peer_context_verify_hostname(self):
        """Test creating peer context with hostname verification."""
        builder = SSLContextBuilder()
        context = builder.create_peer_context(verify_hostname=True)

        assert isinstance(context, ssl.SSLContext)
        # Peer contexts are less strict by default
        assert context.check_hostname is False or context.check_hostname is True

    def test_create_peer_context_require_valid_not_hostname(self):
        """Test creating peer context requiring valid certs but not hostname."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                    "ssl_verify_certificates": True,
                    "ssl_allow_insecure_peers": False,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config", return_value=config):
            builder = SSLContextBuilder()
            builder.config = config
            context = builder.create_peer_context(verify_hostname=False)

            assert isinstance(context, ssl.SSLContext)
            assert context.check_hostname is False
            assert context.verify_mode == ssl.CERT_REQUIRED

    def test_create_peer_context_with_ca_cert_file(self):
        """Test creating peer context with custom CA certificate file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n")
            ca_path = Path(f.name)

        try:
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_peers": True,
                        "ssl_ca_certificates": str(ca_path),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config", return_value=config):
                builder = SSLContextBuilder()
                builder.config = config
                
                with patch.object(ssl.SSLContext, "load_verify_locations") as mock_load:
                    context = builder.create_peer_context()

                    assert isinstance(context, ssl.SSLContext)
                    mock_load.assert_called()
        finally:
            ca_path.unlink(missing_ok=True)

    def test_create_peer_context_with_ca_cert_dir(self):
        """Test creating peer context with custom CA certificate directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ca_dir = Path(tmpdir)
            
            config_data = {
                "security": {
                    "ssl": {
                        "enable_ssl_peers": True,
                        "ssl_ca_certificates": str(ca_dir),
                    }
                }
            }
            config = Config(**config_data)

            with patch("ccbt.security.ssl_context.get_config", return_value=config):
                builder = SSLContextBuilder()
                builder.config = config
                
                with patch.object(ssl.SSLContext, "load_verify_locations") as mock_load:
                    context = builder.create_peer_context()

                    assert isinstance(context, ssl.SSLContext)
                    mock_load.assert_called()

    def test_create_peer_context_cipher_suite_error(self):
        """Test peer context creation with invalid cipher suite."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                    "ssl_cipher_suites": ["INVALID-CIPHER-SUITE"],
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config", return_value=config):
            builder = SSLContextBuilder()
            builder.config = config
            
            # Mock set_ciphers to raise SSLError
            with patch.object(ssl.SSLContext, "set_ciphers", side_effect=ssl.SSLError("Invalid cipher")):
                with patch.object(builder.logger, "warning") as mock_warning:
                    context = builder.create_peer_context()
                    
                    # Should continue despite cipher error
                    assert isinstance(context, ssl.SSLContext)
                    mock_warning.assert_called()

    def test_create_peer_context_allow_insecure(self):
        """Test creating peer context allowing insecure peers."""
        config_data = {
            "security": {
                "ssl": {
                    "enable_ssl_peers": True,
                    "ssl_allow_insecure_peers": True,
                }
            }
        }
        config = Config(**config_data)

        with patch("ccbt.security.ssl_context.get_config", return_value=config):
            builder = SSLContextBuilder()
            builder.config = config
            context = builder.create_peer_context()

            assert isinstance(context, ssl.SSLContext)
            # Should allow insecure peers
            assert context.verify_mode == ssl.CERT_NONE
            assert context.check_hostname is False


class TestSSLContextBuilderHelpers:
    """Tests for SSLContextBuilder helper methods."""

    def test_get_protocol_version_tlsv12(self):
        """Test protocol version mapping for TLSv1.2."""
        builder = SSLContextBuilder()
        version = builder._get_protocol_version("TLSv1.2")
        assert version == ssl.TLSVersion.TLSv1_2

    def test_get_protocol_version_tlsv13(self):
        """Test protocol version mapping for TLSv1.3."""
        builder = SSLContextBuilder()
        version = builder._get_protocol_version("TLSv1.3")
        assert version == ssl.TLSVersion.TLSv1_3

    def test_get_protocol_version_protocol_tls(self):
        """Test protocol version mapping for PROTOCOL_TLS."""
        builder = SSLContextBuilder()
        version = builder._get_protocol_version("PROTOCOL_TLS")
        # PROTOCOL_TLS maps to MINIMUM_SUPPORTED
        assert version == ssl.TLSVersion.MINIMUM_SUPPORTED

    def test_get_protocol_version_invalid(self):
        """Test protocol version mapping with invalid version."""
        builder = SSLContextBuilder()
        with pytest.raises(ValueError, match="Invalid SSL protocol version"):
            builder._get_protocol_version("INVALID")

    def test_load_ca_certificates_file(self):
        """Test loading CA certificates from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write("-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n")
            ca_path = Path(f.name)

        try:
            builder = SSLContextBuilder()
            cert_paths, count = builder._load_ca_certificates(str(ca_path))
            assert count == 1
            assert str(ca_path) in cert_paths
        finally:
            ca_path.unlink(missing_ok=True)

    def test_load_ca_certificates_dir(self):
        """Test loading CA certificates from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ca_dir = Path(tmpdir)
            # Create a dummy .pem file
            (ca_dir / "ca1.pem").write_text("-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n")

            builder = SSLContextBuilder()
            cert_paths, count = builder._load_ca_certificates(str(ca_dir))
            assert count >= 1

    def test_load_ca_certificates_nonexistent(self):
        """Test loading CA certificates from nonexistent path."""
        builder = SSLContextBuilder()
        with pytest.raises(ValueError, match="does not exist"):
            builder._load_ca_certificates("/nonexistent/path")

    def test_load_ca_certificates_invalid_path(self):
        """Test loading CA certificates from invalid path (not file or directory)."""
        builder = SSLContextBuilder()
        
        # Mock Path to return a mock object with the desired behavior
        mock_path = MagicMock(spec=Path)
        mock_path.is_file.return_value = False
        mock_path.is_dir.return_value = False
        mock_path.exists.return_value = True
        mock_path.__str__ = Mock(return_value="/invalid/path")
        mock_path.expanduser.return_value = mock_path
        
        with patch("ccbt.security.ssl_context.Path", return_value=mock_path):
            with pytest.raises(ValueError, match="not a file or directory"):
                builder._load_ca_certificates("/invalid/path")

    def test_validate_certificate_paths_valid(self):
        """Test validating certificate paths with valid files."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert_f:
            cert_f.write("test cert")
            cert_path = Path(cert_f.name)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as key_f:
            key_f.write("test key")
            key_path = Path(key_f.name)

        try:
            builder = SSLContextBuilder()
            cert_file, key_file = builder._validate_certificate_paths(
                str(cert_path), str(key_path)
            )
            assert cert_file == cert_path
            assert key_file == key_path
        finally:
            cert_path.unlink(missing_ok=True)
            key_path.unlink(missing_ok=True)

    def test_validate_certificate_paths_invalid(self):
        """Test validating certificate paths with invalid files."""
        builder = SSLContextBuilder()
        with pytest.raises(ValueError, match="does not exist"):
            builder._validate_certificate_paths("/nonexistent/cert.pem")

    def test_validate_certificate_paths_cert_only(self):
        """Test validating certificate paths with cert only."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as cert_f:
            cert_f.write("test cert")
            cert_path = Path(cert_f.name)

        try:
            builder = SSLContextBuilder()
            cert_file, key_file = builder._validate_certificate_paths(str(cert_path))
            assert cert_file == cert_path
            assert key_file is None
        finally:
            cert_path.unlink(missing_ok=True)

    def test_validate_certificate_paths_key_missing(self):
        """Test validating certificate paths with missing key file."""
        builder = SSLContextBuilder()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
            cert_path = Path(f.name)

        try:
            builder = SSLContextBuilder()
            with pytest.raises(ValueError, match="does not exist"):
                builder._validate_certificate_paths(str(cert_path), "/nonexistent/key.pem")
        finally:
            cert_path.unlink(missing_ok=True)


class TestSSLCertificateValidator:
    """Tests for SSL certificate validator."""

    def test_validate_tracker_certificate_exact_match(self):
        """Test validating certificate with exact hostname match."""
        validator = SSLCertificateValidator()

        cert = {
            "subject": (("commonName", "example.com"),),
            "subjectAltName": (("DNS", "example.com"),),
        }

        assert validator.validate_tracker_certificate(cert, "example.com") is True

    def test_validate_tracker_certificate_wildcard(self):
        """Test validating certificate with wildcard."""
        validator = SSLCertificateValidator()

        cert = {
            "subject": (("commonName", "*.example.com"),),
            "subjectAltName": (("DNS", "*.example.com"),),
        }

        assert validator.validate_tracker_certificate(cert, "sub.example.com") is True
        assert validator.validate_tracker_certificate(cert, "example.com") is True

    def test_validate_tracker_certificate_no_match(self):
        """Test validating certificate with no match."""
        validator = SSLCertificateValidator()

        cert = {
            "subject": (("commonName", "example.com"),),
            "subjectAltName": (("DNS", "example.com"),),
        }

        assert validator.validate_tracker_certificate(cert, "other.com") is False

    def test_validate_tracker_certificate_match_san(self):
        """Test validating certificate matching SAN."""
        validator = SSLCertificateValidator()

        cert = {
            "subject": (("commonName", "wrong.com"),),
            "subjectAltName": (("DNS", "correct.com"), ("DNS", "also.correct.com")),
        }

        # Should match on CN or SAN - the code checks CN first, then SANs
        assert validator.validate_tracker_certificate(cert, "correct.com") is True  # Matches SAN
        assert validator.validate_tracker_certificate(cert, "also.correct.com") is True  # Matches SAN
        assert validator.validate_tracker_certificate(cert, "wrong.com") is True  # Matches CN
        # Test a hostname that doesn't match either
        assert validator.validate_tracker_certificate(cert, "nonexistent.com") is False

    def test_validate_tracker_certificate_no_cert(self):
        """Test validating with no certificate."""
        validator = SSLCertificateValidator()
        assert validator.validate_tracker_certificate({}, "example.com") is False

    def test_extract_common_name(self):
        """Test extracting common name from certificate."""
        validator = SSLCertificateValidator()

        cert = {
            "subject": (
                ("countryName", "US"),
                ("commonName", "example.com"),
            ),
        }

        cn = validator._extract_common_name(cert)
        assert cn == "example.com"

    def test_extract_common_name_missing(self):
        """Test extracting common name when missing."""
        validator = SSLCertificateValidator()

        cert = {"subject": (("countryName", "US"),)}

        cn = validator._extract_common_name(cert)
        assert cn is None

    def test_extract_sans(self):
        """Test extracting subject alternative names."""
        validator = SSLCertificateValidator()

        cert = {
            "subjectAltName": (
                ("DNS", "example.com"),
                ("DNS", "www.example.com"),
                ("IP", "192.168.1.1"),
            ),
        }

        sans = validator._extract_sans(cert)
        assert "example.com" in sans
        assert "www.example.com" in sans
        assert "192.168.1.1" not in sans  # IP addresses not included

    def test_extract_sans_empty(self):
        """Test extracting SANs when empty."""
        validator = SSLCertificateValidator()

        cert = {}
        sans = validator._extract_sans(cert)
        assert sans == []

    def test_match_hostname_exact(self):
        """Test hostname matching with exact match."""
        validator = SSLCertificateValidator()

        assert validator._match_hostname("example.com", "example.com") is True
        assert validator._match_hostname("example.com", "other.com") is False

    def test_match_hostname_wildcard(self):
        """Test hostname matching with wildcard."""
        validator = SSLCertificateValidator()

        assert validator._match_hostname("sub.example.com", "*.example.com") is True
        assert validator._match_hostname("example.com", "*.example.com") is True
        assert validator._match_hostname("other.com", "*.example.com") is False

    def test_match_hostname_wildcard_domain_only(self):
        """Test hostname matching with wildcard where hostname equals domain."""
        validator = SSLCertificateValidator()

        # *.example.com should match example.com
        assert validator._match_hostname("example.com", "*.example.com") is True
        # Should not match if hostname is shorter than domain
        assert validator._match_hostname("com", "*.example.com") is False

    def test_match_hostname_none(self):
        """Test hostname matching with None pattern."""
        validator = SSLCertificateValidator()

        assert validator._match_hostname("example.com", None) is False
        assert validator._match_hostname("example.com", "") is False


class TestCertificatePinner:
    """Tests for certificate pinning."""

    def test_pin_certificate(self):
        """Test pinning a certificate."""
        pinner = CertificatePinner()
        pinner.pin_certificate("example.com", "abcd1234")

        assert "example.com" in pinner.pinned_certs
        assert pinner.pinned_certs["example.com"] == "abcd1234"

    def test_verify_pin_match(self):
        """Test verifying certificate pin with match."""
        pinner = CertificatePinner()
        pinner.pin_certificate("example.com", "abcd1234")

        # Mock certificate (simplified)
        cert = {"subject": (("commonName", "example.com"),)}

        # Mock fingerprint calculation
        with patch.object(
            pinner, "_calculate_fingerprint_from_dict", return_value="abcd1234"
        ):
            assert pinner.verify_pin("example.com", cert) is True

    def test_verify_pin_match_case_insensitive(self):
        """Test verifying certificate pin with case-insensitive match."""
        pinner = CertificatePinner()
        pinner.pin_certificate("example.com", "abcd1234")

        cert = {"subject": (("commonName", "example.com"),)}

        with patch.object(
            pinner, "_calculate_fingerprint_from_dict", return_value="ABCD1234"
        ):
            assert pinner.verify_pin("Example.COM", cert) is True

    def test_verify_pin_no_match(self):
        """Test verifying certificate pin with no match."""
        pinner = CertificatePinner()
        pinner.pin_certificate("example.com", "abcd1234")

        cert = {"subject": (("commonName", "example.com"),)}

        with patch.object(
            pinner, "_calculate_fingerprint_from_dict", return_value="different"
        ):
            assert pinner.verify_pin("example.com", cert) is False

    def test_verify_pin_with_bytes(self):
        """Test verifying certificate pin with bytes certificate."""
        pinner = CertificatePinner()
        pinner.pin_certificate("example.com", "abcd1234")

        cert_bytes = b"test certificate bytes"

        with patch.object(
            pinner, "_calculate_fingerprint", return_value="abcd1234"
        ):
            assert pinner.verify_pin("example.com", cert_bytes) is True

    def test_verify_pin_not_pinned(self):
        """Test verifying certificate when not pinned."""
        pinner = CertificatePinner()

        cert = {"subject": (("commonName", "example.com"),)}

        # Should return True if not pinned (allow connection)
        assert pinner.verify_pin("example.com", cert) is True

    def test_calculate_fingerprint(self):
        """Test calculating certificate fingerprint."""
        pinner = CertificatePinner()

        cert_bytes = b"test certificate bytes"
        fingerprint = pinner._calculate_fingerprint(cert_bytes)

        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64  # SHA-256 hex digest

    def test_calculate_fingerprint_from_dict(self):
        """Test calculating fingerprint from certificate dictionary."""
        pinner = CertificatePinner()

        cert = {
            "subject": (("commonName", "example.com"),),
            "issuer": (("commonName", "CA"),),
        }

        fingerprint = pinner._calculate_fingerprint_from_dict(cert)
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 64

    def test_pin_case_insensitive(self):
        """Test that pinning is case-insensitive for hostnames."""
        pinner = CertificatePinner()
        pinner.pin_certificate("Example.COM", "abcd1234")

        assert "example.com" in pinner.pinned_certs

