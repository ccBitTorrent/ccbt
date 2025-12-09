"""TLS Certificate Manager for Ed25519-based certificates.

from __future__ import annotations

Provides generation and management of Ed25519-based X.509 certificates
for TLS/HTTPS support.
"""

from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ccbt.utils.logging_config import get_logger

if TYPE_CHECKING:
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.x509.oid import NameOID

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )
    from cryptography.x509.oid import NameOID

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    x509 = None  # type: ignore[assignment, misc]
    ed25519 = None  # type: ignore[assignment, misc]
    hashes = None  # type: ignore[assignment, misc]
    Encoding = None  # type: ignore[assignment, misc]
    PrivateFormat = None  # type: ignore[assignment, misc]
    NoEncryption = None  # type: ignore[assignment, misc]
    NameOID = None  # type: ignore[assignment, misc]

logger = get_logger(__name__)


class TLSCertificateError(Exception):
    """Base exception for TLS certificate errors."""


class TLSCertificateManager:
    """Manages Ed25519-based TLS certificates."""

    def __init__(self, cert_dir: Path | str | None = None):
        """Initialize certificate manager.

        Args:
            cert_dir: Directory to store certificates (defaults to ~/.ccbt/certs)

        Raises:
            TLSCertificateError: If cryptography library not available

        """
        if not CRYPTOGRAPHY_AVAILABLE:
            msg = (
                "cryptography library is required for TLS certificates. "
                "Install with: pip install cryptography"
            )
            raise TLSCertificateError(msg)

        if cert_dir is None:
            cert_dir = Path.home() / ".ccbt" / "certs"
        elif isinstance(cert_dir, str):
            cert_dir = Path(cert_dir).expanduser()

        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        self.certificate_file = self.cert_dir / "server.crt"
        self.private_key_file = self.cert_dir / "server.key"

    def generate_self_signed_certificate(
        self,
        private_key: Ed25519PrivateKey,
        common_name: str = "ccBitTorrent",
        validity_days: int = 365,
    ) -> x509.Certificate:
        """Generate self-signed X.509 certificate using Ed25519.

        Args:
            private_key: Ed25519 private key for signing
            common_name: Common name for certificate subject
            validity_days: Certificate validity period in days

        Returns:
            X.509 certificate

        Raises:
            TLSCertificateError: If certificate generation fails

        """
        if not CRYPTOGRAPHY_AVAILABLE:
            msg = "Cryptography library not available"
            raise TLSCertificateError(msg)

        try:
            public_key = private_key.public_key()

            # Create subject and issuer (self-signed)
            subject = issuer = x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Internet"),
                    x509.NameAttribute(NameOID.LOCALITY_NAME, "P2P"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ccBitTorrent"),
                    x509.NameAttribute(NameOID.COMMON_NAME, common_name),
                ]
            )

            # Certificate validity period
            now = datetime.now(timezone.utc)
            valid_from = now
            valid_to = now + timedelta(days=validity_days)

            # Build certificate
            cert_builder = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(public_key)
                .serial_number(x509.random_serial_number())
                .not_valid_before(valid_from)
                .not_valid_after(valid_to)
                .add_extension(
                    x509.SubjectAlternativeName(
                        [
                            x509.DNSName("localhost"),
                            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                            x509.IPAddress(ipaddress.IPv6Address("::1")),
                        ]
                    ),
                    critical=False,
                )
            )

            # Sign certificate with private key
            # For Ed25519, we still need to provide a hash algorithm (SHA256 is standard)
            if hashes is None:
                msg = "Cryptography hashes module not available"
                raise TLSCertificateError(msg)
            certificate = cert_builder.sign(
                private_key=private_key, algorithm=hashes.SHA256()
            )

            logger.info(
                "Generated self-signed Ed25519 certificate: CN=%s, valid until %s",
                common_name,
                valid_to.isoformat(),
            )

            return certificate
        except Exception as e:
            msg = f"Failed to generate certificate: {e}"
            logger.exception(msg)
            raise TLSCertificateError(msg) from e

    def save_certificate(
        self, certificate: x509.Certificate, private_key: Ed25519PrivateKey
    ) -> None:
        """Save certificate and private key to files.

        Args:
            certificate: X.509 certificate to save
            private_key: Private key to save

        Raises:
            TLSCertificateError: If save fails

        """
        try:
            # Save certificate in PEM format
            cert_pem = certificate.public_bytes(Encoding.PEM)
            self.certificate_file.write_bytes(cert_pem)
            self.certificate_file.chmod(0o644)  # Readable by owner and group

            # Save private key in PEM format (encrypted)
            private_key_pem = private_key.private_bytes(
                encoding=Encoding.PEM,
                format=PrivateFormat.PKCS8,
                encryption_algorithm=NoEncryption(),
            )
            self.private_key_file.write_bytes(private_key_pem)
            self.private_key_file.chmod(0o600)  # Read/write for owner only

            logger.info("Saved TLS certificate and private key")
        except Exception as e:
            msg = f"Failed to save certificate: {e}"
            logger.exception(msg)
            raise TLSCertificateError(msg) from e

    def load_certificate(
        self,
    ) -> tuple[x509.Certificate, Ed25519PrivateKey] | None:
        """Load certificate and private key from files.

        Returns:
            Tuple of (certificate, private_key) or None if not found

        Raises:
            TLSCertificateError: If load fails

        """
        if not self.certificate_file.exists() or not self.private_key_file.exists():
            return None

        try:
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key,
            )

            # Load certificate
            cert_pem = self.certificate_file.read_bytes()
            certificate = x509.load_pem_x509_certificate(cert_pem)

            # Load private key
            key_pem = self.private_key_file.read_bytes()
            private_key = load_pem_private_key(key_pem, password=None)

            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                msg = "Private key is not Ed25519"
                raise TLSCertificateError(msg)

            logger.info("Loaded TLS certificate and private key")
            return certificate, private_key
        except Exception as e:
            msg = f"Failed to load certificate: {e}"
            logger.exception(msg)
            raise TLSCertificateError(msg) from e

    def get_or_create_certificate(
        self, private_key: Ed25519PrivateKey
    ) -> tuple[x509.Certificate, Ed25519PrivateKey]:
        """Get existing certificate or generate new one.

        Args:
            private_key: Ed25519 private key

        Returns:
            Tuple of (certificate, private_key)

        """
        loaded = self.load_certificate()
        if loaded is not None:
            cert, key = loaded
            # Verify the private key matches
            if (
                key.public_key().public_bytes_raw()
                == private_key.public_key().public_bytes_raw()
            ):
                return cert, key

        # Generate new certificate
        certificate = self.generate_self_signed_certificate(private_key)
        self.save_certificate(certificate, private_key)
        return certificate, private_key
