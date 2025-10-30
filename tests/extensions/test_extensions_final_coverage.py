"""Final coverage tests for extensions modules to reach 90%+ coverage."""

import asyncio
import json
import socket
import struct
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.extensions]

from ccbt.extensions.manager import ExtensionManager, ExtensionStatus, ExtensionState
from ccbt.extensions.pex import PEXMessageType, PEXPeer, PeerExchange
from ccbt.extensions.protocol import ExtensionProtocol, ExtensionMessageType, ExtensionInfo
from ccbt.extensions.webseed import WebSeedExtension, WebSeedInfo
from ccbt.models import PeerInfo, PieceInfo
from ccbt.utils.events import Event, EventType


class TestPEXFinalCoverage:
    """Final PEX tests for remaining coverage."""

    def test_merge_peer_lists(self):
        """Test merging peer lists with duplicates."""
        pex = PeerExchange()
        peers1 = [
            PEXPeer(ip="127.0.0.1", port=6881),
            PEXPeer(ip="192.168.1.1", port=6882),
        ]
        peers2 = [
            PEXPeer(ip="192.168.1.1", port=6882),  # Duplicate
            PEXPeer(ip="10.0.0.1", port=6883),
        ]

        merged = pex.merge_peer_lists(peers1, peers2)

        assert len(merged) == 3  # No duplicates
        assert PEXPeer(ip="127.0.0.1", port=6881) in merged
        assert PEXPeer(ip="192.168.1.1", port=6882) in merged
        assert PEXPeer(ip="10.0.0.1", port=6883) in merged

    def test_merge_peer_lists_empty(self):
        """Test merging empty peer lists."""
        pex = PeerExchange()

        merged = pex.merge_peer_lists([], [])

        assert len(merged) == 0

    def test_merge_peer_lists_one_empty(self):
        """Test merging with one empty list."""
        pex = PeerExchange()
        peers = [PEXPeer(ip="127.0.0.1", port=6881)]

        merged = pex.merge_peer_lists(peers, [])

        assert len(merged) == 1
        assert PEXPeer(ip="127.0.0.1", port=6881) in merged

    def test_create_peer_from_info_with_flags(self):
        """Test creating peer from info with specific flags."""
        pex = PeerExchange()
        peer_info = PeerInfo(ip="127.0.0.1", port=6881)

        # Test with only seed flag
        peer = pex.create_peer_from_info(peer_info, is_seed=True, is_connectable=False)
        assert peer.flags == 1  # Only seed flag

        # Test with only connectable flag
        peer = pex.create_peer_from_info(peer_info, is_seed=False, is_connectable=True)
        assert peer.flags == 2  # Only connectable flag

        # Test with no flags
        peer = pex.create_peer_from_info(peer_info, is_seed=False, is_connectable=False)
        assert peer.flags == 0  # No flags

    def test_get_peer_statistics_comprehensive(self):
        """Test comprehensive peer statistics."""
        pex = PeerExchange()

        # Add peers with different flags
        pex.add_peer(PEXPeer(ip="127.0.0.1", port=6881, flags=1))  # Seed
        pex.add_peer(PEXPeer(ip="192.168.1.1", port=6882, flags=2))  # Connectable
        pex.drop_peer(PEXPeer(ip="10.0.0.1", port=6883, flags=3))  # Both

        # Set flags for statistics
        pex.set_peer_flags("127.0.0.1", 6881, 1)
        pex.set_peer_flags("192.168.1.1", 6882, 2)
        pex.set_peer_flags("10.0.0.1", 6883, 3)

        stats = pex.get_peer_statistics()

        assert stats["added_peers_count"] == 2
        assert stats["dropped_peers_count"] == 1
        assert stats["total_peers_with_flags"] == 3
        assert stats["seeds_count"] == 2  # First and third
        assert stats["connectable_peers_count"] == 2  # Second and third


