from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from ccbt.config.config import Config, ConfigManager


def apply_cli_overrides(cfg_mgr: ConfigManager, options: dict[str, Any]) -> None:
    """Apply all CLI overrides to configuration."""
    cfg = cfg_mgr.config
    _apply_network_overrides(cfg, options)
    _apply_discovery_overrides(cfg, options)
    _apply_strategy_overrides(cfg, options)
    _apply_disk_overrides(cfg, options)
    _apply_observability_overrides(cfg, options)
    _apply_limit_overrides(cfg, options)
    _apply_nat_overrides(cfg, options)
    _apply_proxy_overrides(cfg, options)
    _apply_ssl_overrides(cfg, options)
    _apply_protocol_v2_overrides(cfg, options)
    _apply_utp_overrides(cfg, options)
    _apply_xet_overrides(cfg, options)


def _apply_network_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("listen_port") is not None:
        cfg.network.listen_port = int(options["listen_port"])
    if options.get("max_peers") is not None:
        cfg.network.max_global_peers = int(options["max_peers"])
    if options.get("max_peers_per_torrent") is not None:
        cfg.network.max_peers_per_torrent = int(options["max_peers_per_torrent"])
    if options.get("pipeline_depth") is not None:
        cfg.network.pipeline_depth = int(options["pipeline_depth"])
    if options.get("block_size_kib") is not None:
        cfg.network.block_size_kib = int(options["block_size_kib"])
    if options.get("connection_timeout") is not None:
        cfg.network.connection_timeout = float(options["connection_timeout"])
    if options.get("global_down_kib") is not None:
        cfg.network.global_down_kib = int(options["global_down_kib"])
    if options.get("global_up_kib") is not None:
        cfg.network.global_up_kib = int(options["global_up_kib"])
    if options.get("connection_pool_max_connections") is not None:
        cfg.network.connection_pool_max_connections = int(
            options["connection_pool_max_connections"]
        )
    if options.get("connection_pool_warmup_enabled"):
        cfg.network.connection_pool_warmup_enabled = True
    if options.get("disable_connection_pool_warmup"):
        cfg.network.connection_pool_warmup_enabled = False
    if options.get("tracker_keepalive_timeout") is not None:
        cfg.network.tracker_keepalive_timeout = float(
            options["tracker_keepalive_timeout"]
        )
    if options.get("tracker_dns_cache_ttl") is not None:
        cfg.network.tracker_dns_cache_ttl = int(options["tracker_dns_cache_ttl"])
    if options.get("enable_tracker_dns_cache"):
        cfg.network.tracker_enable_dns_cache = True
    if options.get("disable_tracker_dns_cache"):
        cfg.network.tracker_enable_dns_cache = False
    if options.get("enable_adaptive_timeout"):
        cfg.network.timeout_adaptive = True
    if options.get("disable_adaptive_timeout"):
        cfg.network.timeout_adaptive = False
    if options.get("timeout_min_seconds") is not None:
        cfg.network.timeout_min_seconds = float(options["timeout_min_seconds"])
    if options.get("timeout_max_seconds") is not None:
        cfg.network.timeout_max_seconds = float(options["timeout_max_seconds"])
    if options.get("enable_exponential_backoff"):
        cfg.network.retry_exponential_backoff = True
    if options.get("disable_exponential_backoff"):
        cfg.network.retry_exponential_backoff = False
    if options.get("enable_circuit_breaker"):
        cfg.network.circuit_breaker_enabled = True
    if options.get("disable_circuit_breaker"):
        cfg.network.circuit_breaker_enabled = False
    if options.get("enable_adaptive_buffers"):
        cfg.network.socket_adaptive_buffers = True
    if options.get("disable_adaptive_buffers"):
        cfg.network.socket_adaptive_buffers = False
    if options.get("socket_min_buffer_kib") is not None:
        cfg.network.socket_min_buffer_kib = int(options["socket_min_buffer_kib"])
    if options.get("socket_max_buffer_kib") is not None:
        cfg.network.socket_max_buffer_kib = int(options["socket_max_buffer_kib"])
    if options.get("enable_adaptive_pipeline"):
        cfg.network.pipeline_adaptive_depth = True
    if options.get("disable_adaptive_pipeline"):
        cfg.network.pipeline_adaptive_depth = False
    if options.get("pipeline_min_depth") is not None:
        cfg.network.pipeline_min_depth = int(options["pipeline_min_depth"])
    if options.get("pipeline_max_depth") is not None:
        cfg.network.pipeline_max_depth = int(options["pipeline_max_depth"])
    if options.get("enable_pipeline_prioritization"):
        cfg.network.pipeline_enable_prioritization = True
    if options.get("disable_pipeline_prioritization"):
        cfg.network.pipeline_enable_prioritization = False
    if options.get("enable_ipv6"):
        cfg.network.enable_ipv6 = True
    if options.get("disable_ipv6"):
        cfg.network.enable_ipv6 = False
    if options.get("enable_tcp"):
        cfg.network.enable_tcp = True
    if options.get("disable_tcp"):
        cfg.network.enable_tcp = False
    if options.get("enable_utp"):
        cfg.network.enable_utp = True
    if options.get("disable_utp"):
        cfg.network.enable_utp = False
    if options.get("enable_encryption"):
        cfg.network.enable_encryption = True
    if options.get("enable_webtorrent"):
        cfg.network.webtorrent.enable_webtorrent = True
    if options.get("disable_webtorrent"):
        cfg.network.webtorrent.enable_webtorrent = False
    if options.get("webtorrent_signaling_url") is not None:
        cfg.network.webtorrent.webtorrent_signaling_url = options[
            "webtorrent_signaling_url"
        ]
    if options.get("webtorrent_port") is not None:
        cfg.network.webtorrent.webtorrent_port = int(options["webtorrent_port"])
    if options.get("webtorrent_stun_servers") is not None:
        servers = [s.strip() for s in options["webtorrent_stun_servers"].split(",")]
        cfg.network.webtorrent.webtorrent_stun_servers = servers
    if options.get("disable_encryption"):
        cfg.network.enable_encryption = False
    if options.get("tcp_nodelay"):
        cfg.network.tcp_nodelay = True
    if options.get("no_tcp_nodelay"):
        cfg.network.tcp_nodelay = False
    if options.get("socket_rcvbuf_kib") is not None:
        cfg.network.socket_rcvbuf_kib = int(options["socket_rcvbuf_kib"])
    if options.get("socket_sndbuf_kib") is not None:
        cfg.network.socket_sndbuf_kib = int(options["socket_sndbuf_kib"])
    if options.get("listen_interface") is not None:
        cfg.network.listen_interface = str(options["listen_interface"])  # type: ignore[arg-type]
    if options.get("peer_timeout") is not None:
        cfg.network.peer_timeout = float(options["peer_timeout"])  # type: ignore[attr-defined]
    if options.get("dht_timeout") is not None:
        cfg.network.dht_timeout = float(options["dht_timeout"])  # type: ignore[attr-defined]
    if options.get("min_block_size_kib") is not None:
        cfg.network.min_block_size_kib = int(options["min_block_size_kib"])  # type: ignore[attr-defined]
    if options.get("max_block_size_kib") is not None:
        cfg.network.max_block_size_kib = int(options["max_block_size_kib"])  # type: ignore[attr-defined]


