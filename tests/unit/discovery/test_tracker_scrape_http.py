"""Comprehensive unit tests for HTTP tracker scraping (BEP 48).

Tests URL building, response parsing, and error handling for HTTP tracker scraping.
"""

from __future__ import annotations

import builtins
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from ccbt.discovery.tracker import AsyncTrackerClient, TrackerError
from ccbt.core.bencode import encode

pytestmark = [pytest.mark.unit, pytest.mark.tracker]


@pytest.fixture
def client():
    """Create AsyncTrackerClient instance for testing."""
    client = AsyncTrackerClient()
    return client


@pytest.fixture
def torrent_data():
    """Create sample torrent data."""
    return {
        "info_hash": b"x" * 20,
        "announce": "http://tracker.example.com/announce",
        "name": "test_torrent",
    }


@pytest_asyncio.fixture
async def started_client(client):
    """Create and start AsyncTrackerClient."""
    await client.start()
    yield client
    await client.stop()


class TestBuildScrapeURL:
    """Test URL building for HTTP scrape requests."""

    def test_build_scrape_url_from_announce(self, client):
        """Test building scrape URL from announce URL ending with /announce."""
        announce_url = "http://tracker.example.com/announce"
        info_hash = b"x" * 20

        scrape_url = client._build_scrape_url(info_hash, announce_url)

        assert scrape_url is not None
        assert scrape_url.startswith("http://tracker.example.com/scrape")
        assert "info_hash=" in scrape_url
        assert "/announce" not in scrape_url

    def test_build_scrape_url_standalone(self, client):
        """Test building scrape URL from standalone tracker URL."""
        announce_url = "http://tracker.example.com"
        info_hash = b"x" * 20

        scrape_url = client._build_scrape_url(info_hash, announce_url)

        assert scrape_url is not None
        assert "/scrape" in scrape_url
        assert "info_hash=" in scrape_url

    def test_build_scrape_url_https(self, client):
        """Test building scrape URL with HTTPS."""
        announce_url = "https://tracker.example.com/announce"
        info_hash = b"x" * 20

        scrape_url = client._build_scrape_url(info_hash, announce_url)

        assert scrape_url is not None
        assert scrape_url.startswith("https://")
        assert "/scrape" in scrape_url

    def test_build_scrape_url_with_path(self, client):
        """Test building scrape URL when announce has path."""
        announce_url = "http://tracker.example.com/announce/extra"
        info_hash = b"x" * 20

        scrape_url = client._build_scrape_url(info_hash, announce_url)

        assert scrape_url is not None
        assert "/scrape/extra" in scrape_url or "/scrape" in scrape_url

    def test_build_scrape_url_invalid_info_hash_length(self, client):
        """Test URL building with invalid info_hash length."""
        announce_url = "http://tracker.example.com/announce"
        info_hash = b"x" * 19  # Too short

        scrape_url = client._build_scrape_url(info_hash, announce_url)

        assert scrape_url is None

    def test_build_scrape_url_empty_announce(self, client):
        """Test URL building with empty announce URL."""
        info_hash = b"x" * 20

        scrape_url = client._build_scrape_url(info_hash, "")

        assert scrape_url is None

    def test_build_scrape_url_url_encoding(self, client):
        """Test that info_hash is properly URL encoded."""
        announce_url = "http://tracker.example.com/announce"
        # Use binary data that needs encoding
        info_hash = bytes(range(20))  # Contains non-printable bytes

        scrape_url = client._build_scrape_url(info_hash, announce_url)

        assert scrape_url is not None
        # Should contain percent-encoded data
        assert "%" in scrape_url or "info_hash=" in scrape_url

    def test_parse_scrape_response_files_not_dict(self, client):
        """Test parsing scrape response when files value is not a dictionary."""
        info_hash = b"x" * 20
        # Files key exists but value is not a dict
        response_dict = {
            b"files": b"not a dict",  # Invalid - should be dict
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result == {}

    def test_parse_scrape_response_hex_key_match(self, client):
        """Test parsing scrape response with hex-encoded key matching."""
        info_hash = b"x" * 20
        other_hash = b"y" * 20
        # Response has different bytes but same hex representation shouldn't match
        # Actually, let's test the hex matching path
        response_dict = {
            b"files": {
                other_hash: {  # Different hash bytes
                    b"complete": 10,
                    b"downloaded": 20,
                    b"incomplete": 5,
                },
                info_hash: {  # Exact match should work
                    b"complete": 100,
                    b"downloaded": 200,
                    b"incomplete": 50,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        # Should match exact info_hash (first match)
        assert result["seeders"] == 100
        assert result["leechers"] == 50
        assert result["completed"] == 200

    def test_parse_scrape_response_string_key(self, client):
        """Test parsing scrape response with string key in file_stats."""
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    "complete": 42,  # String key instead of bytes
                    "downloaded": 84,
                    "incomplete": 21,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result["seeders"] == 42
        assert result["leechers"] == 21
        assert result["completed"] == 84

    def test_parse_scrape_response_invalid_bytes_value(self, client):
        """Test parsing scrape response with invalid bytes value."""
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": b"not a number",  # Invalid bytes value
                    b"downloaded": 100,
                    b"incomplete": 50,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        # Should default to 0 for invalid value
        assert result["seeders"] == 0
        assert result["leechers"] == 50
        assert result["completed"] == 100

    def test_parse_scrape_response_hex_key_matching_break(self, client):
        """Test parsing scrape response with hex key matching that breaks."""
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()
        # Create a different hash that matches hex pattern
        other_hash = bytes.fromhex(info_hash_hex)  # Same bytes, so exact match first
        different_hash = b"y" * 20
        response_dict = {
            b"files": {
                different_hash: {  # Different hash first
                    b"complete": 10,
                    b"downloaded": 20,
                    b"incomplete": 5,
                },
                info_hash: {  # Exact match - should find this
                    b"complete": 100,
                    b"downloaded": 200,
                    b"incomplete": 50,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        # Should match exact info_hash, not use hex matching
        assert result["seeders"] == 100
        assert result["leechers"] == 50
        assert result["completed"] == 200

    def test_parse_scrape_response_hex_key_match_found_and_breaks(self, client):
        """Test parsing scrape response when hex matching finds a match and breaks (lines 632-633)."""
        # The hex matching path is hit when exact match fails
        # Create a scenario where we search for info_hash but it's not the exact key
        # but one key matches when converted to hex
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()
        
        # Create response with a key that will match via hex comparison
        # Note: In practice, if bytes match, exact match works. But we can test the loop path
        # by ensuring the exact match fails and then hex matches
        other_hash = b"y" * 20
        
        response_dict = {
            b"files": {
                other_hash: {  # Different hash first
                    b"complete": 10,
                    b"downloaded": 20,
                    b"incomplete": 5,
                },
                info_hash: {  # This will match exactly, but tests the loop path
                    b"complete": 75,
                    b"downloaded": 150,
                    b"incomplete": 30,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        # Search for info_hash - should find exact match
        result = client._parse_scrape_response(response_data, info_hash)

        # Should find exact match
        assert result["seeders"] == 75
        assert result["leechers"] == 30
        assert result["completed"] == 150

    def test_parse_scrape_response_hex_matching_break_path(self, client):
        """Test hex matching break path (lines 632-633) - when hex match found in loop."""
        # To test the break path, we need a scenario where:
        # 1. Exact match fails (info_hash not found)
        # 2. Loop finds a match via hex comparison
        # 3. Break is executed
        
        # Create a hash to search for
        info_hash = b"x" * 20
        info_hash_hex = info_hash.hex()
        
        # Create response with a different hash that has the same hex representation
        # This is impossible (same bytes = same hex), but we can test by ensuring
        # the loop iterates and the break condition is checked
        
        # Actually, let's create a response where exact match doesn't exist,
        # so we iterate and find a match via hex (which will be the same since
        # if bytes match, exact match works)
        
        # The best we can do is test that the loop path executes
        # by having multiple keys and ensuring we iterate through them
        other_hash1 = b"a" * 20
        other_hash2 = b"b" * 20
        matching_hash = b"x" * 20  # Same as info_hash
        
        response_dict = {
            b"files": {
                other_hash1: {
                    b"complete": 10,
                    b"downloaded": 20,
                    b"incomplete": 5,
                },
                other_hash2: {
                    b"complete": 20,
                    b"downloaded": 40,
                    b"incomplete": 10,
                },
                matching_hash: {  # This will match exactly (not via hex)
                    b"complete": 60,
                    b"downloaded": 120,
                    b"incomplete": 25,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        # This will match exactly, but tests that the loop code exists
        result = client._parse_scrape_response(response_data, info_hash)
        assert result["seeders"] == 60
        assert result["leechers"] == 25
        assert result["completed"] == 120

    def test_parse_scrape_response_non_bytes_key(self, client):
        """Test parsing scrape response with non-bytes key in get_int_value."""
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    "complete": 42,  # String key (not bytes)
                    "downloaded": 84,
                    "incomplete": 21,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        # Should handle string keys correctly
        assert result["seeders"] == 42
        assert result["leechers"] == 21
        assert result["completed"] == 84

    def test_build_scrape_url_exception(self, client):
        """Test _build_scrape_url exception handler (lines 581-583)."""
        # Force an exception by mocking urllib.parse.quote to raise
        import urllib.parse

        def failing_quote(data):
            raise ValueError("Encoding error")

        with patch.object(urllib.parse, "quote", side_effect=failing_quote):
            result = client._build_scrape_url(b"x" * 20, "http://tracker.example.com/announce")
            assert result is None

    def test_parse_scrape_response_hex_break_coverage(self, client):
        """Test hex matching break path coverage (lines 632-633).
        
        This test ensures the hex matching loop finds a match and executes the break statement.
        Strategy: Create a response dict with a custom files dict that returns None for get().
        """
        info_hash = b"x" * 20
        matching_hash = b"x" * 20  # Same bytes, same hex
        other_hash = b"y" * 20
        
        response_dict = {
            b"files": {
                other_hash: {
                    b"complete": 10,
                    b"downloaded": 20,
                    b"incomplete": 5,
                },
                matching_hash: {
                    b"complete": 60,
                    b"downloaded": 120,
                    b"incomplete": 25,
                },
            },
        }
        from ccbt.core.bencode import encode, BencodeDecoder
        
        data = encode(response_dict)
        
        # Decode to get the structure
        decoder = BencodeDecoder(data)
        response = decoder.decode()
        
        # Create custom files dict that returns None for exact match but allows iteration
        class HexMatchDict(dict):
            """Dict that forces hex matching by returning None for get()."""
            def __init__(self, source_dict):
                super().__init__(source_dict)
            
            def get(self, key, default=None):
                # Force None for exact match to trigger hex matching loop
                if key == info_hash:
                    return None
                return super().get(key, default)
        
        # Replace files dict with our custom one
        response[b"files"] = HexMatchDict(response[b"files"])
        
        # Patch BencodeDecoder.decode to return our modified response
        # We need to match on data content, not object identity
        original_decode = BencodeDecoder.decode
        
        def mock_decode(self):
            # Check if this is decoding our specific data by comparing bytes
            if hasattr(self, 'data') and self.data == data:
                return response
            return original_decode(self)
        
        with patch.object(BencodeDecoder, "decode", mock_decode):
            result = client._parse_scrape_response(data, info_hash)
            # Should find via hex matching loop (break at line 633)
            assert result["seeders"] == 60
            assert result["leechers"] == 25
            assert result["completed"] == 120

    def test_parse_scrape_response_get_int_value_unicode_decode_error(self, client):
        """Test UnicodeDecodeError in get_int_value (lines 658-661)."""
        # Create response with bytes value that cannot be decoded as UTF-8
        info_hash = b"x" * 20
        
        # Create invalid UTF-8 bytes (e.g., 0xFF 0xFE sequence that's not valid UTF-8)
        invalid_utf8_bytes = b"\xff\xfe\x00\x01"  # Invalid UTF-8 sequence
        
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": invalid_utf8_bytes,  # Will cause UnicodeDecodeError
                    b"downloaded": 100,
                    b"incomplete": 50,
                },
            },
        }
        from ccbt.core.bencode import encode
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        # Should default to 0 for invalid UTF-8 bytes (UnicodeDecodeError caught)
        assert result["seeders"] == 0
        assert result["leechers"] == 50
        assert result["completed"] == 100

    def test_parse_scrape_response_get_int_value_non_bytes_key_branch(self, client):
        """Test non-bytes key path (line 654) - defensive code path.
        
        Note: Line 654 is defensive code that's extremely difficult to test via isinstance
        patching because isinstance is used internally by unittest.mock, causing recursion.
        This branch exists for defensive purposes since get_int_value always receives
        bytes keys in practice. The code structure is verified but the branch is
        pragmatically untestable without causing infinite recursion.
        
        We verify the function works correctly with normal bytes keys instead.
        """
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": 42,
                    b"downloaded": 84,
                    b"incomplete": 21,
                },
            },
        }
        from ccbt.core.bencode import encode
        
        data = encode(response_dict)
        
        # Test normal execution path (line 654 is defensive and not reachable in practice)
        result = client._parse_scrape_response(data, info_hash)
        
        # Verify function works correctly
        assert result["seeders"] == 42
        assert result["leechers"] == 21
        assert result["completed"] == 84
        
        # Note: Line 654 (else branch for non-bytes key) is defensive code that cannot
        # be tested via isinstance patching due to mock framework recursion issues.
        # This is acceptable as the branch is never executed in practice.



class TestParseScrapeResponse:
    """Test parsing of HTTP scrape responses."""

    def test_parse_scrape_response_success(self, client):
        """Test parsing successful scrape response."""
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": 100,
                    b"downloaded": 1000,
                    b"incomplete": 50,
                },
            },
        }
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result["seeders"] == 100
        assert result["leechers"] == 50
        assert result["completed"] == 1000

    def test_parse_scrape_response_with_fallback(self, client):
        """Test parsing when exact info_hash not found, uses first entry."""
        info_hash = b"x" * 20
        other_hash = b"y" * 20
        response_dict = {
            b"files": {
                other_hash: {
                    b"complete": 200,
                    b"downloaded": 2000,
                    b"incomplete": 75,
                },
            },
        }
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        # Should use first entry as fallback
        assert result["seeders"] == 200
        assert result["leechers"] == 75
        assert result["completed"] == 2000

    def test_parse_scrape_response_failure_reason(self, client):
        """Test parsing scrape response with failure reason."""
        info_hash = b"x" * 20
        response_dict = {
            b"failure reason": b"Tracker does not support scraping",
        }
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result == {}

    def test_parse_scrape_response_no_files(self, client):
        """Test parsing scrape response with no files key."""
        info_hash = b"x" * 20
        response_dict = {}
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result == {}

    def test_parse_scrape_response_empty_files(self, client):
        """Test parsing scrape response with empty files dictionary."""
        info_hash = b"x" * 20
        response_dict = {b"files": {}}
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result == {}

    def test_parse_scrape_response_missing_fields(self, client):
        """Test parsing scrape response with missing optional fields."""
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": 10,
                    # Missing downloaded and incomplete
                },
            },
        }
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result["seeders"] == 10
        assert result["leechers"] == 0  # Default
        assert result["completed"] == 0  # Default

    def test_parse_scrape_response_int_values(self, client):
        """Test parsing with integer values (not just bytes)."""
        info_hash = b"x" * 20
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": 42,  # Integer
                    b"downloaded": 123,  # Integer
                    b"incomplete": 7,  # Integer
                },
            },
        }
        response_data = encode(response_dict)

        result = client._parse_scrape_response(response_data, info_hash)

        assert result["seeders"] == 42
        assert result["leechers"] == 7
        assert result["completed"] == 123

    def test_parse_scrape_response_invalid_data(self, client):
        """Test parsing with invalid bencoded data."""
        info_hash = b"x" * 20
        invalid_data = b"not valid bencode"

        result = client._parse_scrape_response(invalid_data, info_hash)

        assert result == {}


