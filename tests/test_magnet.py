import base64

from ccbt.magnet import build_torrent_data_from_metadata, parse_magnet


def test_parse_magnet_hex():
    uri = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=example&tr=http://t/announce"
    mi = parse_magnet(uri)
    assert mi.info_hash == bytes.fromhex("0123456789abcdef0123456789abcdef01234567")
    assert mi.display_name == "example"
    assert mi.trackers == ["http://t/announce"]


def test_parse_magnet_base32():
    # hex -> base32
    ih = bytes.fromhex("89abcdef89abcdef89abcdef89abcdef89abcd12")
    b32 = base64.b32encode(ih).decode().lower()
    uri = f"magnet:?xt=urn:btih:{b32}"
    mi = parse_magnet(uri)
    assert mi.info_hash == ih


def test_build_torrent_data_from_metadata_single_file():
    info = {
        b"name": b"test.txt",
        b"length": 1024,
        b"piece length": 512,
        b"pieces": b"x" * 40,  # two pieces
    }
    ih = b"\x00" * 20
    td = build_torrent_data_from_metadata(ih, info)
    assert td["info_hash"] == ih
    assert td["file_info"]["type"] == "single"
    assert td["pieces_info"]["num_pieces"] == 2


def test_build_torrent_data_from_metadata_multi_file():
    info = {
        b"name": b"Dir",
        b"piece length": 512,
        b"pieces": b"x" * 40,
        b"files": [
            {b"length": 600, b"path": [b"a.txt"]},
            {b"length": 400, b"path": [b"sub", b"b.txt"]},
        ],
    }
    ih = b"\x11" * 20
    td = build_torrent_data_from_metadata(ih, info)
    assert td["info_hash"] == ih
    assert td["file_info"]["type"] == "multi"
    assert td["pieces_info"]["num_pieces"] == 2

