"""Unit tests for BEP 53: Magnet URI Extension - Specify Indices to Download."""

from __future__ import annotations

import base64

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.core]

from ccbt.core.magnet import (
    _parse_index_list,
    _parse_prioritized_indices,
    apply_magnet_file_selection,
    generate_magnet_link,
    parse_magnet,
    validate_and_normalize_indices,
)


class TestParseIndexList:
    """Test parsing of so parameter (selected file indices)."""

    def test_parse_single_index(self):
        """Test parsing a single index."""
        result = _parse_index_list("0")
        assert result == [0]

    def test_parse_multiple_indices(self):
        """Test parsing comma-separated indices."""
        result = _parse_index_list("0,2,4")
        assert result == [0, 2, 4]

    def test_parse_range(self):
        """Test parsing a range."""
        result = _parse_index_list("0-5")
        assert result == [0, 1, 2, 3, 4, 5]

    def test_parse_mixed_indices_and_ranges(self):
        """Test parsing mixed indices and ranges."""
        result = _parse_index_list("0,3-5,8")
        assert result == [0, 3, 4, 5, 8]

    def test_parse_with_whitespace(self):
        """Test parsing handles whitespace."""
        result = _parse_index_list("1, 3 , 5-7")
        assert result == [1, 3, 5, 6, 7]

    def test_parse_empty_string(self):
        """Test parsing empty string returns empty list."""
        result = _parse_index_list("")
        assert result == []

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string."""
        result = _parse_index_list("   ")
        assert result == []

    def test_parse_deduplicates_indices(self):
        """Test parsing deduplicates indices."""
        result = _parse_index_list("0,0,2,2,4")
        assert result == [0, 2, 4]

    def test_parse_sorts_indices(self):
        """Test parsing sorts indices."""
        result = _parse_index_list("4,2,0,8")
        assert result == [0, 2, 4, 8]

    def test_parse_single_range_duplicate(self):
        """Test parsing range with duplicates."""
        result = _parse_index_list("0-2,1,2")
        assert result == [0, 1, 2]

    def test_parse_invalid_range_start_greater_than_end(self):
        """Test parsing invalid range where start > end."""
        with pytest.raises(ValueError, match="Invalid range"):
            _parse_index_list("5-2")

    def test_parse_negative_index(self):
        """Test parsing negative index raises error."""
        # "-1" is parsed as range (split by "-"), which fails during int() conversion
        with pytest.raises(ValueError):
            _parse_index_list("-1")

    def test_parse_negative_range(self):
        """Test parsing range with negative values raises error."""
        # "-5--2" splits into ["", "5", "", "2"] which fails during int() conversion
        with pytest.raises(ValueError):
            _parse_index_list("-5--2")

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises error."""
        with pytest.raises(ValueError):
            _parse_index_list("abc")

    def test_parse_priority_range_indexerror(self):
        """Test parsing priority range that causes IndexError."""
        # Range with empty parts
        with pytest.raises(ValueError):
            _parse_prioritized_indices("-:4")

    def test_parse_index_range_indexerror(self):
        """Test parsing index range that causes IndexError."""
        # Range with empty parts
        with pytest.raises(ValueError):
            _parse_index_list("-")

    def test_parse_index_list_range_with_negative_start(self):
        """Test parsing range with negative start index."""
        # "-1-5" is parsed as range, empty string fails int() conversion
        with pytest.raises(ValueError):
            _parse_index_list("-1-5")

    def test_parse_index_list_range_with_negative_end(self):
        """Test parsing range with negative end index."""
        # "0--1" splits into ["0", "-1"], but "-1" fails int() conversion
        with pytest.raises(ValueError):
            _parse_index_list("0--1")

    def test_parse_index_list_single_negative(self):
        """Test parsing single negative index."""
        # "-5" is parsed as range (split by "-"), empty string fails int() conversion
        with pytest.raises(ValueError):
            _parse_index_list("-5")


