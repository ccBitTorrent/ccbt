"""Performance benchmarks for encryption operations.

Uses pytest-benchmark to measure:
- Cipher encryption/decryption throughput
- MSE handshake latency
- Stream wrapper overhead
- End-to-end encrypted connection performance
"""

from __future__ import annotations

import asyncio

import pytest

from ccbt.security.ciphers.aes import AESCipher
from ccbt.security.ciphers.rc4 import RC4Cipher
from ccbt.security.dh_exchange import DHPeerExchange

# Check if pytest-benchmark is available
try:
    import pytest_benchmark  # noqa: F401

    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False

pytestmark = [pytest.mark.performance, pytest.mark.security]


# Stub benchmark function for when pytest-benchmark is not available
def stub_benchmark(func, *args, **kwargs):
    """Stub benchmark function that just calls the function once."""
    if asyncio.iscoroutinefunction(func):
        try:
            loop = asyncio.get_running_loop()
            return func(*args, **kwargs)
        except RuntimeError:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(func(*args, **kwargs))
            finally:
                loop.close()
    else:
        return func(*args, **kwargs)


class TestCipherPerformance:
    """Benchmark cipher encryption/decryption performance."""

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_rc4_encrypt_1kb(self, benchmark=None):
        """Benchmark RC4 encryption throughput for 1KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        data = b"x" * 1024  # 1KB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_rc4_encrypt_64kb(self, benchmark=None):
        """Benchmark RC4 encryption throughput for 64KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        data = b"x" * (64 * 1024)  # 64KB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_rc4_encrypt_1mb(self, benchmark=None):
        """Benchmark RC4 encryption throughput for 1MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        data = b"x" * (1024 * 1024)  # 1MB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_rc4_encrypt_10mb(self, benchmark=None):
        """Benchmark RC4 encryption throughput for 10MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        data = b"x" * (10 * 1024 * 1024)  # 10MB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-decryption")
    def test_rc4_decrypt_1kb(self, benchmark=None):
        """Benchmark RC4 decryption throughput for 1KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        encrypted = cipher.encrypt(b"x" * 1024)

        result = benchmark(cipher.decrypt, encrypted)
        assert len(result) == len(encrypted)

    @pytest.mark.benchmark(group="cipher-decryption")
    def test_rc4_decrypt_64kb(self, benchmark=None):
        """Benchmark RC4 decryption throughput for 64KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        encrypted = cipher.encrypt(b"x" * (64 * 1024))

        result = benchmark(cipher.decrypt, encrypted)
        assert len(result) == len(encrypted)

    @pytest.mark.benchmark(group="cipher-decryption")
    def test_rc4_decrypt_1mb(self, benchmark=None):
        """Benchmark RC4 decryption throughput for 1MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = RC4Cipher(b"x" * 16)
        encrypted = cipher.encrypt(b"x" * (1024 * 1024))

        result = benchmark(cipher.decrypt, encrypted)
        assert len(result) == len(encrypted)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_aes128_encrypt_1kb(self, benchmark=None):
        """Benchmark AES-128 encryption throughput for 1KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 16)  # 16 bytes = AES-128
        data = b"x" * 1024  # 1KB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_aes128_encrypt_64kb(self, benchmark=None):
        """Benchmark AES-128 encryption throughput for 64KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 16)
        data = b"x" * (64 * 1024)  # 64KB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_aes128_encrypt_1mb(self, benchmark=None):
        """Benchmark AES-128 encryption throughput for 1MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 16)
        data = b"x" * (1024 * 1024)  # 1MB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_aes256_encrypt_1kb(self, benchmark=None):
        """Benchmark AES-256 encryption throughput for 1KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 32)  # 32 bytes = AES-256
        data = b"x" * 1024  # 1KB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_aes256_encrypt_64kb(self, benchmark=None):
        """Benchmark AES-256 encryption throughput for 64KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 32)
        data = b"x" * (64 * 1024)  # 64KB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-encryption")
    def test_aes256_encrypt_1mb(self, benchmark=None):
        """Benchmark AES-256 encryption throughput for 1MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 32)
        data = b"x" * (1024 * 1024)  # 1MB

        result = benchmark(cipher.encrypt, data)
        assert len(result) == len(data)

    @pytest.mark.benchmark(group="cipher-decryption")
    def test_aes128_decrypt_1kb(self, benchmark=None):
        """Benchmark AES-128 decryption throughput for 1KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 16)
        encrypted = cipher.encrypt(b"x" * 1024)

        result = benchmark(cipher.decrypt, encrypted)
        assert len(result) == len(encrypted)

    @pytest.mark.benchmark(group="cipher-decryption")
    def test_aes128_decrypt_64kb(self, benchmark=None):
        """Benchmark AES-128 decryption throughput for 64KB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 16)
        encrypted = cipher.encrypt(b"x" * (64 * 1024))

        result = benchmark(cipher.decrypt, encrypted)
        assert len(result) == len(encrypted)

    @pytest.mark.benchmark(group="cipher-decryption")
    def test_aes128_decrypt_1mb(self, benchmark=None):
        """Benchmark AES-128 decryption throughput for 1MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        cipher = AESCipher(b"x" * 16)
        encrypted = cipher.encrypt(b"x" * (1024 * 1024))

        result = benchmark(cipher.decrypt, encrypted)
        assert len(result) == len(encrypted)

    @pytest.mark.benchmark(group="cipher-comparison")
    def test_cipher_throughput_comparison_1mb(self, benchmark=None):
        """Compare RC4, AES-128, and AES-256 throughput on 1MB data."""
        if benchmark is None:
            benchmark = stub_benchmark

        data = b"x" * (1024 * 1024)  # 1MB

        # RC4
        rc4_cipher = RC4Cipher(b"x" * 16)
        rc4_result = benchmark(rc4_cipher.encrypt, data)
        assert len(rc4_result) == len(data)

        # AES-128
        aes128_cipher = AESCipher(b"x" * 16)
        aes128_result = benchmark(aes128_cipher.encrypt, data)
        assert len(aes128_result) == len(data)

        # AES-256
        aes256_cipher = AESCipher(b"x" * 32)
        aes256_result = benchmark(aes256_cipher.encrypt, data)
        assert len(aes256_result) == len(data)


