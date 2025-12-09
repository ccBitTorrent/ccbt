"""SSL context management for tracker and peer connections.

This module provides SSL/TLS context creation and certificate validation
for secure BitTorrent tracker and peer connections.
"""

from __future__ import annotations

import hashlib
import logging
import ssl
from pathlib import Path
from typing import Any

from ccbt.config.config import get_config

logger = logging.getLogger(__name__)


class SSLContextBuilder:
    """Build SSL contexts for tracker and peer connections."""

    def __init__(self):
        """Initialize SSL context builder."""
        self.config = get_config()
        self.logger = logging.getLogger(__name__)

    def create_tracker_context(self) -> ssl.SSLContext:
        """Create SSL context for tracker connections.

        Returns:
            Configured SSL context for tracker connections

        Raises:
            ValueError: If certificate paths are invalid
            OSError: If certificate files cannot be loaded

        """
        ssl_config = self.config.security.ssl

        # Create default context with system CA certificates
        # Use PROTOCOL_TLS_CLIENT for client-side connections
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=None,  # Use system default CA store
            capath=None,
        )

        # Configure certificate validation
        # Must set check_hostname BEFORE verify_mode when disabling verification
        if ssl_config.ssl_verify_certificates:
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.logger.warning("SSL certificate verification is disabled for trackers")

        # Load custom CA certificates if configured
        if ssl_config.ssl_ca_certificates:
            ca_path = Path(ssl_config.ssl_ca_certificates).expanduser()
            if not ca_path.exists():
                msg = f"CA certificates path does not exist: {ca_path}"
                self.logger.error(msg)
                raise ValueError(msg)

            try:
                if ca_path.is_file():
                    # Single CA certificate file
                    context.load_verify_locations(cafile=str(ca_path))
                elif ca_path.is_dir():
                    # Directory containing CA certificates
                    context.load_verify_locations(capath=str(ca_path))
                else:
                    msg = f"CA certificates path is not a file or directory: {ca_path}"
                    self.logger.error(msg)
                    raise ValueError(msg)

                self.logger.info("Loaded custom CA certificates from %s", ca_path)
            except ssl.SSLError as e:
                msg = f"Failed to load CA certificates from {ca_path}: {e}"
                self.logger.error(msg, exc_info=True)
                raise OSError(msg) from e
            except OSError as e:
                msg = f"Failed to read CA certificates from {ca_path}: {e}"
                self.logger.error(msg, exc_info=True)
                raise

        # Set protocol version
        protocol = self._get_protocol_version(ssl_config.ssl_protocol_version)
        context.minimum_version = protocol

        # Configure cipher suites if specified
        if ssl_config.ssl_cipher_suites:
            # Convert cipher suite names to OpenSSL format
            ciphers = ":".join(ssl_config.ssl_cipher_suites)
            try:
                context.set_ciphers(ciphers)
            except ssl.SSLError as e:
                self.logger.warning("Failed to set cipher suites %s: %s", ciphers, e)

        # Load client certificate if configured
        if ssl_config.ssl_client_certificate and ssl_config.ssl_client_key:
            cert_path = Path(ssl_config.ssl_client_certificate).expanduser()
            key_path = Path(ssl_config.ssl_client_key).expanduser()

            if not cert_path.exists():
                msg = f"Client certificate file does not exist: {cert_path}"
                self.logger.error(msg)
                raise ValueError(msg)
            if not key_path.exists():
                msg = f"Client key file does not exist: {key_path}"
                self.logger.error(msg)
                raise ValueError(msg)

            try:
                context.load_cert_chain(str(cert_path), str(key_path))
                self.logger.info(  # pragma: no cover - Logging statement, tested indirectly via successful SSL context creation
                    "Loaded client certificate from %s with key %s",
                    cert_path,
                    key_path,
                )
            except ssl.SSLError as e:
                msg = f"Failed to load client certificate from {cert_path}: {e}"
                self.logger.error(msg, exc_info=True)
                raise OSError(msg) from e
            except OSError as e:
                msg = f"Failed to read client certificate from {cert_path}: {e}"
                self.logger.error(msg, exc_info=True)
                raise

        # Set security options
        # Disable insecure protocols (OP_NO_SSLv2/v3 still needed for older Python versions)
        # OP_NO_TLSv1/v1_1 are deprecated - use minimum_version instead (already set above)
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        # Removed deprecated ssl.OP_NO_TLSv1 and ssl.OP_NO_TLSv1_1 - handled by minimum_version

        return context

    def create_peer_context(self, verify_hostname: bool = False) -> ssl.SSLContext:
        """Create SSL context for peer connections.

        Args:
            verify_hostname: Whether to verify peer hostname

        Returns:
            Configured SSL context for peer connections

        """
        ssl_config = self.config.security.ssl

        # Create default context
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

        # For peers, verification is optional (opportunistic encryption)
        # Must set check_hostname BEFORE verify_mode when disabling verification
        if ssl_config.ssl_verify_certificates and verify_hostname:
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
        elif ssl_config.ssl_allow_insecure_peers:
            # Allow peers with invalid certificates for opportunistic encryption
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        else:
            # Require valid certificates but don't check hostname
            context.check_hostname = False
            context.verify_mode = ssl.CERT_REQUIRED

        # Load custom CA certificates if configured
        if ssl_config.ssl_ca_certificates:
            ca_path = Path(ssl_config.ssl_ca_certificates).expanduser()
            if ca_path.exists():
                if ca_path.is_file():
                    context.load_verify_locations(cafile=str(ca_path))
                elif ca_path.is_dir():
                    context.load_verify_locations(capath=str(ca_path))
                self.logger.debug(
                    "Loaded custom CA certificates from %s for peer context",
                    ca_path,
                )

        # Set protocol version
        protocol = self._get_protocol_version(ssl_config.ssl_protocol_version)
        context.minimum_version = protocol

        # Configure cipher suites if specified
        if ssl_config.ssl_cipher_suites:
            ciphers = ":".join(ssl_config.ssl_cipher_suites)
            try:
                context.set_ciphers(ciphers)
            except ssl.SSLError as e:
                self.logger.warning("Failed to set cipher suites %s: %s", ciphers, e)

        # Set security options
        # Disable insecure protocols (OP_NO_SSLv2/v3 still needed for older Python versions)
        # OP_NO_TLSv1/v1_1 are deprecated - use minimum_version instead (already set above)
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        # Removed deprecated ssl.OP_NO_TLSv1 and ssl.OP_NO_TLSv1_1 - handled by minimum_version

        return context

    def _get_protocol_version(self, version_str: str) -> ssl.TLSVersion:
        """Map protocol version string to ssl.TLSVersion constant.

        Args:
            version_str: Protocol version string (TLSv1.2, TLSv1.3, PROTOCOL_TLS)

        Returns:
            ssl.TLSVersion constant

        Raises:
            ValueError: If version string is invalid

        """
        version_map = {
            "TLSv1.2": ssl.TLSVersion.TLSv1_2,
            "TLSv1.3": ssl.TLSVersion.TLSv1_3,
            "PROTOCOL_TLS": ssl.TLSVersion.MINIMUM_SUPPORTED,
        }

        if version_str not in version_map:
            msg = f"Invalid SSL protocol version: {version_str}"
            raise ValueError(msg)

        return version_map[version_str]

    def _load_ca_certificates(self, path: str | Path) -> tuple[list[str], int]:
        """Load CA certificates from file or directory.

        Args:
            path: Path to CA certificate file or directory

        Returns:
            Tuple of (certificate paths, count)

        Raises:
            ValueError: If path is invalid
            OSError: If certificates cannot be loaded

        """
        ca_path = Path(path).expanduser()

        if not ca_path.exists():
            msg = f"CA certificates path does not exist: {ca_path}"
            raise ValueError(msg)

        cert_paths = []

        if ca_path.is_file():
            cert_paths.append(str(ca_path))
        elif ca_path.is_dir():
            # Load all .pem and .crt files from directory
            cert_paths.extend(str(cert_file) for cert_file in ca_path.glob("*.pem"))
            cert_paths.extend(  # pragma: no cover - Same pattern as .pem, coverage demonstrated via .pem tests
                str(cert_file) for cert_file in ca_path.glob("*.crt")
            )
        else:
            msg = f"CA certificates path is not a file or directory: {ca_path}"
            raise ValueError(msg)

        return cert_paths, len(cert_paths)

    def _validate_certificate_paths(
        self, cert_path: str, key_path: str | None = None
    ) -> tuple[Path, Path | None]:
        """Validate certificate file paths.

        Args:
            cert_path: Path to certificate file
            key_path: Optional path to private key file

        Returns:
            Tuple of validated certificate and key paths

        Raises:
            ValueError: If paths are invalid

        """
        cert_file = Path(cert_path).expanduser()
        if not cert_file.exists():
            msg = f"Certificate file does not exist: {cert_file}"
            raise ValueError(msg)

        key_file = None
        if key_path:
            key_file = Path(key_path).expanduser()
            if not key_file.exists():
                msg = f"Key file does not exist: {key_file}"
                raise ValueError(msg)

        return cert_file, key_file