class TestProtocolFinalCoverage:
    """Final Protocol tests for remaining coverage."""

    def test_get_peer_extensions(self):
        """Test getting peer extensions."""
        protocol = ExtensionProtocol()

        # Set peer extensions
        protocol.peer_extensions["peer123"] = {"ext1": {"version": "1.0"}}

        extensions = protocol.get_peer_extensions("peer123")

        assert "ext1" in extensions
        assert extensions["ext1"]["version"] == "1.0"

    def test_get_peer_extensions_not_found(self):
        """Test getting extensions for unknown peer."""
        protocol = ExtensionProtocol()

        extensions = protocol.get_peer_extensions("unknown")

        assert extensions == {}

    def test_peer_supports_extension(self):
        """Test checking if peer supports extension."""
        protocol = ExtensionProtocol()

        # Set peer extensions
        protocol.peer_extensions["peer123"] = {"ext1": {"version": "1.0"}}

        assert protocol.peer_supports_extension("peer123", "ext1")
        assert not protocol.peer_supports_extension("peer123", "ext2")
        assert not protocol.peer_supports_extension("unknown", "ext1")

    def test_get_peer_extension_info(self):
        """Test getting peer extension info."""
        protocol = ExtensionProtocol()

        # Set peer extensions
        protocol.peer_extensions["peer123"] = {"ext1": {"version": "1.0", "message_id": 5}}

        info = protocol.get_peer_extension_info("peer123", "ext1")

        assert info is not None
        assert info["version"] == "1.0"
        assert info["message_id"] == 5

    def test_get_peer_extension_info_not_found(self):
        """Test getting extension info for unknown peer/extension."""
        protocol = ExtensionProtocol()

        info = protocol.get_peer_extension_info("unknown", "ext1")
        assert info is None

        protocol.peer_extensions["peer123"] = {"ext1": {"version": "1.0"}}
        info = protocol.get_peer_extension_info("peer123", "ext2")
        assert info is None

    @pytest.mark.asyncio
    async def test_handle_extension_message_no_handler(self):
        """Test handling extension message with no handler."""
        protocol = ExtensionProtocol()

        # Register extension without handler
        msg_id = protocol.register_extension("test_ext", "1.0", None)

        # Should not raise
        await protocol.handle_extension_message("peer123", msg_id, b"data")

    @pytest.mark.asyncio
    async def test_handle_extension_message_unknown_extension(self):
        """Test handling message for unknown extension."""
        protocol = ExtensionProtocol()

        # Should not raise
        await protocol.handle_extension_message("peer123", 999, b"data")


class TestManagerFinalCoverage:
    """Final Manager tests for remaining coverage."""

    def test_get_extension_statistics(self):
        """Test getting extension statistics."""
        manager = ExtensionManager()

        stats = manager.get_extension_statistics()

        assert "protocol" in stats
        assert "fast" in stats
        assert "pex" in stats
        assert "dht" in stats
        assert "webseed" in stats
        assert "compact" in stats

        # Check structure
        for name, stat in stats.items():
            assert "status" in stat
            assert "last_activity" in stat
            assert "error_count" in stat
            assert "last_error" in stat
            assert "capabilities" in stat

    def test_get_peer_extensions(self):
        """Test getting peer extensions."""
        manager = ExtensionManager()

        # Set peer extensions
        manager.peer_extensions["peer123"] = {"ext1": {"version": "1.0"}}

        extensions = manager.get_peer_extensions("peer123")

        assert "ext1" in extensions
        assert extensions["ext1"]["version"] == "1.0"

    def test_get_peer_extensions_not_found(self):
        """Test getting extensions for unknown peer."""
        manager = ExtensionManager()

        extensions = manager.get_peer_extensions("unknown")

        assert extensions == {}

    def test_set_peer_extensions(self):
        """Test setting peer extensions."""
        manager = ExtensionManager()

        extensions = {"ext1": {"version": "1.0"}}
        manager.set_peer_extensions("peer123", extensions)

        assert manager.peer_extensions["peer123"] == extensions

    def test_peer_supports_extension(self):
        """Test checking if peer supports extension."""
        manager = ExtensionManager()

        # Set peer extensions
        manager.peer_extensions["peer123"] = {"ext1": {"version": "1.0"}}

        assert manager.peer_supports_extension("peer123", "ext1")
        assert not manager.peer_supports_extension("peer123", "ext2")
        assert not manager.peer_supports_extension("unknown", "ext1")

    def test_get_extension_capabilities(self):
        """Test getting extension capabilities."""
        manager = ExtensionManager()

        # Test with extension that has get_capabilities method
        mock_ext = Mock()
        mock_ext.get_capabilities = Mock(return_value={"test": True})
        manager.extensions["test_ext"] = mock_ext

        capabilities = manager.get_extension_capabilities("test_ext")

        assert capabilities == {"test": True}
        mock_ext.get_capabilities.assert_called_once()

    def test_get_extension_capabilities_not_found(self):
        """Test getting capabilities for unknown extension."""
        manager = ExtensionManager()

        capabilities = manager.get_extension_capabilities("unknown")

        assert capabilities == {}


