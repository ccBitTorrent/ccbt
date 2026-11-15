"""Content-defined chunking using Gearhash algorithm for Xet protocol.

This module implements the Gearhash-based CDC (Content-Defined Chunking) algorithm
as specified in the Xet protocol. It chunks data into variable-sized blocks
based on content patterns rather than fixed positions, enabling efficient
deduplication across different files and torrents.

Based on reference implementations:
- xet-core (Rust): https://github.com/huggingface/xet-core
- zig-xet (Zig): https://github.com/jedisct1/huggingface-xet
"""

from __future__ import annotations

import logging
from typing import Iterator

logger = logging.getLogger(__name__)

# Gearhash CDC constants (upstream Xet suite XET-BLAKE3-GEARHASH-LZ4).
# See docs/en/xet-native-spec.md and draft-denis-xet-05 Appendix B.
MIN_CHUNK_SIZE = 8192  # 8 KB - minimum chunk size (target / 8)
MAX_CHUNK_SIZE = 131072  # 128 KB - maximum chunk size (target * 2)
TARGET_CHUNK_SIZE = 65536  # 64 KB - target chunk size
MASK = 0xFFFF000000000000  # Boundary mask for the 64 KiB target
_UINT64_MASK = 0xFFFFFFFFFFFFFFFF