def _apply_discovery_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("enable_dht"):
        cfg.discovery.enable_dht = True
    if options.get("disable_dht"):
        cfg.discovery.enable_dht = False
    if options.get("dht_port") is not None:
        cfg.discovery.dht_port = int(options["dht_port"])
    if options.get("enable_dht_ipv6"):
        cfg.discovery.dht_enable_ipv6 = True
    if options.get("disable_dht_ipv6"):
        cfg.discovery.dht_enable_ipv6 = False
    if options.get("prefer_dht_ipv6"):
        cfg.discovery.dht_prefer_ipv6 = True
    if options.get("dht_readonly"):
        cfg.discovery.dht_readonly_mode = True
    if options.get("enable_dht_multiaddress"):
        cfg.discovery.dht_enable_multiaddress = True
    if options.get("disable_dht_multiaddress"):
        cfg.discovery.dht_enable_multiaddress = False
    if options.get("enable_dht_storage"):
        cfg.discovery.dht_enable_storage = True
    if options.get("disable_dht_storage"):
        cfg.discovery.dht_enable_storage = False
    if options.get("enable_dht_indexing"):
        cfg.discovery.dht_enable_indexing = True
    if options.get("disable_dht_indexing"):
        cfg.discovery.dht_enable_indexing = False
    if options.get("enable_http_trackers"):
        cfg.discovery.enable_http_trackers = True
    if options.get("disable_http_trackers"):
        cfg.discovery.enable_http_trackers = False
    if options.get("enable_udp_trackers"):
        cfg.discovery.enable_udp_trackers = True
    if options.get("disable_udp_trackers"):
        cfg.discovery.enable_udp_trackers = False
    if options.get("tracker_announce_interval") is not None:
        cfg.discovery.tracker_announce_interval = float(
            options["tracker_announce_interval"]
        )  # type: ignore[attr-defined]
    if options.get("tracker_scrape_interval") is not None:
        cfg.discovery.tracker_scrape_interval = float(
            options["tracker_scrape_interval"]
        )  # type: ignore[attr-defined]
    if options.get("pex_interval") is not None:
        cfg.discovery.pex_interval = float(options["pex_interval"])  # type: ignore[attr-defined]