class TestWebSeedFinalCoverage:
    """Final WebSeed tests for remaining coverage."""

    def test_get_webseed_statistics(self):
        """Test getting WebSeed statistics."""
        webseed = WebSeedExtension()

        webseed_id = webseed.add_webseed("http://example.com/file.torrent")
        webseed.webseeds[webseed_id].bytes_downloaded = 1000
        webseed.webseeds[webseed_id].bytes_failed = 100
        webseed.webseeds[webseed_id].success_rate = 0.9

        stats = webseed.get_webseed_statistics(webseed_id)

        assert stats is not None
        assert stats["url"] == "http://example.com/file.torrent"
        assert stats["bytes_downloaded"] == 1000
        assert stats["bytes_failed"] == 100
        assert stats["success_rate"] == 0.9

    def test_get_webseed_statistics_not_found(self):
        """Test getting statistics for unknown WebSeed."""
        webseed = WebSeedExtension()

        stats = webseed.get_webseed_statistics("unknown")

        assert stats is None

    def test_get_all_statistics(self):
        """Test getting all WebSeed statistics."""
        webseed = WebSeedExtension()

        # Add multiple WebSeeds
        webseed_id1 = webseed.add_webseed("http://example1.com/file.torrent")
        webseed_id2 = webseed.add_webseed("http://example2.com/file.torrent")

        # Set statistics
        webseed.webseeds[webseed_id1].bytes_downloaded = 1000
        webseed.webseeds[webseed_id1].bytes_failed = 100
        webseed.webseeds[webseed_id1].is_active = True

        webseed.webseeds[webseed_id2].bytes_downloaded = 500
        webseed.webseeds[webseed_id2].bytes_failed = 50
        webseed.webseeds[webseed_id2].is_active = False

        stats = webseed.get_all_statistics()

        assert stats["total_webseeds"] == 2
        assert stats["active_webseeds"] == 1
        assert stats["total_bytes_downloaded"] == 1500
        assert stats["total_bytes_failed"] == 150
        assert stats["overall_success_rate"] == 1500 / 1650

    def test_get_all_statistics_empty(self):
        """Test getting statistics with no WebSeeds."""
        webseed = WebSeedExtension()

        stats = webseed.get_all_statistics()

        assert stats["total_webseeds"] == 0
        assert stats["active_webseeds"] == 0
        assert stats["total_bytes_downloaded"] == 0
        assert stats["total_bytes_failed"] == 0
        assert stats["overall_success_rate"] == 0.0

    def test_set_webseed_active(self):
        """Test setting WebSeed active status."""
        webseed = WebSeedExtension()

        webseed_id = webseed.add_webseed("http://example.com/file.torrent")

        # Set inactive
        webseed.set_webseed_active(webseed_id, False)
        assert not webseed.webseeds[webseed_id].is_active

        # Set active
        webseed.set_webseed_active(webseed_id, True)
        assert webseed.webseeds[webseed_id].is_active

    def test_set_webseed_active_not_found(self):
        """Test setting active status for unknown WebSeed."""
        webseed = WebSeedExtension()

        # Should not raise
        webseed.set_webseed_active("unknown", True)

    def test_get_best_webseed(self):
        """Test getting best WebSeed based on score."""
        webseed = WebSeedExtension()

        # Add WebSeeds with different success rates
        webseed_id1 = webseed.add_webseed("http://example1.com/file.torrent")
        webseed_id2 = webseed.add_webseed("http://example2.com/file.torrent")

        webseed.webseeds[webseed_id1].success_rate = 0.8
        webseed.webseeds[webseed_id1].is_active = True

        webseed.webseeds[webseed_id2].success_rate = 0.9
        webseed.webseeds[webseed_id2].is_active = True

        best_id = webseed.get_best_webseed()

        # Should return the one with higher success rate
        assert best_id == webseed_id2

    def test_get_best_webseed_no_active(self):
        """Test getting best WebSeed when none are active."""
        webseed = WebSeedExtension()

        webseed_id = webseed.add_webseed("http://example.com/file.torrent")
        webseed.webseeds[webseed_id].is_active = False

        best_id = webseed.get_best_webseed()

        assert best_id is None

    def test_get_best_webseed_empty(self):
        """Test getting best WebSeed when none exist."""
        webseed = WebSeedExtension()

        best_id = webseed.get_best_webseed()

        assert best_id is None

    def test_webseed_info_custom(self):
        """Test WebSeedInfo with custom values."""
        webseed_info = WebSeedInfo(
            url="http://example.com/file.torrent",
            name="custom_name",
            is_active=False,
            last_accessed=1234567890.0,
            bytes_downloaded=1000,
            bytes_failed=100,
            success_rate=0.9
        )

        assert webseed_info.url == "http://example.com/file.torrent"
        assert webseed_info.name == "custom_name"
        assert webseed_info.is_active is False
        assert webseed_info.last_accessed == 1234567890.0
        assert webseed_info.bytes_downloaded == 1000
        assert webseed_info.bytes_failed == 100
        assert webseed_info.success_rate == 0.9