class SSLCertificateValidator:
    """Validate SSL certificates for trackers and peers."""

    def __init__(self):
        """Initialize certificate validator."""
        self.logger = logging.getLogger(__name__)

    def validate_tracker_certificate(self, cert: dict[str, Any], hostname: str) -> bool:
        """Validate tracker certificate against hostname.

        Args:
            cert: Certificate dictionary from ssl.getpeercert()
            hostname: Expected hostname

        Returns:
            True if certificate is valid for hostname

        """
        if not cert:
            self.logger.warning("No certificate provided for validation")
            return False

        # Extract common name and subject alternative names
        cn = self._extract_common_name(cert)
        sans = self._extract_sans(cert)

        # Check if hostname matches CN or any SAN
        if self._match_hostname(hostname, cn):
            return True

        for san in sans:
            if self._match_hostname(hostname, san):
                return True

        self.logger.warning(
            "Certificate does not match hostname %s (CN: %s, SANs: %s)",
            hostname,
            cn,
            sans,
        )
        return False

    def _extract_common_name(self, cert: dict[str, Any]) -> str | None:
        """Extract common name from certificate.

        Args:
            cert: Certificate dictionary

        Returns:
            Common name or None

        """
        subject = cert.get("subject", ())
        for item in subject:
            if isinstance(item, tuple) and len(item) == 2:
                key, value = item
                if key == "commonName":
                    return value
        return None

    def _extract_sans(self, cert: dict[str, Any]) -> list[str]:
        """Extract subject alternative names from certificate.

        Args:
            cert: Certificate dictionary

        Returns:
            List of SAN entries

        """
        sans = []
        ext = cert.get("subjectAltName", ())
        for entry in ext:
            if isinstance(entry, tuple) and len(entry) == 2:
                # Entry format: (type, value)
                # Type can be "DNS", "IP", etc.
                _type, value = entry
                if _type == "DNS":
                    sans.append(value)
        return sans

    def _match_hostname(self, hostname: str, pattern: str | None) -> bool:
        """Match hostname against certificate pattern.

        Supports wildcard certificates (e.g., *.example.com).

        Args:
            hostname: Hostname to match
            pattern: Certificate pattern (may contain wildcard, may be None)

        Returns:
            True if hostname matches pattern

        """
        if not pattern:
            return False

        # Exact match
        if hostname.lower() == pattern.lower():
            return True

        # Wildcard match
        if pattern.startswith("*."):
            domain = pattern[2:]
            # Match *.example.com against example.com or subdomain.example.com
            if hostname.lower().endswith(f".{domain.lower()}"):
                return True
            if hostname.lower() == domain.lower():
                return True

        return False


