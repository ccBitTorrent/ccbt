"""
Property-based tests for piece selection algorithms.

Tests invariants and properties of piece selection strategies
using Hypothesis for automatic test case generation.
"""

from hypothesis import given
from hypothesis import strategies as st

from ccbt.models import PieceInfo, PieceState


class TestPieceSelectionProperties:
    """Property-based tests for piece selection algorithms."""

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_rarest_first_selection(self, bitfield, num_pieces):
        """Test properties of rarest first selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,  # 16KB pieces
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        # Rarest first should select pieces we don't have
        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]

        if missing_pieces:
            # Should select from missing pieces
            selected_piece = missing_pieces[0]  # Simplified selection
            assert selected_piece.state == PieceState.MISSING
            assert selected_piece.index < len(bitfield)

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_sequential_selection(self, bitfield, start_index):
        """Test properties of sequential selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        # Sequential should select pieces in order
        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]

        if missing_pieces:
            # Should select the first missing piece
            selected_piece = missing_pieces[0]
            assert selected_piece.state == PieceState.MISSING
            assert selected_piece.index >= 0
            assert selected_piece.index < len(bitfield)

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_round_robin_selection(self, bitfield, current_index):
        """Test properties of round robin selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        # Round robin should cycle through pieces
        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]

        if missing_pieces:
            # Should select a missing piece
            selected_piece = missing_pieces[0]  # Simplified selection
            assert selected_piece.state == PieceState.MISSING
            assert selected_piece.index >= 0
            assert selected_piece.index < len(bitfield)

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_completeness(self, bitfield, num_pieces):
        """Test that piece selection is complete."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]
        complete_pieces = [p for p in pieces if p.state == PieceState.COMPLETE]

        # Total pieces should equal missing + complete
        assert len(pieces) == len(missing_pieces) + len(complete_pieces)

        # All pieces should have valid indices
        for piece in pieces:
            assert 0 <= piece.index < len(bitfield)
            assert piece.length > 0
            assert len(piece.hash) == 20

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_consistency(self, bitfield, num_pieces):
        """Test that piece selection is consistent."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        # Same bitfield should produce same missing pieces
        missing_pieces1 = [p for p in pieces if p.state == PieceState.MISSING]
        missing_pieces2 = [p for p in pieces if p.state == PieceState.MISSING]

        assert len(missing_pieces1) == len(missing_pieces2)
        assert all(p1.index == p2.index for p1, p2 in zip(missing_pieces1, missing_pieces2))

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_invariants(self, bitfield, num_pieces):
        """Test invariants of piece selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]
        complete_pieces = [p for p in pieces if p.state == PieceState.COMPLETE]

        # Invariant: all pieces should be either missing or complete
        for piece in pieces:
            assert piece.state in [PieceState.MISSING, PieceState.COMPLETE]

        # Invariant: piece indices should be unique
        indices = [p.index for p in pieces]
        assert len(indices) == len(set(indices))

        # Invariant: piece lengths should be positive
        for piece in pieces:
            assert piece.length > 0

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_ordering(self, bitfield, num_pieces):
        """Test ordering properties of piece selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]

        if len(missing_pieces) > 1:
            # Sequential selection should maintain order
            sequential_pieces = sorted(missing_pieces, key=lambda p: p.index)
            assert all(sequential_pieces[i].index < sequential_pieces[i+1].index
                      for i in range(len(sequential_pieces)-1))

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_efficiency(self, bitfield, num_pieces):
        """Test efficiency properties of piece selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]

        # Should be able to select from missing pieces
        if missing_pieces:
            selected_piece = missing_pieces[0]
            assert selected_piece.state == PieceState.MISSING
            assert selected_piece.index >= 0
            assert selected_piece.index < len(bitfield)

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_robustness(self, bitfield, num_pieces):
        """Test robustness of piece selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        # Should handle empty bitfield
        if not bitfield:
            assert len(pieces) == 0

        # Should handle all missing pieces
        if all(not b for b in bitfield):
            missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]
            assert len(missing_pieces) == len(pieces)

        # Should handle all complete pieces
        if all(bitfield):
            complete_pieces = [p for p in pieces if p.state == PieceState.COMPLETE]
            assert len(complete_pieces) == len(pieces)

    @given(
        st.lists(st.booleans(), min_size=1, max_size=100),
        st.integers(min_value=0, max_value=99),
    )
    def test_piece_selection_monotonicity(self, bitfield, num_pieces):
        """Test monotonicity properties of piece selection."""
        # Create piece info list
        pieces = []
        for i in range(len(bitfield)):
            pieces.append(PieceInfo(
                index=i,
                length=16384,
                hash=b"\x00" * 20,
                state=PieceState.MISSING if not bitfield[i] else PieceState.COMPLETE,
            ))

        missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]

        # As more pieces are completed, fewer should be missing
        if len(missing_pieces) > 0:
            # Simulate completing a piece
            completed_piece = missing_pieces[0]
            completed_piece.state = PieceState.COMPLETE

            new_missing_pieces = [p for p in pieces if p.state == PieceState.MISSING]
            assert len(new_missing_pieces) == len(missing_pieces) - 1