class TestProtocolMoreCoverage:
    """Extra protocol tests for unknown extension events."""

    @pytest.mark.asyncio
    async def test_unknown_extension_message_emits_event(self):
        protocol = ExtensionProtocol()
        with patch("ccbt.extensions.protocol.emit_event") as mock_emit:
            await protocol.handle_extension_message("peerX", 9999, b"payload")
            assert mock_emit.called


class TestManagerMoreCoverage:
    """Extra manager tests for peer extensions and capabilities fallback."""

    def test_set_get_peer_extensions_and_supports(self):
        manager = ExtensionManager()
        manager.set_peer_extensions("peerA", {"extA": {"v": "1"}})
        assert manager.get_peer_extensions("peerA") == {"extA": {"v": "1"}}
        assert manager.peer_supports_extension("peerA", "extA") is True
        assert manager.peer_supports_extension("peerA", "missing") is False
        assert manager.get_peer_extensions("unknown") == {}

    def test_get_extension_capabilities_prefers_get_capabilities(self):
        manager = ExtensionManager()
        mock_ext = Mock()
        mock_ext.get_capabilities = Mock(return_value={"caps": True})
        mock_ext.get_extension_statistics = Mock(return_value={"stats": True})
        manager.extensions["caps_ext"] = mock_ext
        caps = manager.get_extension_capabilities("caps_ext")
        assert caps == {"caps": True}
        mock_ext.get_capabilities.assert_called_once()
        # Fallback not called when capabilities present
        mock_ext.get_extension_statistics.assert_not_called()

    def test_get_extension_capabilities_fallback_to_stats(self):
        manager = ExtensionManager()
        class StatsOnly:
            def get_extension_statistics(self):
                return {"stats": True}
        stats_only = StatsOnly()
        manager.extensions["stats_ext"] = stats_only
        caps = manager.get_extension_capabilities("stats_ext")
        assert caps == {"stats": True}


class TestWebSeedMoreCoverage:
    """Extra WebSeed tests to cover failure event and lifecycle branches."""

    @pytest.mark.asyncio
    async def test_download_piece_http_failure_emits_event_and_updates_stats(self):
        webseed = WebSeedExtension()
        ws_id = webseed.add_webseed("http://example.com/file")
        piece = PieceInfo(index=1, length=1024, hash=b"h" * 20)
        mock_resp = AsyncMock()
        mock_resp.status = 500
        with patch("aiohttp.ClientSession.get") as mock_get, \
             patch("ccbt.extensions.webseed.emit_event") as mock_emit:
            mock_get.return_value.__aenter__.return_value = mock_resp
            await webseed.start()
            try:
                result = await webseed.download_piece(ws_id, piece, b"x")
                assert result is None
                # failure accounted
                stats = webseed.get_webseed_statistics(ws_id)
                assert stats is not None and stats["bytes_failed"] >= 1024
                assert mock_emit.called
            finally:
                await webseed.stop()

    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self):
        webseed = WebSeedExtension()
        await webseed.start()
        # Call start again (no-op expected)
        await webseed.start()
        await webseed.stop()
        # Call stop again (no-op expected)
        await webseed.stop()


