"""Piece availability health bar widget.

Displays a beautiful progress bar showing piece availability with colored segments.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.widgets import Static
else:
    try:
        from textual.widgets import Static
    except ImportError:
        class Static:  # type: ignore[no-redef]
            pass

from rich.text import Text

from ccbt.i18n import _

logger = logging.getLogger(__name__)

PIECE_HEALTH_THRESHOLDS: tuple[tuple[str, float], ...] = (
    ("excellent", 0.8),
    ("healthy", 0.5),
    ("fragile", 0.25),
    ("empty", 0.0),
)
PIECE_HEALTH_GLYPHS = {
    "excellent": "■",
    "healthy": "■",
    "fragile": "▣",
    "empty": "□",
}
PIECE_HEALTH_COLORS = {
    "excellent": "green",
    "healthy": "yellow",
    "fragile": "orange1",
    "empty": "grey46",
}

PIECE_HEALTH_LABELS = {
    "excellent": _("≥ 80% available"),
    "healthy": _("50–79% available"),
    "fragile": _("25–49% available"),
    "empty": _("Unavailable"),
}

__all__ = [
    "PieceAvailabilityHealthBar",
    "PIECE_HEALTH_THRESHOLDS",
    "PIECE_HEALTH_GLYPHS",
    "PIECE_HEALTH_COLORS",
    "PIECE_HEALTH_LABELS",
    "determine_piece_health_level",
]


def determine_piece_health_level(ratio: float) -> str:
    """Determine health level name for a piece availability ratio."""
    for level, threshold in PIECE_HEALTH_THRESHOLDS:
        if ratio >= threshold:
            return level
    return "empty"


class PieceAvailabilityHealthBar(Static):  # type: ignore[misc]
    """Widget to display piece availability as a colored health bar.
    
    Shows a pictogram with square glyphs representing piece availability:
    - Green solid squares: High availability
    - Yellow outlined squares: Medium availability
    - Orange outlines: Low availability
    - Gray open squares: Missing pieces
    """

    DEFAULT_CSS = """
    PieceAvailabilityHealthBar {
        height: auto;
        min-height: 3;
        width: 1fr;
    }
    """

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize piece availability health bar."""
        super().__init__(*args, **kwargs)
        self._availability: list[int] = []
        self._max_peers: int = 0
        self._piece_health_data: dict[str, Any] | None = None  # Full piece health data from DataProvider
        self._grid_rows: int = 8  # Number of rows in multi-line grid
        self._grid_cols: int = 0  # Calculated based on terminal width

    def update_availability(
        self,
        availability: list[int],
        max_peers: int | None = None,
    ) -> None:
        """Update the health bar with piece availability data.
        
        Args:
            availability: List of peer counts for each piece (index = piece index, value = peer count)
            max_peers: Maximum number of peers (for color scaling). If None, uses max from availability.
        """
        self._availability = availability
        if max_peers is None:
            self._max_peers = max(availability) if availability else 1
        else:
            self._max_peers = max(max_peers, 1)
        
        self._render_bar()
    
    def update_from_piece_health(
        self,
        piece_health: dict[str, Any],
    ) -> None:
        """Update the health bar with full piece health data from DataProvider.
        
        Args:
            piece_health: Dictionary from DataProvider.get_piece_health() containing:
                - availability: List of peer counts
                - max_peers: Maximum peer count
                - availability_histogram: Histogram buckets
                - prioritized_pieces: List of prioritized piece indices
                - dht_success_ratio: DHT success ratio
        """
        self._piece_health_data = piece_health
        self._availability = piece_health.get("availability", [])
        self._max_peers = piece_health.get("max_peers", 0) or max(self._availability) if self._availability else 1
        self._render_bar()

    def _render_bar(self) -> None:
        """Render the health bar with multi-line ASCII square grid."""
        if not self._availability:
            self.update(Text(_("No availability data"), style="dim"))
            return
        
        num_pieces = len(self._availability)
        if num_pieces == 0:
            self.update(Text(_("No pieces"), style="dim"))
            return
        
        # Get terminal width for grid calculation
        try:
            width = self.size.width if hasattr(self, "size") and self.size else 60
        except Exception:
            width = 60
        
        # Calculate grid dimensions
        # Reserve space for labels and callouts (about 20 chars)
        available_width = max(20, width - 20)
        self._grid_cols = available_width // 2  # 2 chars per piece (square + space)
        pieces_per_cell = max(1, num_pieces // (self._grid_rows * self._grid_cols))
        
        # Build multi-line grid
        grid_lines: list[Text] = []
        piece_idx = 0
        
        for row in range(self._grid_rows):
            row_text = Text()
            for col in range(self._grid_cols):
                if piece_idx >= num_pieces:
                    # Fill remaining cells with empty squares
                    row_text.append("□ ", style="grey46")
                    continue
                
                # Get piece data (may aggregate multiple pieces per cell)
                cell_peer_counts = []
                for _ in range(pieces_per_cell):
                    if piece_idx < num_pieces:
                        cell_peer_counts.append(self._availability[piece_idx])
                        piece_idx += 1
                
                if not cell_peer_counts:
                    row_text.append("□ ", style="grey46")
                    continue
                
                # Use average peer count for cell
                avg_peer_count = sum(cell_peer_counts) / len(cell_peer_counts)
                ratio = avg_peer_count / self._max_peers if self._max_peers else 0.0
                level = determine_piece_health_level(ratio)
                glyph = PIECE_HEALTH_GLYPHS.get(level, "□")
                color = PIECE_HEALTH_COLORS.get(level, "grey46")
                
                # Enhanced prioritized piece highlighting
                is_prioritized = False
                if self._piece_health_data:
                    prioritized = self._piece_health_data.get("prioritized_pieces", [])
                    start_idx = piece_idx - len(cell_peer_counts)
                    is_prioritized = any(start_idx <= p < piece_idx for p in prioritized)
                    if is_prioritized:
                        # Use brighter color and different glyph for prioritized pieces
                        if color == "green":
                            color = "bright_green"
                            glyph = "◆"  # Diamond for prioritized
                        elif color == "yellow":
                            color = "bright_yellow"
                            glyph = "◆"
                        elif color == "orange1":
                            color = "bright_red"
                            glyph = "◆"
                        else:
                            glyph = "◆"
                            color = "bright_cyan"
                
                row_text.append(glyph, style=color)
                row_text.append(" ", style="dim")
            
            grid_lines.append(row_text)
        
        # Build summary and callouts
        available_pieces = sum(1 for count in self._availability if count > 0)
        total_pieces = len(self._availability)
        availability_pct = (available_pieces / total_pieces * 100) if total_pieces > 0 else 0.0
        avg_peers = sum(self._availability) / total_pieces if total_pieces > 0 else 0.0
        
        # Extract histogram and rare piece info
        histogram = {}
        rare_count = 0
        verifying_count = 0
        if self._piece_health_data:
            histogram = self._piece_health_data.get("availability_histogram", {})
            rare_count = histogram.get("rare", 0)
            # Check for pieces being verified (would need piece manager state)
        
        # Build full text with grid and labels
        full_text = Text()
        
        # Add grid
        for row_text in grid_lines:
            full_text.append(row_text)
            full_text.append("\n")
        
        # Add summary line
        summary = Text()
        summary.append(f"{_('Health')}: ", style="cyan")
        if availability_pct >= 80:
            summary.append(f"{availability_pct:.1f}%", style="green")
        elif availability_pct >= 50:
            summary.append(f"{availability_pct:.1f}%", style="yellow")
        else:
            summary.append(f"{availability_pct:.1f}%", style="red")
        summary.append(f" | {available_pieces}/{total_pieces} {_('pieces')} | ", style="dim")
        summary.append(f"avg {avg_peers:.1f} {_('peers')}", style="dim")
        full_text.append(summary)
        full_text.append("\n")
        
        # Add callouts for rare pieces and other metrics
        callouts = Text()
        if rare_count > 0:
            callouts.append(f"Rare: {rare_count} ", style="orange1")
        if histogram.get("missing", 0) > 0:
            callouts.append(f"Missing: {histogram.get('missing', 0)} ", style="red")
        
        # Enhanced DHT success ratio indicator with color coding
        if self._piece_health_data:
            dht_ratio = self._piece_health_data.get("dht_success_ratio", 0.0)
            if dht_ratio > 0:
                dht_pct = dht_ratio * 100
                if dht_pct >= 80:
                    dht_style = "green"
                elif dht_pct >= 50:
                    dht_style = "yellow"
                else:
                    dht_style = "red"
                callouts.append(f"DHT: {dht_pct:.0f}% ", style=dht_style)
            
            # Piece selection strategy indicator
            piece_selection = self._piece_health_data.get("piece_selection", {})
            if isinstance(piece_selection, dict):
                strategy = piece_selection.get("strategy") or piece_selection.get("selection_strategy")
                if strategy:
                    strategy_display = str(strategy).replace("_", " ").title()
                    callouts.append(f"Strategy: {strategy_display} ", style="cyan")
        
        # Piece download progress states (if available from torrent status)
        if self._piece_health_data:
            # Try to get piece states from piece_selection or torrent status
            piece_selection = self._piece_health_data.get("piece_selection", {})
            downloading_count = 0
            verifying_count = 0
            completed_count = 0
            
            # Check for piece states in piece_selection
            if isinstance(piece_selection, dict):
                downloading_count = piece_selection.get("downloading_pieces", 0) or len(piece_selection.get("downloading", []))
                verifying_count = piece_selection.get("verifying_pieces", 0) or len(piece_selection.get("verifying", []))
                completed_count = piece_selection.get("completed_pieces", 0)
            
            # If not found, try to infer from torrent status
            if downloading_count == 0 and verifying_count == 0:
                # Check if we have pieces_completed info
                pieces_completed = self._piece_health_data.get("pieces_completed")
                pieces_total = len(self._availability)
                if pieces_completed is not None and pieces_total > 0:
                    completed_count = pieces_completed
                    # Estimate downloading as pieces with availability but not completed
                    downloading_count = max(0, available_pieces - completed_count)
            
            if downloading_count > 0:
                callouts.append(f"↓ {downloading_count} ", style="blue")
            if verifying_count > 0:
                callouts.append(f"✓ {verifying_count} ", style="magenta")
            if completed_count > 0:
                callouts.append(f"● {completed_count} ", style="green")
        
        if callouts:
            full_text.append(callouts)
            full_text.append("\n")
        
        # Add legend with enhanced information
        legend = Text()
        for level in ("excellent", "healthy", "fragile", "empty"):
            glyph = PIECE_HEALTH_GLYPHS[level]
            color = PIECE_HEALTH_COLORS[level]
            legend.append(" ")
            legend.append(glyph, style=color)
            legend.append(f" {PIECE_HEALTH_LABELS[level]}", style="dim")
        
        # Add prioritized piece indicator to legend
        if self._piece_health_data and self._piece_health_data.get("prioritized_pieces"):
            legend.append("  ")
            legend.append("◆", style="bright_cyan")
            legend.append(" Prioritized", style="dim")
        
        # Add download state indicators to legend
        if self._piece_health_data:
            piece_selection = self._piece_health_data.get("piece_selection", {})
            if isinstance(piece_selection, dict) and (piece_selection.get("downloading_pieces") or piece_selection.get("verifying_pieces")):
                legend.append("  ")
                legend.append("↓", style="blue")
                legend.append(" Downloading  ", style="dim")
                legend.append("✓", style="magenta")
                legend.append(" Verifying  ", style="dim")
                legend.append("●", style="green")
                legend.append(" Completed", style="dim")
        
        full_text.append(legend)
        
        self.update(full_text)

    def _get_color_for_availability(self, peer_count: int) -> str:
        """Get color code for piece availability.
        
        Args:
            peer_count: Number of peers that have this piece
            
        Returns:
            Color name for Rich Text
        """
        if self._max_peers == 0:
            return PIECE_HEALTH_COLORS["empty"]
        
        ratio = peer_count / self._max_peers
        level = determine_piece_health_level(ratio)
        return PIECE_HEALTH_COLORS.get(level, "gray50")




