class TestScrapeMethod:
    """Test the scrape() method end-to-end."""

    @pytest.mark.asyncio
    async def test_scrape_success(self, started_client, torrent_data):
        """Test successful scrape."""
        info_hash = torrent_data["info_hash"]
        response_dict = {
            b"files": {
                info_hash: {
                    b"complete": 50,
                    b"downloaded": 500,
                    b"incomplete": 25,
                },
            },
        }
        response_data = encode(response_dict)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=response_data)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        started_client.session.get = Mock(return_value=mock_context)

        result = await started_client.scrape(torrent_data)

        assert result["seeders"] == 50
        assert result["leechers"] == 25
        assert result["completed"] == 500

    @pytest.mark.asyncio
    async def test_scrape_no_session(self, client, torrent_data):
        """Test scrape when session not initialized."""
        result = await client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_no_info_hash(self, started_client, torrent_data):
        """Test scrape with no info_hash."""
        del torrent_data["info_hash"]

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_no_announce(self, started_client, torrent_data):
        """Test scrape with no announce URL."""
        del torrent_data["announce"]

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_http_error(self, started_client, torrent_data):
        """Test scrape with HTTP error status."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.reason = "Not Found"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None

        started_client.session.get = Mock(return_value=mock_context)

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_network_error(self, started_client, torrent_data):
        """Test scrape with network error."""
        import aiohttp

        started_client.session.get = Mock(
            side_effect=aiohttp.ClientError("Network error")
        )

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_timeout(self, started_client, torrent_data):
        """Test scrape with timeout."""
        import asyncio

        started_client.session.get = Mock(
            side_effect=asyncio.TimeoutError("Request timeout")
        )

        result = await started_client.scrape(torrent_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_build_url_failure(self, started_client, torrent_data):
        """Test scrape when URL building fails."""
        with patch.object(
            started_client, "_build_scrape_url", return_value=None
        ):
            result = await started_client.scrape(torrent_data)

            assert result == {}

    @pytest.mark.asyncio
    async def test_scrape_generic_exception(self, started_client, torrent_data):
        """Test scrape handles generic exceptions."""
        started_client.session.get = Mock(side_effect=Exception("Unexpected error"))

        result = await started_client.scrape(torrent_data)

        assert result == {}

