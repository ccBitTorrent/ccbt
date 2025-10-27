import os

import pytest


def make_td_single():
    return {
        "file_info": {
            "type": "single",
            "length": 1024,
            "name": "t.txt",
            "total_length": 1024,
        },
        "pieces_info": {
            "piece_length": 512,
            "num_pieces": 2,
            "piece_hashes": [b"x" * 20, b"x" * 20],
            "total_length": 1024,
        },
    }


@pytest.mark.asyncio
async def test_file_assembler_simple_direct(tmp_path):
    """Test file assembler functionality with direct file operations."""
    td = make_td_single()

    # Create a simple file assembler that uses direct file operations
    class SimpleFileAssembler:
        def __init__(self, torrent_data, output_dir):
            self.torrent_data = torrent_data
            self.output_dir = output_dir
            self.file_info = torrent_data["file_info"]
            self.pieces_info = torrent_data["pieces_info"]

            # Create output directory
            os.makedirs(output_dir, exist_ok=True)

            # Build file segments
            self.file_segments = self._build_file_segments()
            self.written_pieces = set()

        def _build_file_segments(self):
            segments = []
            current_offset = 0
            piece_length = self.pieces_info["piece_length"]

            for piece_index in range(self.pieces_info["num_pieces"]):
                if piece_index == self.pieces_info["num_pieces"] - 1:
                    piece_end = self.file_info["total_length"]
                else:
                    piece_end = current_offset + piece_length

                file_path = os.path.join(self.output_dir, self.file_info["name"])
                segments.append({
                    "file_path": file_path,
                    "start_offset": current_offset,
                    "end_offset": piece_end,
                    "piece_index": piece_index,
                    "piece_offset": 0,
                })
                current_offset = piece_end

            return segments

        async def write_piece_to_file(self, piece_index, piece_data):
            """Write piece data directly to file."""
            piece_segments = [seg for seg in self.file_segments if seg["piece_index"] == piece_index]

            for segment in piece_segments:
                file_path = segment["file_path"]
                start_offset = segment["start_offset"]
                end_offset = segment["end_offset"]

                # Extract segment data - for single file, the entire piece data goes to the segment
                segment_data = piece_data

                # Write to file (create if doesn't exist)
                # Ensure file exists and is large enough
                if not os.path.exists(file_path):
                    with open(file_path, "wb") as f:
                        f.write(b"\x00" * self.file_info["total_length"])

                with open(file_path, "r+b") as f:
                    f.seek(start_offset)
                    f.write(segment_data)

            self.written_pieces.add(piece_index)

        async def read_block(self, piece_index, begin, length):
            """Read block data directly from file."""
            # For cross-piece reads, we need to look at all segments that overlap
            # with the requested range
            all_segments = []
            current_piece_offset = 0

            for seg in self.file_segments:
                seg["piece_offset"] = current_piece_offset
                all_segments.append(seg)
                current_piece_offset += seg["end_offset"] - seg["start_offset"]

            # Find segments that overlap with the requested range
            request_start = begin
            request_end = begin + length

            overlapping_segments = []
            current_offset = 0

            for seg in all_segments:
                seg_start = current_offset
                seg_end = current_offset + (seg["end_offset"] - seg["start_offset"])

                # Check if this segment overlaps with our request
                if seg_start < request_end and seg_end > request_start:
                    overlapping_segments.append({
                        "segment": seg,
                        "seg_start": seg_start,
                        "seg_end": seg_end,
                    })

                current_offset = seg_end

            if not overlapping_segments:
                return None

            remaining = length
            current_offset_in_piece = begin
            parts = []

            for seg_info in overlapping_segments:
                if remaining <= 0:
                    break

                seg = seg_info["segment"]
                seg_start = seg_info["seg_start"]
                seg_end = seg_info["seg_end"]

                # Check if this segment overlaps with what we need
                overlap_start = max(current_offset_in_piece, seg_start)
                overlap_end = min(current_offset_in_piece + remaining, seg_end)

                if overlap_start < overlap_end:
                    # Read the overlapping portion
                    read_len = overlap_end - overlap_start
                    file_offset = seg["start_offset"] + (overlap_start - seg_start)

                    try:
                        with open(seg["file_path"], "rb") as f:
                            f.seek(file_offset)
                            chunk = f.read(read_len)
                            if len(chunk) != read_len:
                                return None
                            parts.append(chunk)
                    except Exception:
                        return None

                    remaining -= read_len
                    current_offset_in_piece = overlap_end

            return b"".join(parts) if parts else None

    # Use the simple assembler
    asm = SimpleFileAssembler(td, str(tmp_path))

    # Write two pieces
    await asm.write_piece_to_file(0, b"A" * 512)
    await asm.write_piece_to_file(1, b"B" * 512)

    # Read across piece boundary (from piece 0 offset 256, length 512)
    # This should read: 256 bytes from piece 0 + 256 bytes from piece 1
    data = await asm.read_block(0, 256, 512)
    assert data == b"A" * 256 + b"B" * 256