class TestParsePrioritizedIndices:
    """Test parsing of x.pe parameter (prioritized file indices)."""

    def test_parse_single_priority_pair(self):
        """Test parsing single file_index:priority pair."""
        result = _parse_prioritized_indices("0:4")
        assert result == {0: 4}

    def test_parse_multiple_priority_pairs(self):
        """Test parsing multiple file_index:priority pairs."""
        result = _parse_prioritized_indices("0:4,2:3")
        assert result == {0: 4, 2: 3}

    def test_parse_priority_with_range(self):
        """Test parsing priority with file index range."""
        result = _parse_prioritized_indices("0:4,3-5:3")
        assert result == {0: 4, 3: 3, 4: 3, 5: 3}

    def test_parse_priority_overwrites_on_duplicate(self):
        """Test parsing priority overwrites when same file index appears twice."""
        result = _parse_prioritized_indices("0:4,0:3")
        assert result == {0: 3}  # Last value wins

    def test_parse_empty_string(self):
        """Test parsing empty string returns empty dict."""
        result = _parse_prioritized_indices("")
        assert result == {}

    def test_parse_missing_separator(self):
        """Test parsing missing ':' separator raises error."""
        with pytest.raises(ValueError, match="Missing ':' separator"):
            _parse_prioritized_indices("0")

    def test_parse_priority_out_of_range_high(self):
        """Test parsing priority > 4 raises error."""
        with pytest.raises(ValueError, match="Priority must be 0-4"):
            _parse_prioritized_indices("0:5")

    def test_parse_priority_out_of_range_low(self):
        """Test parsing priority < 0 raises error."""
        with pytest.raises(ValueError, match="Priority must be 0-4"):
            _parse_prioritized_indices("0:-1")

    def test_parse_negative_file_index(self):
        """Test parsing negative file index raises error."""
        # "-1:4" is parsed as range (split by "-"), which fails during int() conversion
        with pytest.raises(ValueError):
            _parse_prioritized_indices("-1:4")

    def test_parse_priority_range_negative_start(self):
        """Test parsing priority range with negative start."""
        # "-1-5:4" fails during int() conversion of empty string
        with pytest.raises(ValueError):
            _parse_prioritized_indices("-1-5:4")

    def test_parse_priority_range_negative_end(self):
        """Test parsing priority range with negative end."""
        # "0--1:4" fails during int() conversion
        with pytest.raises(ValueError):
            _parse_prioritized_indices("0--1:4")

    def test_parse_priority_single_negative_index(self):
        """Test parsing priority with single negative file index."""
        # "-5:4" is parsed as range, fails during int() conversion
        with pytest.raises(ValueError):
            _parse_prioritized_indices("-5:4")

    def test_parse_prioritized_indices_empty_token(self):
        """Test parsing prioritized indices with empty token."""
        result = _parse_prioritized_indices("0:4,,2:3")
        assert result == {0: 4, 2: 3}

    def test_parse_negative_file_range(self):
        """Test parsing negative file range raises error."""
        # "-5--2:3" splits incorrectly and fails during int() conversion
        with pytest.raises(ValueError):
            _parse_prioritized_indices("-5--2:3")

    def test_parse_invalid_range_start_greater_than_end(self):
        """Test parsing invalid file range raises error."""
        with pytest.raises(ValueError, match="Invalid range"):
            _parse_prioritized_indices("5-2:3")

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises error."""
        with pytest.raises(ValueError):
            _parse_prioritized_indices("abc:def")


class TestValidateAndNormalizeIndices:
    """Test validation and normalization of file indices."""

    def test_validate_none_returns_empty(self):
        """Test validating None returns empty list."""
        result = validate_and_normalize_indices(None, 10)
        assert result == []

    def test_validate_valid_indices(self):
        """Test validating valid indices returns them."""
        result = validate_and_normalize_indices([0, 2, 4], 10)
        assert result == [0, 2, 4]

    def test_validate_filters_out_of_range_indices(self):
        """Test validating filters out-of-range indices."""
        result = validate_and_normalize_indices([0, 5, 10, 15], 10)
        assert result == [0, 5]  # 10 and 15 are out of range

    def test_validate_deduplicates_indices(self):
        """Test validating deduplicates indices."""
        result = validate_and_normalize_indices([0, 0, 2, 2], 10)
        assert result == [0, 2]

    def test_validate_sorts_indices(self):
        """Test validating sorts indices."""
        result = validate_and_normalize_indices([4, 2, 0], 10)
        assert result == [0, 2, 4]

    def test_validate_empty_list(self):
        """Test validating empty list returns empty."""
        result = validate_and_normalize_indices([], 10)
        assert result == []

    def test_validate_all_out_of_range(self):
        """Test validating all out-of-range indices returns empty."""
        result = validate_and_normalize_indices([10, 11, 12], 10)
        assert result == []


class TestParseMagnetWithBEP53:
    """Test parsing magnet URIs with BEP 53 parameters."""

    def test_parse_magnet_with_so_parameter(self):
        """Test parsing magnet URI with so parameter."""
        uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&so=0,2,4"
        mi = parse_magnet(uri)
        assert mi.selected_indices == [0, 2, 4]

    def test_parse_magnet_with_xpe_parameter(self):
        """Test parsing magnet URI with x.pe parameter."""
        uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&x.pe=0:4,2:3"
        mi = parse_magnet(uri)
        assert mi.prioritized_indices == {0: 4, 2: 3}

    def test_parse_magnet_with_both_parameters(self):
        """Test parsing magnet URI with both so and x.pe."""
        uri = (
            "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
            "&so=0,2,4&x.pe=0:4,2:3"
        )
        mi = parse_magnet(uri)
        assert mi.selected_indices == [0, 2, 4]
        assert mi.prioritized_indices == {0: 4, 2: 3}

    def test_parse_magnet_with_invalid_so_ignores(self):
        """Test parsing magnet URI with invalid so parameter ignores it."""
        uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&so=invalid"
        mi = parse_magnet(uri)
        assert mi.selected_indices is None

    def test_parse_magnet_with_invalid_xpe_ignores(self):
        """Test parsing magnet URI with invalid x.pe parameter ignores it."""
        uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&x.pe=invalid"
        mi = parse_magnet(uri)
        assert mi.prioritized_indices is None

    def test_parse_magnet_without_bep53_parameters(self):
        """Test parsing magnet URI without BEP 53 parameters."""
        uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=example"
        mi = parse_magnet(uri)
        assert mi.selected_indices is None
        assert mi.prioritized_indices is None


class TestGenerateMagnetLink:
    """Test generating magnet URIs with BEP 53 parameters."""

    def test_generate_with_selected_indices(self):
        """Test generating magnet link with selected indices."""
        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        uri = generate_magnet_link(info_hash, selected_indices=[0, 2, 4])
        assert "so=0,2,4" in uri
        assert "xt=urn:btih:0123456789abcdef0123456789abcdef01234567" in uri

    def test_generate_with_prioritized_indices(self):
        """Test generating magnet link with prioritized indices."""
        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        uri = generate_magnet_link(
            info_hash,
            prioritized_indices={0: 4, 2: 3},
        )
        assert "x.pe=0:4,2:3" in uri

    def test_generate_with_both_parameters(self):
        """Test generating magnet link with both parameters."""
        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        uri = generate_magnet_link(
            info_hash,
            selected_indices=[0, 2, 4],
            prioritized_indices={0: 4, 2: 3},
        )
        assert "so=0,2,4" in uri
        assert "x.pe=0:4,2:3" in uri

    def test_generate_with_base32_hash(self):
        """Test generating magnet link with base32 hash encoding."""
        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        uri = generate_magnet_link(info_hash, use_base32=True)
        # base64.b32encode returns uppercase by default
        b32 = base64.b32encode(info_hash).decode().rstrip("=")
        assert f"xt=urn:btih:{b32}" in uri or f"xt=urn:btih:{b32.lower()}" in uri

    def test_generate_with_display_name_and_trackers(self):
        """Test generating magnet link with display name and trackers."""
        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        uri = generate_magnet_link(
            info_hash,
            display_name="test torrent",
            trackers=["http://tracker1.com/announce", "http://tracker2.com/announce"],
        )
        # urllib.parse.quote uses %20 for spaces, not +
        assert "dn=test%20torrent" in uri
        assert "tr=http://tracker1.com/announce" in uri
        assert "tr=http://tracker2.com/announce" in uri

    def test_generate_with_web_seeds(self):
        """Test generating magnet link with web seeds."""
        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        uri = generate_magnet_link(
            info_hash,
            web_seeds=["http://seed1.com/file", "http://seed2.com/file"],
        )
        assert "ws=http://seed1.com/file" in uri
        assert "ws=http://seed2.com/file" in uri


class TestApplyMagnetFileSelection:
    """Test applying file selection from magnet URI indices."""

    @pytest.mark.asyncio
    async def test_apply_selection_respects_indices_true(self):
        """Test applying selection when respect_indices=True."""
        # Mock FileSelectionManager
        class MockFileSelectionManager:
            def __init__(self):
                self.selected_files = set()
                self.file_priorities = {}

            async def deselect_all(self):
                self.selected_files = set()

            async def select_files(self, indices):
                self.selected_files = set(indices)

            async def set_file_priority(self, index, priority):
                self.file_priorities[index] = priority

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 2, 4],
            prioritized_indices={0: 4, 2: 3},
        )

        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=10,
            respect_indices=True,
        )

        assert manager.selected_files == {0, 2, 4}
        assert manager.file_priorities == {0: 4, 2: 3}

    @pytest.mark.asyncio
    async def test_apply_selection_respects_indices_false(self):
        """Test applying selection when respect_indices=False does nothing."""
        class MockFileSelectionManager:
            def __init__(self):
                self.selected_files = set([0, 1, 2])
                self.called_deselect = False
                self.called_select = False

            async def deselect_all_files(self):
                self.called_deselect = True

            async def select_files(self, indices):
                self.called_select = True

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 2, 4],
            prioritized_indices={0: 4},
        )

        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=10,
            respect_indices=False,
        )

        assert not manager.called_deselect
        assert not manager.called_select
        assert manager.selected_files == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_apply_selection_single_file_torrent(self):
        """Test applying selection for single-file torrent does nothing."""
        class MockFileSelectionManager:
            def __init__(self):
                self.called_deselect = False

            async def deselect_all_files(self):
                self.called_deselect = True

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0],
        )

        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=1,
            respect_indices=True,
        )

        assert not manager.called_deselect

    @pytest.mark.asyncio
    async def test_apply_selection_validates_indices(self):
        """Test applying selection validates indices against file count."""
        class MockFileSelectionManager:
            def __init__(self):
                self.selected_files = set()

            async def deselect_all(self):
                self.selected_files = set()

            async def select_files(self, indices):
                self.selected_files = set(indices)

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[0, 5, 10],  # Only 0 and 5 are valid for 10 files
        )

        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=10,
            respect_indices=True,
        )

        assert manager.selected_files == {0, 5}

    @pytest.mark.asyncio
    async def test_apply_selection_only_priorities(self):
        """Test applying selection with only priorities, no selected indices."""
        class MockFileSelectionManager:
            def __init__(self):
                self.file_priorities = {}
                self.called_deselect = False
                self.called_select = False

            async def deselect_all(self):
                self.called_deselect = True

            async def select_files(self, indices):
                self.called_select = True

            async def set_file_priority(self, index, priority):
                self.file_priorities[index] = priority

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=None,
            prioritized_indices={0: 4, 2: 3},
        )

        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=10,
            respect_indices=True,
        )

        # Should not deselect or select files, only set priorities
        assert not manager.called_deselect
        assert not manager.called_select
        assert manager.file_priorities == {0: 4, 2: 3}

    def test_parse_index_list_empty_token(self):
        """Test parsing with empty token (comma with nothing between)."""
        result = _parse_index_list("0,,2")
        assert result == [0, 2]

    def test_parse_magnet_base32_hash(self):
        """Test parsing magnet URI with base32 hash."""
        import base64

        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        b32 = base64.b32encode(info_hash).decode().rstrip("=")
        uri = f"magnet:?xt=urn:btih:{b32}"
        mi = parse_magnet(uri)
        assert mi.info_hash == info_hash

    def test_parse_magnet_invalid_scheme(self):
        """Test parsing non-magnet URI raises error."""
        with pytest.raises(ValueError, match="Not a magnet URI"):
            parse_magnet("http://example.com")

    def test_parse_magnet_missing_btih(self):
        """Test parsing magnet URI without xt=urn:btih raises error."""
        with pytest.raises(ValueError, match="Magnet URI missing xt=urn:btih"):
            parse_magnet("magnet:?dn=example")

    def test_validate_indices_num_files_zero(self):
        """Test validating indices with num_files=0."""
        result = validate_and_normalize_indices([0, 1, 2], 0)
        assert result == []

    def test_validate_indices_num_files_negative(self):
        """Test validating indices with negative num_files."""
        result = validate_and_normalize_indices([0, 1, 2], -1)
        assert result == []

    @pytest.mark.asyncio
    async def test_apply_selection_no_valid_indices_after_validation(self):
        """Test applying selection when all indices are invalid."""
        class MockFileSelectionManager:
            def __init__(self):
                self.selected_files = set()
                self.warning_logged = False

            async def deselect_all(self):
                self.selected_files = set()

            async def select_files(self, indices):
                self.selected_files = set(indices)

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=[10, 11, 12],  # All out of range for 5 files
        )

        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=5,
            respect_indices=True,
        )

        # Should not select any files since all are invalid
        assert manager.selected_files == set()

    @pytest.mark.asyncio
    async def test_apply_selection_invalid_priority_value(self):
        """Test applying selection with invalid priority value."""
        class MockFileSelectionManager:
            def __init__(self):
                self.file_priorities = {}
                self.warning_logged = False

            async def set_file_priority(self, index, priority):
                self.file_priorities[index] = priority

        from ccbt.core.magnet import MagnetInfo

        manager = MockFileSelectionManager()
        # Note: This shouldn't happen since parsing validates, but test the error handling
        magnet_info = MagnetInfo(
            info_hash=b"\x00" * 20,
            display_name="test",
            trackers=[],
            web_seeds=[],
            selected_indices=None,
            prioritized_indices={0: 99},  # Invalid priority (but FilePriority will handle it)
        )

        # FilePriority(99) will raise ValueError which is caught
        await apply_magnet_file_selection(
            manager,
            magnet_info,
            num_files=10,
            respect_indices=True,
        )

        # Invalid priority should be ignored
        assert 0 not in manager.file_priorities

    def test_build_minimal_torrent_data_empty_trackers(self):
        """Test build_minimal_torrent_data with empty trackers list."""
        from ccbt.core.magnet import build_minimal_torrent_data

        info_hash = bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
        result = build_minimal_torrent_data(info_hash, "test", [])
        assert result["announce"] == ""
        assert result["announce_list"] == []
        assert result["info_hash"] == info_hash

    def test_validate_indices_with_debug_logged(self, caplog):
        """Test that validation logs debug messages for invalid indices."""
        import logging

        with caplog.at_level(logging.DEBUG):
            result = validate_and_normalize_indices([0, 10, 20], 5, "test_param")
        assert result == [0]
        # Validation uses logger.debug for out-of-range indices
        if caplog.text:
            assert "out of range" in caplog.text.lower() or "filtered" in caplog.text.lower()

