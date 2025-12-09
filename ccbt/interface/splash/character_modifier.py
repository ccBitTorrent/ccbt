"""Character group modifier for animation variations.

Provides utilities to modify character groups, add variations, and transform
characters for advanced animation effects.
"""

from __future__ import annotations

import random
from typing import Any, Callable


class CharacterModifier:
    """Helper class for modifying character groups in animations."""

    # Letter width definitions for "ccBitTonic"
    LETTER_WIDTHS = {
        'c': 9, 'C': 9,
        'i': 5, 'I': 5,
        'o': 9, 'O': 9,
        'r': 9, 'R': 9,
        'e': 8, 'E': 8,
        'n': 10, 'N': 10,
        't': 10, 'T': 12,  # lowercase t is 10, capital T is 12
        'B': 13,
        ' ': 1,  # Space is 1 character
    }

    @staticmethod
    def get_letter_width(char: str) -> int:
        """Get the width of a letter character.
        
        Args:
            char: Single character
            
        Returns:
            Width in spaces
        """
        return CharacterModifier.LETTER_WIDTHS.get(char, 1)

    @staticmethod
    def find_letter_positions(text: str, target_letter: str) -> list[tuple[int, int, int]]:
        """Find positions of a specific letter in text.
        
        Args:
            text: Text to search
            target_letter: Letter to find
            
        Returns:
            List of (line_idx, start_col, width) tuples
        """
        positions = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            col = 0
            for char in line:
                if char == target_letter:
                    width = CharacterModifier.get_letter_width(char)
                    positions.append((line_idx, col, width))
                col += 1
        
        return positions

    @staticmethod
    def find_all_letters(text: str) -> dict[str, list[tuple[int, int, int]]]:
        """Find all letter positions in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary mapping letters to their positions
        """
        letter_map: dict[str, list[tuple[int, int, int]]] = {}
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            col = 0
            for char in line:
                if char.strip() and char not in letter_map:
                    letter_map[char] = []
                if char.strip():
                    width = CharacterModifier.get_letter_width(char)
                    letter_map[char].append((line_idx, col, width))
                col += 1
        
        return letter_map

    @staticmethod
    def parse_letters_by_width(text: str) -> list[dict[str, Any]]:
        """Parse text into letters based on character widths.
        
        The logo text "ccBitTonic" has no spaces between letters. Letters are
        defined by their widths. We parse by scanning for the start of letters
        (first non-space character after spaces or after previous letter) and
        using the width definitions to determine letter boundaries.
        
        Letter widths for "ccBitTonic":
        - c: 9, c: 9, B: 13, i: 5, t: 10, T: 12, o: 9, n: 10, i: 5, c: 9
        
        Args:
            text: Text to parse (no spaces between letters)
            
        Returns:
            List of letter dictionaries with 'line_idx', 'start_col', 'width', 'chars', 'char'
        """
        lines = text.split('\n')
        letters = []
        
        # Find the first line with non-space content to determine letter positions
        first_content_line_idx = None
        first_content_line = None
        for line_idx, line in enumerate(lines):
            if line.strip():
                first_content_line_idx = line_idx
                first_content_line = line
                break
        
        if first_content_line is None:
            return letters
        
        # Parse letters by scanning for letter starts and using width definitions
        # We'll scan through and when we find a non-space character, we'll
        # determine what letter it could be based on context and width
        col = 0
        i = 0
        letter_positions = []  # List of (start_col, width, char) tuples
        
        # Known letter sequence for "ccBitTonic" - we'll use this to identify letters
        # But we need to detect them by width, not by character content
        # So we'll scan and when we find a letter start, we'll try to match it
        
        # Improved parsing: scan through and identify letters by their width
        # We'll use the known sequence but also verify by checking if we've consumed
        # the expected width before finding the next letter start
        letter_sequence = ['c', 'c', 'B', 'i', 't', 'T', 'o', 'n', 'i', 'c']
        
        while i < len(first_content_line):
            if first_content_line[i] != " ":
                # Found start of a letter
                start_col = col
                letter_idx = len(letter_positions)
                
                # Determine letter from sequence
                if letter_idx < len(letter_sequence):
                    letter_char = letter_sequence[letter_idx]
                    letter_width = CharacterModifier.get_letter_width(letter_char)
                else:
                    # Fallback: try to measure block width and match to known widths
                    block_start = i
                    block_width = 0
                    while block_start + block_width < len(first_content_line) and first_content_line[block_start + block_width] != " ":
                        block_width += 1
                    
                    # Try to match block width to a known letter width
                    letter_char = '?'
                    letter_width = block_width
                    for char, width in CharacterModifier.LETTER_WIDTHS.items():
                        if width == block_width and char != ' ':
                            letter_char = char
                            letter_width = width
                            break
                
                # Verify we can actually move forward by this width
                # Check if there's enough space or if we hit a space boundary
                actual_width = letter_width
                if i + actual_width > len(first_content_line):
                    actual_width = len(first_content_line) - i
                
                # Check if we hit a space before the full width
                for check_idx in range(i, min(i + actual_width, len(first_content_line))):
                    if first_content_line[check_idx] == " ":
                        actual_width = check_idx - i
                        break
                
                # Store this letter position
                letter_positions.append((start_col, actual_width, letter_char))
                
                # Move forward by the actual width consumed
                i += actual_width
                col += actual_width
            else:
                # Space - skip it
                i += 1
                col += 1
        
        # Now create letter entries - store entire column groups for each letter
        for letter_idx, (start_col, width, letter_char) in enumerate(letter_positions):
            # Store all columns for this letter across all lines
            # This represents the entire column group for the letter
            letter_columns = []  # List of column strings, one per line
            
            for line_idx, line in enumerate(lines):
                if start_col < len(line):
                    end_col = min(start_col + width, len(line))
                    column_segment = line[start_col:end_col]
                    # Pad if needed to match width
                    if len(column_segment) < width:
                        column_segment += " " * (width - len(column_segment))
                    letter_columns.append(column_segment)
                else:
                    # Empty line for this letter
                    letter_columns.append(" " * width)
            
            # Find which line has the most content (for reference)
            best_line_idx = first_content_line_idx
            max_non_space = 0
            for line_idx, column_seg in enumerate(letter_columns):
                non_space_count = len([c for c in column_seg if c != " "])
                if non_space_count > max_non_space:
                    max_non_space = non_space_count
                    best_line_idx = line_idx
            
            letters.append({
                'line_idx': best_line_idx,  # Reference line index
                'start_col': start_col,
                'width': width,
                'columns': letter_columns,  # All columns for this letter (one per line)
                'char': letter_char,
            })
        
        return letters

    @staticmethod
    def modify_characters(
        text: str,
        modifier_func: Callable[[str, int, int], str],
    ) -> str:
        """Modify characters in text using a modifier function.
        
        Args:
            text: Text to modify
            modifier_func: Function(char, line_idx, col_idx) -> new_char
            
        Returns:
            Modified text
        """
        lines = text.split('\n')
        result_lines = []
        
        for line_idx, line in enumerate(lines):
            result_line = ""
            for col_idx, char in enumerate(line):
                new_char = modifier_func(char, line_idx, col_idx)
                result_line += new_char
            result_lines.append(result_line)
        
        return '\n'.join(result_lines)

    @staticmethod
    def replace_character_group(
        text: str,
        line_idx: int,
        start_col: int,
        width: int,
        replacement: str,
    ) -> str:
        """Replace a character group at a specific position.
        
        Args:
            text: Text to modify
            line_idx: Line index (0-based)
            start_col: Starting column
            width: Width of group
            replacement: Replacement string
            
        Returns:
            Modified text
        """
        lines = text.split('\n')
        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            if start_col < len(line):
                end_col = min(start_col + width, len(line))
                new_line = line[:start_col] + replacement + line[end_col:]
                lines[line_idx] = new_line
        return '\n'.join(lines)

    @staticmethod
    def add_variation_chars(
        text: str,
        variation_chars: str = "·*+×",
        density: float = 0.1,
    ) -> str:
        """Add variation characters randomly to text.
        
        Args:
            text: Text to modify
            variation_chars: Characters to use for variation
            density: Probability of adding variation (0.0-1.0)
            
        Returns:
            Modified text
        """
        def modifier(char: str, line_idx: int, col_idx: int) -> str:
            if char == " " and random.random() < density:
                return random.choice(variation_chars)
            return char
        
        return CharacterModifier.modify_characters(text, modifier)

    @staticmethod
    def create_whitespace_background(
        width: int,
        height: int,
        pattern: str = "|/—\\",
        time_offset: float = 0.0,
    ) -> list[str]:
        """Create animated whitespace background with pattern.
        
        Args:
            width: Terminal width
            height: Terminal height
            pattern: Pattern characters to cycle through
            time_offset: Time offset for animation
            
        Returns:
            List of background lines
        """
        lines = []
        pattern_chars = list(pattern)
        num_chars = len(pattern_chars)
        
        for y in range(height):
            line = ""
            for x in range(width):
                # Calculate pattern index based on position and time
                pattern_idx = int((x + y + time_offset * 2) / 4) % num_chars
                line += pattern_chars[pattern_idx]
            lines.append(line)
        
        return lines