def _apply_strategy_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("piece_selection") is not None:
        cfg.strategy.piece_selection = options["piece_selection"]
    if options.get("endgame_threshold") is not None:
        cfg.strategy.endgame_threshold = float(options["endgame_threshold"])
    if options.get("endgame_duplicates") is not None:
        cfg.strategy.endgame_duplicates = int(options["endgame_duplicates"])  # type: ignore[attr-defined]
    if options.get("streaming_mode"):
        cfg.strategy.streaming_mode = True
    if options.get("sequential_window_size") is not None:
        cfg.strategy.sequential_window = int(options["sequential_window_size"])
    if options.get("sequential_priority_files"):
        cfg.strategy.sequential_priority_files = list(
            options["sequential_priority_files"]
        )
    if options.get("first_piece_priority"):
        with contextlib.suppress(Exception):
            cfg.strategy.first_piece_priority = True  # type: ignore[attr-defined]
    if options.get("last_piece_priority"):
        with contextlib.suppress(Exception):
            cfg.strategy.last_piece_priority = True  # type: ignore[attr-defined]
    if options.get("optimistic_unchoke_interval") is not None:
        cfg.network.optimistic_unchoke_interval = float(
            options["optimistic_unchoke_interval"]
        )  # type: ignore[attr-defined]
    if options.get("unchoke_interval") is not None:
        cfg.network.unchoke_interval = float(options["unchoke_interval"])  # type: ignore[attr-defined]


def _apply_disk_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("hash_workers") is not None:
        cfg.disk.hash_workers = int(options["hash_workers"])
    if options.get("disk_workers") is not None:
        cfg.disk.disk_workers = int(options["disk_workers"])
    if options.get("use_mmap"):
        cfg.disk.use_mmap = True
    if options.get("no_mmap"):
        cfg.disk.use_mmap = False
    if options.get("mmap_cache_mb") is not None:
        cfg.disk.mmap_cache_mb = int(options["mmap_cache_mb"])
    if options.get("write_batch_kib") is not None:
        cfg.disk.write_batch_kib = int(options["write_batch_kib"])
    if options.get("write_buffer_kib") is not None:
        cfg.disk.write_buffer_kib = int(options["write_buffer_kib"])
    if options.get("preallocate") is not None:
        cfg.disk.preallocate = options["preallocate"]
    if options.get("sparse_files"):
        cfg.disk.sparse_files = True
    if options.get("no_sparse_files"):
        cfg.disk.sparse_files = False
    if options.get("enable_io_uring"):
        with contextlib.suppress(Exception):
            cfg.disk.enable_io_uring = True  # type: ignore[attr-defined]
    if options.get("disable_io_uring"):
        with contextlib.suppress(Exception):
            cfg.disk.enable_io_uring = False  # type: ignore[attr-defined]
    if options.get("preserve_attributes"):
        cfg.disk.attributes.preserve_attributes = True
    if options.get("no_preserve_attributes"):
        cfg.disk.attributes.preserve_attributes = False
    if options.get("skip_padding_files"):
        cfg.disk.attributes.skip_padding_files = True
    if options.get("no_skip_padding_files"):
        cfg.disk.attributes.skip_padding_files = False
    if options.get("verify_file_sha1"):
        cfg.disk.attributes.verify_file_sha1 = True
    if options.get("no_verify_file_sha1"):
        cfg.disk.attributes.verify_file_sha1 = False


