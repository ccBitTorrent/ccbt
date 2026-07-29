"""Long-only CLI options exempt from the short-alias audit.

Expert tuning flags on ``download`` / ``magnet`` share a single pool of ASCII
shorts with command-specific options; the densest tracker/socket knobs stay
long-only. Secret and ambiguous flags stay long-only by policy.
"""

from __future__ import annotations

# Normalized long option names (with leading ``--``) exempt from requiring a
# short form in ``ccbt/cli`` (see tests/unit/cli/test_cli_short_flag_audit.py).
CLI_SHORT_FLAG_EXCEPTIONS: frozenset[str] = frozenset(
    {
        # download / magnet: expert tuning (registry: docs/en/configuration.md)
        "--socket-rcvbuf-kib",
        "--socket-sndbuf-kib",
        "--listen-interface",
        "--peer-timeout",
        "--dht-timeout",
        "--min-block-size-kib",
        "--max-block-size-kib",
        "--enable-http-trackers",
        "--disable-http-trackers",
        "--enable-udp-trackers",
        "--disable-udp-trackers",
        "--tracker-announce-interval",
        "--tracker-scrape-interval",
        "--pex-interval",
        "--endgame-duplicates",
        "--streaming-mode",
        "--first-piece-priority",
        "--last-piece-priority",
        "--optimistic-unchoke-interval",
        "--unchoke-interval",
        "--peer-choked-hard-timeout-seconds",
        "--peer-choked-anchor-timeout-seconds",
        "--peer-choked-solo-grace-seconds",
        "--peer-choked-solo-grace-zero-bytes-cap-seconds",
        "--metrics-interval",
        "--prefer-v2",
        "--v2-only",
        # Secrets: avoid guessable short for passwords
        "--pass",
        # Verbose count aliases (parent already uses ``-v`` / ``-vv`` style)
        "--vv",
        "--vvv",
    },
)