class GearhashChunker:
    """Content-defined chunking using Gearhash algorithm.

    The Gearhash algorithm uses a rolling hash with a precomputed gear table
    to find content-defined chunk boundaries. This ensures that similar content
    in different files will produce the same chunk boundaries, enabling
    cross-file deduplication.

    Attributes:
        target_size: Target average chunk size (default: 16 KB)
        gear_table: Precomputed 256-element gear table for rolling hash

    """

    def __init__(self, target_size: int = TARGET_CHUNK_SIZE):
        """Initialize chunker with target chunk size.

        Args:
            target_size: Target chunk size; must be a power of two.
                The upstream suite uses 65536 (64 KiB). Other values
                produce a different, non-interoperable namespace and
                are rejected at the configuration layer.

        """
        if target_size <= 64 or target_size & (target_size - 1):
            msg = "Target size must be a power of two greater than 64"
            raise ValueError(msg)
        self.target_size = target_size
        self.minimum_chunk = target_size // 8
        self.maximum_chunk = target_size * 2
        mask = target_size - 1
        # Shift the mask all the way left (upstream chunking.rs).
        self.mask = (mask << (64 - mask.bit_length())) & _UINT64_MASK if mask else 0
        self.gear_table = self._init_gear_table()
        self._hash = 0
        self._buffer = bytearray()

    def _init_gear_table(self) -> list[int]:
        """Initialize precomputed gear table for rolling hash.

        The gear table is a 256-element array of 32-bit integers used
        in the rolling hash computation. Values are chosen to provide
        good distribution properties for boundary detection.

        Returns:
            256-element list of 32-bit integers

        """
        # Gear table values based on reference implementations
        # These values provide good hash distribution for boundary detection
        gear_table = [
            0xB088D3A9E840F559,
            0x5652C7F739ED20D6,
            0x45B28969898972AB,
            0x6B0A89D5B68EC777,
            0x368F573E8B7A31B7,
            0x1DC636DCE936D94B,
            0x207A4C4E5554D5B6,
            0xA474B34628239ACB,
            0x3B06A83E1CA3B912,
            0x90E78D6C2F02BAF7,
            0xE1C92DF7150D9A8A,
            0x8E95053A1086D3AD,
            0x5A2EF4F1B83A0722,
            0xA50FAC949F807FAE,
            0x0E7303EB80D8D681,
            0x99B07EDC1570AD0F,
            0x689D2FB555FD3076,
            0x00005082119EA468,
            0xC4B08306A88FCC28,
            0x3EB0678AF6374AFD,
            0xF19F87AB86AD7436,
            0xF2129FBFBE6BC736,
            0x481149575C98A4ED,
            0x0000010695477BC5,
            0x1FBA37801A9CEACC,
            0x3BF06FD663A49B6D,
            0x99687E9782E3874B,
            0x79A10673AA50D8E3,
            0xE4ACCF9E6211F420,
            0x2520E71F87579071,
            0x2BD5D3FD781A8A9B,
            0x00DE4DCDDD11C873,
            0xEAA9311C5A87392F,
            0xDB748EB617BC40FF,
            0xAF579A8DF620BF6F,
            0x86A6E5DA1B09C2B1,
            0xCC2FC30AC322A12E,
            0x355E2AFEC1F74267,
            0x2D99C8F4C021A47B,
            0xBADE4B4A9404CFC3,
            0xF7B518721D707D69,
            0x3286B6587BF32C20,
            0x0000B68886AF270C,
            0xA115D6E4DB8A9079,
            0x484F7E9C97B2E199,
            0xCCCA7BB75713E301,
            0xBF2584A62BB0F160,
            0xADE7E813625DBCC8,
            0x000070940D87955A,
            0x8AE69108139E626F,
            0xBD776AD72FDE38A2,
            0xFB6B001FC2FCC0CF,
            0xC7A474B8E67BC427,
            0xBAF6F11610EB5D58,
            0x09CB1F5B6DE770D1,
            0xB0B219E6977D4C47,
            0x00CCBC386EA7AD4A,
            0xCC849D0ADF973F01,
            0x73A3EF7D016AF770,
            0xC807D2D386BDBDFE,
            0x7F2AC9966C791730,
            0xD037A86BC6C504DA,
            0xF3F17C661EAA609D,
            0xACA626B04DAAE687,
            0x755A99374F4A5B07,
            0x90837EE65B2CAEDE,
            0x6EE8AD93FD560785,
            0x0000D9E11053EDD8,
            0x9E063BB2D21CDBD7,
            0x07AB77F12A01D2B2,
            0xEC550255E6641B44,
            0x78FB94A8449C14C6,
            0xC7510E1BC6C0F5F5,
            0x0000320B36E4CAE3,
            0x827C33262C8B1A2D,
            0x14675F0B48EA4144,
            0x267BD3A6498DECEB,
            0xF1916FF982F5035E,
            0x86221B7FF434FB88,
            0x9DBECEE7386F49D8,
            0xEA58F8CAC80F8F4A,
            0x008D198692FC64D8,
            0x6D38704FBABF9A36,
            0xE032CB07D1E7BE4C,
            0x228D21F6AD450890,
            0x635CB1BFC02589A5,
            0x4620A1739CA2CE71,
            0xA7E7DFE3AAE5FB58,
            0x0C10CA932B3C0DEB,
            0x2727FEE884AFED7B,
            0xA2DF1C6DF9E2AB1F,
            0x4DCDD1AC0774F523,
            0x000070FFAD33E24E,
            0xA2ACE87BC5977816,
            0x9892275AB4286049,
            0xC2861181DDF18959,
            0xBB9972A042483E19,
            0xEF70CD3766513078,
            0x00000513ABFC9864,
            0xC058B61858C94083,
            0x09E850859725E0DE,
            0x9197FB3BF83E7D94,
            0x7E1E626D12B64BCE,
            0x520C54507F7B57D1,
            0xBEE1797174E22416,
            0x6FD9AC3222E95587,
            0x0023957C9ADFBF3E,
            0xA01C7D7E234BBE15,
            0xABA2C758B8A38CBB,
            0x0D1FA0CEEC3E2B30,
            0x0BB6A58B7E60B991,
            0x4333DD5B9FA26635,
            0xC2FD3B7D4001C1A3,
            0xFB41802454731127,
            0x65A56185A50D18CB,
            0xF67A02BD8784B54F,
            0x696F11DD67E65063,
            0x00002022FCA814AB,
            0x8CD6BE912DB9D852,
            0x695189B6E9AE8A57,
            0xEE9453B50ADA0C28,
            0xD8FC5EA91A78845E,
            0xAB86BF191A4AA767,
            0x0000C6B5C86415E5,
            0x267310178E08A22E,
            0xED2D101B078BCA25,
            0x3B41ED84B226A8FB,
            0x13E622120F28DC06,
            0xA315F5EBFB706D26,
            0x8816C34E3301BACE,
            0xE9395B9CBB71FDAE,
            0x002CE9202E721648,
            0x4283DB1D2BB3C91C,
            0xD77D461AD2B1A6A5,
            0xE2EC17E46EEB866B,
            0xB8E0BE4039FBC47C,
            0xDEA160C4D5299D04,
            0x7EEC86C8D28C3634,
            0x2119AD129F98A399,
            0xA6CCF46B61A283EF,
            0x2C52CEDEF658C617,
            0x2DB4871169ACDD83,
            0x0000F0D6F39ECBE9,
            0x3DD5D8C98D2F9489,
            0x8A1872A22B01F584,
            0xF282A4C40E7B3CF2,
            0x8020EC2CCB1BA196,
            0x6693B6E09E59E313,
            0x0000CE19CC7C83EB,
            0x20CB5735F6479C3B,
            0x762EBF3759D75A5B,
            0x207BFE823D693975,
            0xD77DC112339CD9D5,
            0x9BA7834284627D03,
            0x217DC513E95F51E9,
            0xB27B1A29FC5E7816,
            0x00D5CD9831BB662D,
            0x71E39B806D75734C,
            0x7E572AF006FB1A23,
            0xA2734F2F6AE91F85,
            0xBF82C6B5022CDDF2,
            0x5C3BEAC60761A0DE,
            0xCDC893BB47416998,
            0x6D1085615C187E01,
            0x77F8AE30AC277C5D,
            0x917C6B81122A2C91,
            0x5B75B699ADD16967,
            0x0000CF6AE79A069B,
            0xF3C40AFA60DE1104,
            0x2063127AA59167C3,
            0x621DE62269D1894D,
            0xD188AC1DE62B4726,
            0x107036E2154B673C,
            0x0000B85F28553A1D,
            0xF2EF4E4C18236F3D,
            0xD9D6DE6611B9F602,
            0xA1FC7955FB47911C,
            0xEB85FD032F298DBD,
            0xBE27502FB3BEFAE1,
            0xE3034251C4CD661E,
            0x441364D354071836,
            0x0082B36C75F2983E,
            0xB145910316FA66F0,
            0x021C069C9847CAF7,
            0x2910DFC75A4B5221,
            0x735B353E1C57A8B5,
            0xCE44312CE98ED96C,
            0xBC942E4506BDFA65,
            0xF05086A71257941B,
            0xFEC3B215D351CEAD,
            0x00AE1055E0144202,
            0xF54B40846F42E454,
            0x00007FD9C8BCBCC8,
            0xBFBD9EF317DE9BFE,
            0xA804302FF2854E12,
            0x39CE4957A5E5D8D4,
            0xFFB9E2A45637BA84,
            0x55B9AD1D9EA0818B,
            0x00008ACBF319178A,
            0x48E2BFC8D0FBFB38,
            0x8BE39841E848B5E8,
            0x0E2712160696A08B,
            0xD51096E84B44242A,
            0x1101BA176792E13A,
            0xC22E770F4531689D,
            0x1689EFF272BBC56C,
            0x00A92A197F5650EC,
            0xBC765990BDA1784E,
            0xC61441E392FCB8AE,
            0x07E13A2CED31E4A0,
            0x92CBE984234E9D4D,
            0x8F4FF572BB7D8AC5,
            0x0B9670C00B963BD0,
            0x62955A581A03EB01,
            0x645F83E5EA000254,
            0x41FCE516CD88F299,
            0xBBDA9748DA7A98CF,
            0x0000AAB2FE4845FA,
            0x19761B069BF56555,
            0x8B8F5E8343B6AD56,
            0x3E5D1CFD144821D9,
            0xEC5C1E2CA2B0CD8F,
            0xFAF7E0FEA7FBB57F,
            0x000000D3BA12961B,
            0xDA3F90178401B18E,
            0x70FF906DE33A5FEB,
            0x0527D5A7C06970E7,
            0x22D8E773607C13E9,
            0xC9AB70DF643C3BAC,
            0xEDA4C6DC8ABE12E3,
            0xECEF1F410033E78A,
            0x0024C2B274AC72CB,
            0x06740D954FA900B4,
            0x1D7A299B323D6304,
            0xB3C37CB298CBEAD5,
            0xC986E3C76178739B,
            0x9FABEA364B46F58A,
            0x6DA214C5AF85CC56,
            0x17A43ED8B7A38F84,
            0x6ECCEC511D9ADBEB,
            0xF9CAB30913335AFB,
            0x4A5E60C5F415EED2,
            0x00006967503672B4,
            0x9DA51D121454BB87,
            0x84321E13B9BBC816,
            0xFB3D6FB6AB2FDD8D,
            0x60305EED8E160A8D,
            0xCBBF4B14E9946CE8,
            0x00004F63381B10C3,
            0x07D5B7816FCC4E10,
            0xE5A536726A6A8155,
            0x57AFB23447A07FDD,
            0x18F346F7ABC9D394,
            0x636DC655D61AD33D,
            0xCC8BAB4939F7F3F6,
            0x63C7A906C1DD187B,
        ]

        # If table is shorter than 256, pad with values
        while (
            len(gear_table) < 256
        ):  # pragma: no cover - Gear table padding logic, unlikely to trigger with current initialization
            gear_table.extend(
                gear_table[: 256 - len(gear_table)]
            )  # pragma: no cover - Same context

        return gear_table[:256]

    def reset(self) -> None:
        """Reset streaming state."""
        self._hash = 0
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        """Feed data and return any completed chunks (streaming API)."""
        chunks: list[bytes] = []
        table = self.gear_table
        mask = self.mask
        minimum = self.minimum_chunk
        maximum = self.maximum_chunk
        h = self._hash
        buf = self._buffer
        for b in data:
            buf.append(b)
            h = ((h << 1) + table[b]) & _UINT64_MASK
            size = len(buf)
            if size >= minimum and (size >= maximum or (h & mask) == 0):
                chunks.append(bytes(buf))
                buf = bytearray()
                h = 0
        self._hash = h
        self._buffer = buf
        return chunks

    def finalize(self) -> list[bytes]:
        """Flush the final partial chunk, if any."""
        if not self._buffer:
            return []
        chunk = bytes(self._buffer)
        self.reset()
        return [chunk]

    def chunk_buffer(self, data: bytes) -> list[bytes]:
        """Chunk data using Gearhash CDC (upstream scalar algorithm)."""
        self.reset()
        chunks = self.feed(data)
        chunks.extend(self.finalize())
        return chunks

    def _find_chunk_boundary(
        self,
        data: bytes,
        start_pos: int,
        _min_mask: int = 0,
        _max_mask: int = 0,
        _target_mask: int = 0,
    ) -> int:
        """Return the end offset of the first chunk in data[start_pos:].

        Kept for internal callers; implemented on the canonical
        per-byte Gearhash state machine so results always match
        chunk_buffer.
        """
        table = self.gear_table
        h = 0
        for size, pos in enumerate(range(start_pos, len(data)), start=1):
            h = ((h << 1) + table[data[pos]]) & _UINT64_MASK
            if size >= self.minimum_chunk and (
                size >= self.maximum_chunk or (h & self.mask) == 0
            ):
                return pos + 1
        return len(data)

    def chunk_file(
        self, file_path: str, chunk_size_hint: int = 1024 * 1024
    ) -> Iterator[bytes]:
        """Chunk a file incrementally; identical boundaries to chunk_buffer."""
        self.reset()
        with open(file_path, "rb") as f:
            while True:
                block = f.read(chunk_size_hint)
                if not block:
                    break
                yield from self.feed(block)
        yield from self.finalize()

    def chunk_stream(self, stream: Iterator[bytes]) -> Iterator[bytes]:
        """Chunk a stream; identical boundaries to chunk_buffer."""
        self.reset()
        for block in stream:
            yield from self.feed(block)
        yield from self.finalize()