def _apply_xet_overrides(cfg: Config, options: dict[str, Any]) -> None:
    # Disk XET settings
    if options.get("enable_xet"):
        cfg.disk.xet_enabled = True
    if options.get("disable_xet"):
        cfg.disk.xet_enabled = False
    if options.get("xet_deduplication_enabled") is not None:
        cfg.disk.xet_deduplication_enabled = bool(options["xet_deduplication_enabled"])
    if options.get("xet_use_p2p_cas") is not None:
        cfg.disk.xet_use_p2p_cas = bool(options["xet_use_p2p_cas"])
    if options.get("xet_compression_enabled") is not None:
        cfg.disk.xet_compression_enabled = bool(options["xet_compression_enabled"])
    if options.get("xet_chunk_min_size") is not None:
        cfg.disk.xet_chunk_min_size = int(options["xet_chunk_min_size"])
    if options.get("xet_chunk_max_size") is not None:
        cfg.disk.xet_chunk_max_size = int(options["xet_chunk_max_size"])
    if options.get("xet_chunk_target_size") is not None:
        cfg.disk.xet_chunk_target_size = int(options["xet_chunk_target_size"])

    # XET Sync settings
    if options.get("xet_sync_enable_xet") is not None:
        cfg.xet_sync.enable_xet = bool(options["xet_sync_enable_xet"])
    if options.get("xet_sync_check_interval") is not None:
        cfg.xet_sync.check_interval = float(options["xet_sync_check_interval"])
    if options.get("xet_sync_default_sync_mode") is not None:
        cfg.xet_sync.default_sync_mode = str(options["xet_sync_default_sync_mode"])
    if options.get("xet_sync_enable_git_versioning") is not None:
        cfg.xet_sync.enable_git_versioning = bool(options["xet_sync_enable_git_versioning"])
    if options.get("xet_sync_enable_lpd") is not None:
        cfg.xet_sync.enable_lpd = bool(options["xet_sync_enable_lpd"])
    if options.get("xet_sync_enable_gossip") is not None:
        cfg.xet_sync.enable_gossip = bool(options["xet_sync_enable_gossip"])
    if options.get("xet_sync_gossip_fanout") is not None:
        cfg.xet_sync.gossip_fanout = int(options["xet_sync_gossip_fanout"])
    if options.get("xet_sync_gossip_interval") is not None:
        cfg.xet_sync.gossip_interval = float(options["xet_sync_gossip_interval"])
    if options.get("xet_sync_flooding_ttl") is not None:
        cfg.xet_sync.flooding_ttl = int(options["xet_sync_flooding_ttl"])
    if options.get("xet_sync_flooding_priority_threshold") is not None:
        cfg.xet_sync.flooding_priority_threshold = int(options["xet_sync_flooding_priority_threshold"])
    if options.get("xet_sync_consensus_algorithm") is not None:
        cfg.xet_sync.consensus_algorithm = str(options["xet_sync_consensus_algorithm"])
    if options.get("xet_sync_raft_election_timeout") is not None:
        cfg.xet_sync.raft_election_timeout = float(options["xet_sync_raft_election_timeout"])
    if options.get("xet_sync_raft_heartbeat_interval") is not None:
        cfg.xet_sync.raft_heartbeat_interval = float(options["xet_sync_raft_heartbeat_interval"])
    if options.get("xet_sync_enable_byzantine_fault_tolerance") is not None:
        cfg.xet_sync.enable_byzantine_fault_tolerance = bool(options["xet_sync_enable_byzantine_fault_tolerance"])
    if options.get("xet_sync_byzantine_fault_threshold") is not None:
        cfg.xet_sync.byzantine_fault_threshold = float(options["xet_sync_byzantine_fault_threshold"])
    if options.get("xet_sync_weighted_voting") is not None:
        cfg.xet_sync.weighted_voting = bool(options["xet_sync_weighted_voting"])
    if options.get("xet_sync_auto_elect_source") is not None:
        cfg.xet_sync.auto_elect_source = bool(options["xet_sync_auto_elect_source"])
    if options.get("xet_sync_source_election_interval") is not None:
        cfg.xet_sync.source_election_interval = float(options["xet_sync_source_election_interval"])
    if options.get("xet_sync_conflict_resolution_strategy") is not None:
        cfg.xet_sync.conflict_resolution_strategy = str(options["xet_sync_conflict_resolution_strategy"])
    if options.get("xet_sync_git_auto_commit") is not None:
        cfg.xet_sync.git_auto_commit = bool(options["xet_sync_git_auto_commit"])
    if options.get("xet_sync_consensus_threshold") is not None:
        cfg.xet_sync.consensus_threshold = float(options["xet_sync_consensus_threshold"])
    if options.get("xet_sync_max_update_queue_size") is not None:
        cfg.xet_sync.max_update_queue_size = int(options["xet_sync_max_update_queue_size"])
    if options.get("xet_sync_allowlist_encryption_key") is not None:
        cfg.xet_sync.allowlist_encryption_key = str(options["xet_sync_allowlist_encryption_key"]) if options["xet_sync_allowlist_encryption_key"] else None

    # Network XET settings
    if options.get("xet_port") is not None:
        cfg.network.xet_port = int(options["xet_port"]) if options["xet_port"] else None
    if options.get("xet_multicast_address") is not None:
        cfg.network.xet_multicast_address = str(options["xet_multicast_address"])
    if options.get("xet_multicast_port") is not None:
        cfg.network.xet_multicast_port = int(options["xet_multicast_port"])

    # Discovery XET settings
    if options.get("xet_chunk_query_batch_size") is not None:
        cfg.discovery.xet_chunk_query_batch_size = int(options["xet_chunk_query_batch_size"])
    if options.get("xet_chunk_query_max_concurrent") is not None:
        cfg.discovery.xet_chunk_query_max_concurrent = int(options["xet_chunk_query_max_concurrent"])
    if options.get("discovery_cache_ttl") is not None:
        cfg.discovery.discovery_cache_ttl = float(options["discovery_cache_ttl"])


