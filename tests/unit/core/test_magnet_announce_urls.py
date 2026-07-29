"""Tests for announce URL collection and tracker merge helpers."""

from __future__ import annotations

import pytest

from ccbt.core.magnet import (
    collect_announce_urls_from_torrent_data,
    enrich_magnet_uri_with_trackers,
    merge_tracker_url_lists,
    merge_tracker_urls_into_torrent_data,
    resolve_trackers_from_sources,
)

pytestmark = pytest.mark.unit


def test_collect_announce_urls_flat_announce_list() -> None:
    """Flat announce_list entries must not be split into characters."""
    td = {
        "announce": "http://tracker.dler.org:6969/announce",
        "announce_list": [
            "http://tracker.dler.org:6969/announce",
            "http://tracker.renfei.net:8080/announce",
        ],
    }
    urls = collect_announce_urls_from_torrent_data(td)
    assert urls == [
        "http://tracker.dler.org:6969/announce",
        "http://tracker.renfei.net:8080/announce",
    ]


def test_collect_announce_urls_tiered_announce_list() -> None:
    """Tiered announce_list remains supported."""
    td = {
        "announce_list": [
            ["http://a.example/announce", "http://b.example/announce"],
            ["http://c.example/announce"],
        ],
    }
    urls = collect_announce_urls_from_torrent_data(td)
    assert urls == [
        "http://a.example/announce",
        "http://b.example/announce",
        "http://c.example/announce",
    ]


def test_merge_tracker_urls_into_existing_torrent_data() -> None:
    """Supplemental trackers merge into non-empty announce lists."""
    td = {
        "announce": "http://tracker.dler.org:6969/announce",
        "announce_list": ["http://tracker.dler.org:6969/announce"],
    }
    changed = merge_tracker_urls_into_torrent_data(
        td,
        [
            "http://tracker.dler.org:6969/announce",
            "http://tracker.renfei.net:8080/announce",
        ],
    )
    assert changed is True
    assert td["announce_list"] == [
        "http://tracker.dler.org:6969/announce",
        "http://tracker.renfei.net:8080/announce",
    ]


def test_resolve_trackers_from_checkpoint_magnet_without_tr() -> None:
    """Checkpoint announce URLs merge with magnet trackers and defaults."""
    magnet = "magnet:?xt=urn:btih:3b1244529e5b2a6ead07233738cbbef06ebebb84"
    trackers = resolve_trackers_from_sources(
        magnet_trackers=[],
        checkpoint_announce_urls=[
            "http://tracker.renfei.net:8080/announce",
            "http://tracker.dler.org:6969/announce",
        ],
        checkpoint_magnet_uri=magnet,
        supplement_defaults=False,
    )
    assert trackers == [
        "http://tracker.renfei.net:8080/announce",
        "http://tracker.dler.org:6969/announce",
    ]


def test_enrich_magnet_uri_merges_trackers_when_tr_present() -> None:
    """Existing tr= magnets gain supplemental trackers when provided."""
    base = (
        "magnet:?xt=urn:btih:3b1244529e5b2a6ead07233738cbbef06ebebb84"
        "&tr=http%3A%2F%2Ftracker.dler.org%3A6969%2Fannounce"
    )
    enriched = enrich_magnet_uri_with_trackers(
        base,
        ["http://tracker.renfei.net:8080/announce"],
    )
    assert "tracker.dler.org" in enriched
    assert "tracker.renfei.net" in enriched


def test_merge_tracker_url_lists_dedupes() -> None:
    """Duplicate tracker URLs are removed in stable order."""
    merged = merge_tracker_url_lists(
        ["http://a/announce", "udp://b:1337/announce"],
        ["http://a/announce", "https://c/announce"],
    )
    assert merged == [
        "http://a/announce",
        "udp://b:1337/announce",
        "https://c/announce",
    ]