class TestManagerDeepCoverage:
    """Cover manager start/stop, errors, compact, and add/remove webseed guards."""

    @pytest.mark.asyncio
    async def test_start_stop_emits_events_and_updates_state(self):
        manager = ExtensionManager()
        # Inject a minimal extension with start/stop
        class Ext:
            async def start(self):
                return None
            async def stop(self):
                return None
        manager.extensions["custom"] = Ext()
        manager.extension_states["custom"] = ExtensionState(
            name="custom", status=ExtensionStatus.ENABLED, capabilities={}, last_activity=0.0
        )
        with patch("ccbt.extensions.manager.emit_event") as mock_emit:
            await manager.start()
            await manager.stop()
            assert mock_emit.called
            # custom should be disabled after stop
            assert manager.extension_states["custom"].status == ExtensionStatus.DISABLED

    @pytest.mark.asyncio
    async def test_start_handles_extension_error(self):
        manager = ExtensionManager()
        class BadExt:
            async def start(self):
                raise RuntimeError("boom")
        manager.extensions["bad"] = BadExt()
        manager.extension_states["bad"] = ExtensionState(
            name="bad", status=ExtensionStatus.ENABLED, capabilities={}, last_activity=0.0
        )
        with patch("ccbt.extensions.manager.emit_event") as mock_emit:
            await manager.start()
            state = manager.extension_states["bad"]
            assert state.status == ExtensionStatus.ERROR
            assert state.error_count >= 1
            assert state.last_error is not None
            assert mock_emit.called

    def test_add_webseed_inactive_raises(self):
        manager = ExtensionManager()
        manager.disable_extension("webseed")
        with pytest.raises(RuntimeError):
            manager.add_webseed("http://example.com")

    def test_compact_inactive_raises(self):
        manager = ExtensionManager()
        manager.disable_extension("compact")
        with pytest.raises(RuntimeError):
            manager.encode_peers_compact([])  # any list
        with pytest.raises(RuntimeError):
            manager.decode_peers_compact(b"")

    def test_get_all_statistics_includes_specific_extension_stats(self):
        manager = ExtensionManager()
        # Extension with get_extension_statistics
        class ExtStats:
            def get_extension_statistics(self):
                return {"ok": True}
        # Extension with get_all_statistics
        class ExtAll:
            def get_all_statistics(self):
                return {"all": True}
        manager.extensions["stats_only"] = ExtStats()
        manager.extension_states["stats_only"] = ExtensionState(
            name="stats_only", status=ExtensionStatus.ENABLED, capabilities={}, last_activity=0.0
        )
        manager.extensions["all_only"] = ExtAll()
        manager.extension_states["all_only"] = ExtensionState(
            name="all_only", status=ExtensionStatus.ENABLED, capabilities={}, last_activity=0.0
        )
        full = manager.get_all_statistics()
        assert full["total_extensions"] >= 2
        assert "stats_only_stats" in full and full["stats_only_stats"]["ok"] is True
        assert "all_only_stats" in full and full["all_only_stats"]["all"] is True

    @pytest.mark.asyncio
    async def test_early_returns_when_inactive(self):
        manager = ExtensionManager()
        # Fast inactive
        manager.disable_extension("fast")
        # no exception expected
        await manager.handle_fast_extension("peer", 0x0D, b"")
        # Protocol inactive
        manager.disable_extension("protocol")
        await manager.handle_extension_protocol("peer", 1, b"")
        # PEX inactive
        manager.disable_extension("pex")
        await manager.handle_pex_message("peer", 0, b"")
        # DHT inactive
        manager.disable_extension("dht")
        out = await manager.handle_dht_message("127.0.0.1", 6881, b"")
        assert out is None
        # Webseed inactive
        manager.disable_extension("webseed")
        out2 = await manager.download_piece_from_webseed("id", Mock())
        assert out2 is None


class TestProtocolDeepCoverage:
    """Cover protocol utilities and guards."""

    def test_send_extension_message_raises_for_unknown(self):
        proto = ExtensionProtocol()
        with pytest.raises(ValueError):
            proto.send_extension_message("peer", "nope", b"p")

    def test_create_register_unregister_handlers_and_clear(self):
        proto = ExtensionProtocol()
        # create handler and register
        handler = proto.create_extension_handler("x")
        assert callable(handler)
        mid = proto.register_extension("x", "1.0", handler)
        assert mid in proto.get_message_handlers()
        # unregister by name
        proto.unregister_extension("x")
        assert proto.get_extension_info("x") is None
        # register message handler directly
        proto.register_message_handler(99, lambda p, b: None)
        assert 99 in proto.get_message_handlers()
        proto.unregister_message_handler(99)
        assert 99 not in proto.get_message_handlers()
        # peer extensions utilities
        proto.peer_extensions["p1"] = {"e": {}}
        assert proto.peer_supports_extension("p1", "e")
        assert proto.get_peer_extension_info("p1", "e") == {}
        proto.clear_peer_extensions("p1")
        assert proto.get_peer_extensions("p1") == {}
        proto.clear_all_peer_extensions()
        assert proto.get_extension_statistics()["total_extensions"] >= 0