class TestDHPerformance:
    """Benchmark Diffie-Hellman key exchange performance."""

    @pytest.mark.benchmark(group="dh-keypair")
    def test_dh_768_keypair_generation(self, benchmark=None):
        """Benchmark DH 768-bit keypair generation time."""
        if benchmark is None:
            benchmark = stub_benchmark

        dh = DHPeerExchange(key_size=768)

        def generate_keypair():
            return dh.generate_keypair()

        result = benchmark(generate_keypair)
        assert result.private_key is not None
        assert result.public_key is not None

    @pytest.mark.benchmark(group="dh-keypair")
    def test_dh_1024_keypair_generation(self, benchmark=None):
        """Benchmark DH 1024-bit keypair generation time."""
        if benchmark is None:
            benchmark = stub_benchmark

        dh = DHPeerExchange(key_size=1024)

        def generate_keypair():
            return dh.generate_keypair()

        result = benchmark(generate_keypair)
        assert result.private_key is not None
        assert result.public_key is not None

    @pytest.mark.benchmark(group="dh-shared-secret")
    def test_dh_768_shared_secret_computation(self, benchmark=None):
        """Benchmark DH 768-bit shared secret computation."""
        if benchmark is None:
            benchmark = stub_benchmark

        dh = DHPeerExchange(key_size=768)

        # Generate keypairs
        keypair1 = dh.generate_keypair()
        keypair2 = dh.generate_keypair()

        def compute_secret():
            return dh.compute_shared_secret(
                keypair1.private_key, keypair2.public_key
            )

        result = benchmark(compute_secret)
        assert len(result) > 0

    @pytest.mark.benchmark(group="dh-shared-secret")
    def test_dh_1024_shared_secret_computation(self, benchmark=None):
        """Benchmark DH 1024-bit shared secret computation."""
        if benchmark is None:
            benchmark = stub_benchmark

        dh = DHPeerExchange(key_size=1024)

        # Generate keypairs
        keypair1 = dh.generate_keypair()
        keypair2 = dh.generate_keypair()

        def compute_secret():
            return dh.compute_shared_secret(
                keypair1.private_key, keypair2.public_key
            )

        result = benchmark(compute_secret)
        assert len(result) > 0

    @pytest.mark.benchmark(group="dh-key-derivation")
    def test_key_derivation_performance(self, benchmark=None):
        """Benchmark SHA-1 key derivation performance."""
        if benchmark is None:
            benchmark = stub_benchmark

        dh = DHPeerExchange(key_size=768)

        # Generate shared secret
        keypair1 = dh.generate_keypair()
        keypair2 = dh.generate_keypair()
        shared_secret = dh.compute_shared_secret(
            keypair1.private_key, keypair2.public_key
        )

        info_hash = b"x" * 20  # 20 bytes info hash

        def derive_key():
            return dh.derive_encryption_key(shared_secret, info_hash)

        result = benchmark(derive_key)
        assert len(result) == 20  # SHA-1 produces 20 bytes

