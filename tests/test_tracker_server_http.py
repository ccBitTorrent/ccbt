from ccbt.tracker_server_http import InMemoryTrackerStore


def test_http_tracker_compact_peers_encoding(monkeypatch):
    store = InMemoryTrackerStore()
    ih = b"\x01" * 20
    # add two peers
    store.announce(ih, "127.0.0.1", 6881, "started")
    store.announce(ih, "127.0.0.2", 6882, "")
    body = store.announce(ih, "127.0.0.1", 6881, "")
    # bencoded dict
    assert body.startswith(b"d")