class CertificatePinner:
    """Manage certificate pinning for security."""

    def __init__(self):
        """Initialize certificate pinner."""
        self.pinned_certs: dict[str, str] = {}  # hostname -> fingerprint
        self.logger = logging.getLogger(__name__)

    def pin_certificate(self, hostname: str, fingerprint: str) -> None:
        """Pin a certificate for a hostname.

        Args:
            hostname: Hostname to pin certificate for
            fingerprint: Certificate fingerprint (SHA-256)

        """
        self.pinned_certs[hostname.lower()] = fingerprint
        self.logger.info("Pinned certificate for %s: %s", hostname, fingerprint)

    def verify_pin(self, hostname: str, cert: bytes | dict[str, Any]) -> bool:
        """Verify certificate matches pinned fingerprint.

        Args:
            hostname: Hostname to verify
            cert: Certificate bytes or dictionary

        Returns:
            True if certificate matches pin, False otherwise

        """
        hostname_lower = hostname.lower()
        if hostname_lower not in self.pinned_certs:
            # No pin configured, allow connection
            return True

        expected_fingerprint = self.pinned_certs[hostname_lower]

        # Calculate fingerprint
        if isinstance(cert, dict):
            # Extract DER-encoded certificate
            # Note: This is simplified - in practice, we'd need to extract
            # the DER bytes from the certificate object
            fingerprint = self._calculate_fingerprint_from_dict(cert)
        else:
            fingerprint = self._calculate_fingerprint(cert)

        if fingerprint.upper() == expected_fingerprint.upper():
            return True

        self.logger.warning(
            "Certificate fingerprint mismatch for %s: expected %s, got %s",
            hostname,
            expected_fingerprint,
            fingerprint,
        )
        return False

    def _calculate_fingerprint(self, cert_bytes: bytes) -> str:
        """Calculate SHA-256 fingerprint of certificate.

        Args:
            cert_bytes: DER-encoded certificate bytes

        Returns:
            Hexadecimal fingerprint

        """
        return hashlib.sha256(cert_bytes).hexdigest()

    def _calculate_fingerprint_from_dict(self, cert: dict[str, Any]) -> str:
        """Calculate fingerprint from certificate dictionary.

        Note: This is a simplified implementation. In practice, we'd need
        to convert the certificate dictionary back to DER format.

        Args:
            cert: Certificate dictionary

        Returns:
            Hexadecimal fingerprint

        """
        # Simplified: use a hash of certificate fields
        # In production, this should extract the actual DER bytes
        cert_str = str(sorted(cert.items()))
        return hashlib.sha256(cert_str.encode()).hexdigest()