class TestWebSeedDeepCoverage:
    """Cover resets, remove events, and health checks."""

    @pytest.mark.asyncio
    async def test_remove_webseed_emits_event(self):
        ws = WebSeedExtension()
        ws_id = ws.add_webseed("http://example.com/f")
        with patch("ccbt.extensions.webseed.emit_event") as mock_emit:
            await ws.start()
            ws.remove_webseed(ws_id)
            assert mock_emit.called
            await ws.stop()

    def test_reset_statistics(self):
        ws = WebSeedExtension()
        ws_id = ws.add_webseed("http://example.com/f")
        info = ws.get_webseed(ws_id)
        assert info is not None
        info.bytes_downloaded = 10
        info.bytes_failed = 5
        info.last_accessed = time.time()
        info.success_rate = 0.5
        ws.reset_webseed_statistics(ws_id)
        s = ws.get_webseed_statistics(ws_id)
        assert s is not None and s["bytes_downloaded"] == 0 and s["bytes_failed"] == 0 and s["success_rate"] == 1.0
        # all reset
        ws.reset_all_statistics()
        s2 = ws.get_webseed_statistics(ws_id)
        assert s2 is not None and s2["bytes_downloaded"] == 0 and s2["bytes_failed"] == 0

    @pytest.mark.asyncio
    async def test_health_check_and_health_check_all(self):
        ws = WebSeedExtension()
        ws_id = ws.add_webseed("http://example.com/f")
        with patch("aiohttp.ClientSession.head") as mock_head:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_head.return_value.__aenter__.return_value = mock_resp
            await ws.start()
            try:
                ok = await ws.health_check(ws_id)
                assert ok is True
                results = await ws.health_check_all()
                assert ws_id in results and results[ws_id] in {True, False}
            finally:
                await ws.stop()


