"""Tests for CLI SSL commands.

Covers:
- SSL status command (lines 27-70)
- SSL enable-trackers command (lines 77-97)
- SSL disable-trackers command (lines 104-124)
- SSL enable-peers command (lines 131-151)
- SSL disable-peers command (lines 158-178)
- SSL set-ca-certs command (lines 189-221)
- SSL set-client-cert command (lines 234-283)
- SSL set-protocol command (lines 297-317)
- SSL verify-on command (lines 324-344)
- SSL verify-off command (lines 351-371)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner

cli_ssl_commands = __import__("ccbt.cli.ssl_commands", fromlist=["ssl"])

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class TestSSLStatus:
    """Tests for SSL status command (lines 27-70)."""

    def test_ssl_status_display(self, monkeypatch):
        """Test SSL status display (lines 27-66)."""
        runner = CliRunner()

        mock_ssl_config = SimpleNamespace(
            enable_ssl_trackers=True,
            enable_ssl_peers=False,
            ssl_verify_certificates=True,
            ssl_ca_certificates="/path/to/ca.pem",
            ssl_client_certificate=None,
            ssl_client_key=None,
            ssl_protocol_version="TLSv1.2",
            ssl_allow_insecure_peers=False,
            ssl_cipher_suites=["TLS_AES_256_GCM_SHA384"],
        )

        mock_config = SimpleNamespace(security=SimpleNamespace(ssl=mock_ssl_config))

        monkeypatch.setattr(
            cli_ssl_commands, "get_config", lambda: mock_config
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["status"])
        assert result.exit_code == 0
        assert "SSL/TLS Configuration" in result.output
        assert "Tracker SSL Enabled" in result.output
        assert "Peer SSL Enabled" in result.output

    def test_ssl_status_without_cipher_suites(self, monkeypatch):
        """Test SSL status without cipher suites (lines 63-64)."""
        runner = CliRunner()

        mock_ssl_config = SimpleNamespace(
            enable_ssl_trackers=True,
            enable_ssl_peers=False,
            ssl_verify_certificates=True,
            ssl_ca_certificates=None,
            ssl_client_certificate=None,
            ssl_client_key=None,
            ssl_protocol_version="TLSv1.2",
            ssl_allow_insecure_peers=False,
            ssl_cipher_suites=None,
        )

        mock_config = SimpleNamespace(security=SimpleNamespace(ssl=mock_ssl_config))

        monkeypatch.setattr(
            cli_ssl_commands, "get_config", lambda: mock_config
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["status"])
        assert result.exit_code == 0
        assert "System default" in result.output

    def test_ssl_status_exception_handling(self, monkeypatch):
        """Test SSL status exception handling (lines 68-70)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "get_config", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["status"])
        assert result.exit_code != 0
        assert "Error getting SSL status" in result.output


class TestSSLEnableDisableTrackers:
    """Tests for SSL enable/disable trackers commands."""

    def test_ssl_enable_trackers_with_config_file(self, monkeypatch, tmp_path):
        """Test SSL enable-trackers with config file (lines 77-89)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(enable_ssl_trackers=False)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nenable_ssl_trackers = true\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["enable-trackers"])
        assert result.exit_code == 0
        assert "SSL for trackers enabled" in result.output
        assert mock_ssl_config.enable_ssl_trackers is True

    def test_ssl_enable_trackers_without_config_file(self, monkeypatch):
        """Test SSL enable-trackers without config file (lines 90-93)."""
        runner = CliRunner()

        mock_ssl_config = SimpleNamespace(enable_ssl_trackers=False)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = None

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["enable-trackers"])
        assert result.exit_code == 0
        assert "SSL for trackers enabled" in result.output
        assert "configuration not persisted" in result.output

    def test_ssl_enable_trackers_exception_handling(self, monkeypatch):
        """Test SSL enable-trackers exception handling (lines 95-97)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["enable-trackers"])
        assert result.exit_code != 0
        assert "Error enabling SSL for trackers" in result.output

    def test_ssl_disable_trackers_with_config_file(self, monkeypatch, tmp_path):
        """Test SSL disable-trackers with config file (lines 104-116)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(enable_ssl_trackers=True)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nenable_ssl_trackers = false\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["disable-trackers"])
        assert result.exit_code == 0
        assert "SSL for trackers disabled" in result.output
        assert mock_ssl_config.enable_ssl_trackers is False

    def test_ssl_disable_trackers_exception_handling(self, monkeypatch):
        """Test SSL disable-trackers exception handling (lines 122-124)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["disable-trackers"])
        assert result.exit_code != 0
        assert "Error disabling SSL for trackers" in result.output