def _apply_observability_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("log_level") is not None:
        cfg.observability.log_level = options["log_level"]
    if options.get("enable_metrics"):
        cfg.observability.enable_metrics = True
    if options.get("disable_metrics"):
        cfg.observability.enable_metrics = False
    if options.get("metrics_port") is not None:
        cfg.observability.metrics_port = int(options["metrics_port"])
    if options.get("metrics_interval") is not None:
        cfg.observability.metrics_interval = float(options["metrics_interval"])  # type: ignore[attr-defined]
    if options.get("structured_logging"):
        cfg.observability.structured_logging = True  # type: ignore[attr-defined]
    if options.get("log_correlation_id"):
        cfg.observability.log_correlation_id = True  # type: ignore[attr-defined]


def _apply_limit_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("download_limit") is not None:
        cfg.network.global_down_kib = int(options["download_limit"])
    if options.get("upload_limit") is not None:
        cfg.network.global_up_kib = int(options["upload_limit"])


def _apply_nat_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("enable_nat_pmp"):
        cfg.nat.enable_nat_pmp = True
    if options.get("disable_nat_pmp"):
        cfg.nat.enable_nat_pmp = False
    if options.get("enable_upnp"):
        cfg.nat.enable_upnp = True
    if options.get("disable_upnp"):
        cfg.nat.enable_upnp = False
    if options.get("auto_map_ports") is not None:
        cfg.nat.auto_map_ports = bool(options["auto_map_ports"])