class TestManagerBranchCoverage:
    """Push manager branch coverage for fast/pex/dht/webseed paths."""

    @pytest.mark.asyncio
    async def test_handle_fast_extension_all_message_types(self):
        manager = ExtensionManager()
        # Force ACTIVE state
        manager.extension_states["fast"].status = ExtensionStatus.ACTIVE
        fast = Mock()
        fast.decode_suggest = Mock(return_value=7)
        fast.handle_suggest = AsyncMock()
        fast.handle_have_all = AsyncMock()
        fast.handle_have_none = AsyncMock()
        fast.decode_reject = Mock(return_value=(1, 2, 3))
        fast.handle_reject = AsyncMock()
        fast.decode_allow_fast = Mock(return_value=9)
        fast.handle_allow_fast = AsyncMock()
        manager.extensions["fast"] = fast
        await manager.handle_fast_extension("p", 0x0D, b"a")
        await manager.handle_fast_extension("p", 0x0E, b"a")
        await manager.handle_fast_extension("p", 0x0F, b"a")
        await manager.handle_fast_extension("p", 0x10, b"a")
        await manager.handle_fast_extension("p", 0x11, b"a")
        fast.decode_suggest.assert_called_once()
        fast.handle_suggest.assert_called_once()
        fast.handle_have_all.assert_called_once()
        fast.handle_have_none.assert_called_once()
        fast.decode_reject.assert_called_once()
        fast.handle_reject.assert_called_once()
        fast.decode_allow_fast.assert_called_once()
        fast.handle_allow_fast.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_extension_protocol_success_and_error(self):
        manager = ExtensionManager()
        manager.extension_states["protocol"].status = ExtensionStatus.ACTIVE
        proto = Mock()
        proto.handle_extension_message = AsyncMock()
        manager.extensions["protocol"] = proto
        await manager.handle_extension_protocol("p", 5, b"x")
        proto.handle_extension_message.assert_called_once()
        # error branch
        proto2 = Mock()
        proto2.handle_extension_message = AsyncMock(side_effect=RuntimeError("e"))
        manager.extensions["protocol"] = proto2
        await manager.handle_extension_protocol("p", 5, b"x")
        assert manager.extension_states["protocol"].error_count >= 1

    @pytest.mark.asyncio
    async def test_handle_pex_message_added_and_dropped(self):
        manager = ExtensionManager()
        manager.extension_states["pex"].status = ExtensionStatus.ACTIVE
        pex = Mock()
        pex.decode_peers_list = Mock(return_value=[PEXPeer(ip="127.0.0.1", port=6881)])
        pex.handle_added_peers = AsyncMock()
        pex.handle_dropped_peers = AsyncMock()
        manager.extensions["pex"] = pex
        await manager.handle_pex_message("peer", 0, b"data")
        await manager.handle_pex_message("peer", 1, b"data")
        pex.handle_added_peers.assert_called_once()
        pex.handle_dropped_peers.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_dht_message_success_and_exception(self):
        manager = ExtensionManager()
        manager.extension_states["dht"].status = ExtensionStatus.ACTIVE
        dht = Mock()
        dht.handle_dht_message = AsyncMock(return_value=b"ok")
        manager.extensions["dht"] = dht
        out = await manager.handle_dht_message("1.2.3.4", 6881, b"q")
        assert out == b"ok"
        # error path
        dht2 = Mock()
        dht2.handle_dht_message = AsyncMock(side_effect=RuntimeError("err"))
        manager.extensions["dht"] = dht2
        out2 = await manager.handle_dht_message("1.2.3.4", 6881, b"q")
        assert out2 is None

    @pytest.mark.asyncio
    async def test_download_piece_from_webseed_success_and_error(self):
        manager = ExtensionManager()
        manager.extension_states["webseed"].status = ExtensionStatus.ACTIVE
        ws = Mock()
        ws.download_piece = AsyncMock(return_value=b"piece")
        manager.extensions["webseed"] = ws
        data = await manager.download_piece_from_webseed("id", Mock())
        assert data == b"piece"
        # error branch
        ws2 = Mock()
        ws2.download_piece = AsyncMock(side_effect=RuntimeError("bad"))
        manager.extensions["webseed"] = ws2
        data2 = await manager.download_piece_from_webseed("id", Mock())
        assert data2 is None


class TestWebSeedBranchCoverage:
    """Cover range success/failure, exception, and recency/none-session branches."""

    @pytest.mark.asyncio
    async def test_download_piece_range_success_and_failure_and_exception(self):
        ws = WebSeedExtension()
        ws_id = ws.add_webseed("http://example.com/file")
        # success
        resp_ok = AsyncMock(); resp_ok.status = 206; resp_ok.read = AsyncMock(return_value=b"abc")
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.return_value.__aenter__.return_value = resp_ok
            await ws.start()
            data = await ws.download_piece_range(ws_id, 0, 3)
            assert data == b"abc"
        # failure (non-206)
        resp_fail = AsyncMock(); resp_fail.status = 404
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.return_value.__aenter__.return_value = resp_fail
            data2 = await ws.download_piece_range(ws_id, 0, 5)
            assert data2 is None
        # exception path
        with patch("aiohttp.ClientSession.get", side_effect=RuntimeError("boom")):
            data3 = await ws.download_piece_range(ws_id, 0, 5)
            assert data3 is None
        await ws.stop()

    def test_add_webseed_without_loop_emits_no_exception(self):
        ws = WebSeedExtension()
        ws_id = ws.add_webseed("http://example.com/file")
        assert ws_id in ws.list_webseeds()

    def test_get_best_webseed_recency_scoring(self):
        ws = WebSeedExtension()
        a = ws.add_webseed("http://a/x"); b = ws.add_webseed("http://b/x")
        ws.webseeds[a].success_rate = 0.5; ws.webseeds[a].last_accessed = time.time()
        ws.webseeds[b].success_rate = 0.6; ws.webseeds[b].last_accessed = time.time() - 4000
        best = ws.get_best_webseed()
        assert best in {a, b}

    @pytest.mark.asyncio
    async def test_health_check_session_none_guard(self):
        ws = WebSeedExtension()
        ws_id = ws.add_webseed("http://example.com/file")
        # Monkeypatch start so session stays None to trigger guard
        async def no_start():
            return None
        ws.start = no_start  # type: ignore
        ok = await ws.health_check(ws_id)
        assert ok is False