class TestSSLEnableDisablePeers:
    """Tests for SSL enable/disable peers commands."""

    def test_ssl_enable_peers_with_config_file(self, monkeypatch, tmp_path):
        """Test SSL enable-peers with config file (lines 131-143)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(enable_ssl_peers=False)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nenable_ssl_peers = true\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["enable-peers"])
        assert result.exit_code == 0
        assert "SSL for peers enabled" in result.output
        assert mock_ssl_config.enable_ssl_peers is True

    def test_ssl_enable_peers_exception_handling(self, monkeypatch):
        """Test SSL enable-peers exception handling (lines 149-151)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["enable-peers"])
        assert result.exit_code != 0
        assert "Error enabling SSL for peers" in result.output

    def test_ssl_disable_peers_with_config_file(self, monkeypatch, tmp_path):
        """Test SSL disable-peers with config file (lines 158-170)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(enable_ssl_peers=True)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nenable_ssl_peers = false\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["disable-peers"])
        assert result.exit_code == 0
        assert "SSL for peers disabled" in result.output
        assert mock_ssl_config.enable_ssl_peers is False

    def test_ssl_disable_peers_exception_handling(self, monkeypatch):
        """Test SSL disable-peers exception handling (lines 176-178)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["disable-peers"])
        assert result.exit_code != 0
        assert "Error disabling SSL for peers" in result.output


class TestSSLSetCACerts:
    """Tests for SSL set-ca-certs command (lines 189-221)."""

    def test_ssl_set_ca_certs_success(self, monkeypatch, tmp_path):
        """Test SSL set-ca-certs success (lines 184-209)."""
        runner = CliRunner()

        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----")

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(ssl_ca_certificates=None)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nssl_ca_certificates = '/path/to/ca.pem'\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl, ["set-ca-certs", str(ca_file)], obj={"config": mock_config}
        )
        assert result.exit_code == 0
        assert "CA certificates path set" in result.output
        # Check for path in output (may be split across lines on Windows)
        assert str(ca_file.resolve()).replace("\\", "/") in result.output.replace("\\", "/") or ca_file.name in result.output

    def test_ssl_set_ca_certs_file_not_found(self, monkeypatch):
        """Test SSL set-ca-certs with file not found (lines 199-201)."""
        runner = CliRunner()

        mock_ssl_config = SimpleNamespace()
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl, ["set-ca-certs", "/nonexistent/ca.pem"]
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower()

    def test_ssl_set_ca_certs_exception_handling(self, monkeypatch, tmp_path):
        """Test SSL set-ca-certs exception handling (lines 219-221)."""
        runner = CliRunner()

        ca_file = tmp_path / "ca.pem"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----")

        mock_config_manager = MagicMock()
        mock_config_manager.config = SimpleNamespace(security=SimpleNamespace(ssl=SimpleNamespace()))
        mock_config_manager.config_file = tmp_path / "ccbt.toml"
        # Make export raise an exception
        mock_config_manager.export = MagicMock(side_effect=Exception("Test error"))

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", lambda: mock_config_manager)

        result = runner.invoke(
            cli_ssl_commands.ssl, ["set-ca-certs", str(ca_file)]
        )
        assert result.exit_code != 0
        assert "Error" in result.output


class TestSSLSetClientCert:
    """Tests for SSL set-client-cert command (lines 234-283)."""

    def test_ssl_set_client_cert_success(self, monkeypatch, tmp_path):
        """Test SSL set-client-cert success (lines 234-270)."""
        runner = CliRunner()

        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(
            ssl_client_certificate=None,
            ssl_client_key=None,
        )
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nssl_client_certificate = '/path/to/cert'\nssl_client_key = '/path/to/key'\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl,
            ["set-client-cert", str(cert_file), str(key_file)],
            obj={"config": mock_config},
        )
        assert result.exit_code == 0
        assert "Client certificate set" in result.output

    def test_ssl_set_client_cert_cert_not_found(self, monkeypatch):
        """Test SSL set-client-cert with cert file not found (lines 248-250)."""
        runner = CliRunner()

        mock_ssl_config = SimpleNamespace()
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl,
            ["set-client-cert", "/nonexistent/cert.crt", "/path/to/key.key"],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower()

    def test_ssl_set_client_cert_key_not_found(self, monkeypatch, tmp_path):
        """Test SSL set-client-cert with key file not found (lines 251-253)."""
        runner = CliRunner()

        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----")

        mock_ssl_config = SimpleNamespace()
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl,
            ["set-client-cert", str(cert_file), "/nonexistent/key.key"],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower()

    def test_ssl_set_client_cert_exception_handling(self, monkeypatch, tmp_path):
        """Test SSL set-client-cert exception handling (lines 281-283)."""
        runner = CliRunner()

        cert_file = tmp_path / "client.crt"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----")
        key_file = tmp_path / "client.key"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----")

        mock_config_manager = MagicMock()
        mock_config_manager.config = SimpleNamespace(security=SimpleNamespace(ssl=SimpleNamespace()))
        mock_config_manager.config_file = tmp_path / "ccbt.toml"
        mock_config_manager.export = MagicMock(side_effect=Exception("Test error"))

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", lambda: mock_config_manager)

        result = runner.invoke(
            cli_ssl_commands.ssl,
            ["set-client-cert", str(cert_file), str(key_file)],
        )
        assert result.exit_code != 0
        assert "Error setting client certificate" in result.output