def _apply_proxy_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("proxy"):
        proxy_parts = options["proxy"].split(":")
        if len(proxy_parts) == 2:
            cfg.proxy.enable_proxy = True
            cfg.proxy.proxy_host = proxy_parts[0]
            cfg.proxy.proxy_port = int(proxy_parts[1])
    if options.get("proxy_user"):
        cfg.proxy.proxy_username = options["proxy_user"]
        cfg.proxy.enable_proxy = True
    if options.get("proxy_pass"):
        cfg.proxy.proxy_password = options["proxy_pass"]
        cfg.proxy.enable_proxy = True
    if options.get("proxy_type"):
        cfg.proxy.proxy_type = options["proxy_type"]
        cfg.proxy.enable_proxy = True


def _apply_ssl_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("enable_ssl_trackers"):
        cfg.security.ssl.enable_ssl_trackers = True
    if options.get("disable_ssl_trackers"):
        cfg.security.ssl.enable_ssl_trackers = False
    if options.get("enable_ssl_peers"):
        cfg.security.ssl.enable_ssl_peers = True
    if options.get("disable_ssl_peers"):
        cfg.security.ssl.enable_ssl_peers = False
    if options.get("ssl_ca_certs"):
        ca_path = Path(options["ssl_ca_certs"]).expanduser()
        if ca_path.exists():
            cfg.security.ssl.ssl_ca_certificates = str(ca_path)
    if options.get("ssl_client_cert"):
        cert_path = Path(options["ssl_client_cert"]).expanduser()
        if cert_path.exists():
            cfg.security.ssl.ssl_client_certificate = str(cert_path)
    if options.get("ssl_client_key"):
        key_path = Path(options["ssl_client_key"]).expanduser()
        if key_path.exists():
            cfg.security.ssl.ssl_client_key = str(key_path)
    if options.get("no_ssl_verify"):
        cfg.security.ssl.ssl_verify_certificates = False
    if options.get("ssl_protocol_version"):
        cfg.security.ssl.ssl_protocol_version = options["ssl_protocol_version"]


def _apply_utp_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("utp_prefer_over_tcp") is not None:
        cfg.network.utp.prefer_over_tcp = bool(options["utp_prefer_over_tcp"])
    if options.get("utp_connection_timeout") is not None:
        cfg.network.utp.connection_timeout = float(options["utp_connection_timeout"])
    if options.get("utp_max_window_size") is not None:
        cfg.network.utp.max_window_size = int(options["utp_max_window_size"])
    if options.get("utp_mtu") is not None:
        cfg.network.utp.mtu = int(options["utp_mtu"])
    if options.get("utp_initial_rate") is not None:
        cfg.network.utp.initial_rate = int(options["utp_initial_rate"])
    if options.get("utp_min_rate") is not None:
        cfg.network.utp.min_rate = int(options["utp_min_rate"])
    if options.get("utp_max_rate") is not None:
        cfg.network.utp.max_rate = int(options["utp_max_rate"])
    if options.get("utp_ack_interval") is not None:
        cfg.network.utp.ack_interval = float(options["utp_ack_interval"])
    if options.get("utp_retransmit_timeout_factor") is not None:
        cfg.network.utp.retransmit_timeout_factor = float(
            options["utp_retransmit_timeout_factor"]
        )
    if options.get("utp_max_retransmits") is not None:
        cfg.network.utp.max_retransmits = int(options["utp_max_retransmits"])


def _apply_protocol_v2_overrides(cfg: Config, options: dict[str, Any]) -> None:
    if options.get("v2_only"):
        cfg.network.protocol_v2.enable_protocol_v2 = True
        cfg.network.protocol_v2.prefer_protocol_v2 = True
        cfg.network.protocol_v2.support_hybrid = False
    if not options.get("v2_only"):
        if options.get("enable_v2"):
            cfg.network.protocol_v2.enable_protocol_v2 = True
        if options.get("disable_v2"):
            cfg.network.protocol_v2.enable_protocol_v2 = False
        if options.get("prefer_v2"):
            cfg.network.protocol_v2.prefer_protocol_v2 = True