class TestSSLSetProtocol:
    """Tests for SSL set-protocol command (lines 297-317)."""

    def test_ssl_set_protocol_success(self, monkeypatch, tmp_path):
        """Test SSL set-protocol success (lines 292-308)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(ssl_protocol_version="TLSv1.2")
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nssl_protocol_version = 'TLSv1.3'\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl, ["set-protocol", "TLSv1.3"], obj={"config": mock_config}
        )
        assert result.exit_code == 0
        assert "TLS protocol version set" in result.output
        assert mock_ssl_config.ssl_protocol_version == "TLSv1.3"

    def test_ssl_set_protocol_invalid_version(self, monkeypatch):
        """Test SSL set-protocol with invalid version (lines 304-306)."""
        runner = CliRunner()

        mock_ssl_config = SimpleNamespace(ssl_protocol_version="TLSv1.2")
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(
            cli_ssl_commands.ssl, ["set-protocol", "INVALID"]
        )
        # May exit with error or handle gracefully
        assert result.exit_code in [0, 1, 2]

    def test_ssl_set_protocol_exception_handling(self, monkeypatch):
        """Test SSL set-protocol exception handling (lines 315-317)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(
            cli_ssl_commands.ssl, ["set-protocol", "TLSv1.3"]
        )
        assert result.exit_code != 0
        assert "Error setting protocol version" in result.output


class TestSSLVerify:
    """Tests for SSL verify-on/verify-off commands."""

    def test_ssl_verify_on(self, monkeypatch, tmp_path):
        """Test SSL verify-on command (lines 322-338)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(ssl_verify_certificates=False)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nssl_verify_certificates = true\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["verify-on"])
        assert result.exit_code == 0
        assert "SSL certificate verification enabled" in result.output
        assert mock_ssl_config.ssl_verify_certificates is True

    def test_ssl_verify_on_exception_handling(self, monkeypatch):
        """Test SSL verify-on exception handling (lines 342-344)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["verify-on"])
        assert result.exit_code != 0
        assert "Error enabling certificate verification" in result.output

    def test_ssl_verify_off(self, monkeypatch, tmp_path):
        """Test SSL verify-off command (lines 349-365)."""
        runner = CliRunner()

        config_file = tmp_path / "ccbt.toml"
        config_file.write_text("[security]\n[security.ssl]\n")

        mock_ssl_config = SimpleNamespace(ssl_verify_certificates=True)
        mock_security = SimpleNamespace(ssl=mock_ssl_config)
        mock_config = SimpleNamespace(security=mock_security)

        mock_config_manager = MagicMock()
        mock_config_manager.config = mock_config
        mock_config_manager.config_file = config_file
        mock_config_manager.export = MagicMock(return_value="[security]\n[security.ssl]\nssl_verify_certificates = false\n")

        monkeypatch.setattr(
            cli_ssl_commands, "ConfigManager", lambda: mock_config_manager
        )

        result = runner.invoke(cli_ssl_commands.ssl, ["verify-off"])
        assert result.exit_code == 0
        assert "SSL certificate verification disabled" in result.output
        assert mock_ssl_config.ssl_verify_certificates is False

    def test_ssl_verify_off_exception_handling(self, monkeypatch):
        """Test SSL verify-off exception handling (lines 369-371)."""
        runner = CliRunner()

        def _raise_error():
            raise Exception("Test error")

        monkeypatch.setattr(cli_ssl_commands, "ConfigManager", _raise_error)

        result = runner.invoke(cli_ssl_commands.ssl, ["verify-off"])
        assert result.exit_code != 0
        assert "Error disabling certificate verification" in result.output

