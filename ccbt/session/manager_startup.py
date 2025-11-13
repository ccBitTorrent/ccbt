from __future__ import annotations

import asyncio
import socket
import time
from typing import Any


def log_network_configuration(manager: Any) -> None:
    """Log basic network configuration and detected local addresses."""
    logger = manager.logger
    config = manager.config
    try:
        _hostname = socket.gethostname()
        local_ipv4 = None
        local_ipv6 = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ipv4 = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s.connect(("2001:4860:4860::8888", 80))
            local_ipv6 = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        logger.info(
            "Network configuration: listen_interface=%s, listen_port=%d, dht_port=%d, enable_ipv6=%s",
            config.network.listen_interface or "0.0.0.0",
            config.network.listen_port,
            config.discovery.dht_port,
            config.network.enable_ipv6,
        )

        # CRITICAL FIX: Validate configured ports are valid
        if config.network.listen_port <= 0 or config.network.listen_port > 65535:
            logger.error(
                "Invalid configured listen_port %d (must be 1-65535). "
                "Port binding and NAT mapping may fail.",
                config.network.listen_port,
            )
        if config.discovery.dht_port <= 0 or config.discovery.dht_port > 65535:
            logger.error(
                "Invalid configured dht_port %d (must be 1-65535). "
                "DHT may not work properly.",
                config.discovery.dht_port,
            )
        if local_ipv4:
            logger.info("Detected local IPv4 address: %s", local_ipv4)
        if local_ipv6:
            logger.info("Detected local IPv6 address: %s", local_ipv6)
        if not local_ipv4 and not local_ipv6:
            logger.warning(
                "Could not detect local IP addresses - network connectivity may be limited"
            )
        elif local_ipv6 and not local_ipv4:
            logger.warning(
                "Only IPv6 detected. Many BitTorrent trackers/peers use IPv4. "
                "Consider enabling IPv4 or configuring dual-stack networking."
            )
    except Exception as e:
        logger.debug("Error detecting network configuration: %s", e)


async def start_security_manager(manager: Any) -> Any | None:
    """Initialize and return security manager."""
    logger = manager.logger
    start = time.time()
    logger.info("Initializing security manager...")
    try:
        sec = manager._make_security_manager()
        if sec:
            await sec.load_ip_filter(manager.config)
        logger.info(
            "Security manager initialized successfully (took %.2fs)",
            time.time() - start,
        )
        manager.security_manager = sec
        return sec
    except Exception:
        logger.exception(
            "Failed to initialize security manager (took %.2fs)", time.time() - start
        )
        manager.security_manager = None
        return None


async def start_dht(manager: Any) -> Any | None:
    """Create DHT client and start bootstrap.

    CRITICAL: Waits for NAT port mapping to complete before starting DHT bootstrap
    to ensure DHT can receive incoming connections through NAT.
    """
    logger = manager.logger
    config = manager.config
    if not config.discovery.enable_dht:
        return None
    start = time.time()
    logger.info("Initializing DHT client...")

    # CRITICAL FIX: Wait for NAT port mapping to complete before starting DHT
    # This ensures DHT UDP port is mapped and can receive incoming connections
    if manager.nat_manager and config.nat.auto_map_ports:
        logger.info("Waiting for NAT port mapping to complete before starting DHT...")
        mapping_ready = await manager.nat_manager.wait_for_mapping(timeout=60.0)
        if mapping_ready:
            # Validate that DHT UDP port mapping exists specifically
            dht_port = config.discovery.dht_port
            try:
                external_port = await manager.nat_manager.get_external_port(
                    dht_port, "udp"
                )
                if external_port is not None:
                    logger.info(
                        "NAT port mapping confirmed (DHT UDP: %d -> %d), starting DHT client",
                        dht_port,
                        external_port,
                    )
                else:
                    logger.warning(
                        "NAT port mapping exists but DHT UDP port %d mapping not found. "
                        "DHT will start anyway, but incoming DHT connections may fail.",
                        dht_port,
                    )
            except Exception as e:
                logger.debug(
                    "Failed to validate DHT UDP port mapping: %s", e, exc_info=True
                )
                logger.info(
                    "NAT port mapping confirmed, starting DHT client (validation skipped)"
                )
        else:
            logger.warning(
                "NAT port mapping not confirmed after 60s timeout. "
                "DHT will start anyway, but incoming DHT connections may fail. "
                "This may indicate NAT-PMP/UPnP is disabled on your router or the router is slow to respond."
            )

    bind_ip = config.network.listen_interface or "0.0.0.0"  # nosec - required for DHT reachability
    if bind_ip == "127.0.0.1":
        logger.warning(
            "DHT is binding to 127.0.0.1 (localhost). This will prevent DHT from receiving "
            "responses from external nodes. Consider setting listen_interface to 0.0.0.0 "
            "or your public IP address for DHT to work properly."
        )

    # CRITICAL FIX: Check port availability before starting DHT client
    dht_port = config.discovery.dht_port
    from ccbt.utils.port_checker import is_port_available

    port_available, port_error = is_port_available(bind_ip or "0.0.0.0", dht_port, "udp")
    if not port_available:
        from ccbt.utils.port_checker import (
            get_permission_error_resolution,
            get_port_conflict_resolution,
        )

        # CRITICAL FIX: Distinguish between permission errors and port conflicts
        # Check for permission denied in multiple ways (error code 10013 on Windows, 13 on Unix)
        is_permission_error = (
            port_error
            and (
                "Permission denied" in port_error
                or "10013" in str(port_error)
                or "WSAEACCES" in str(port_error)
                or "EACCES" in str(port_error)
                or "forbidden" in str(port_error).lower()
            )
        )
        if is_permission_error:
            resolution = get_permission_error_resolution(dht_port, "udp")
            error_msg = (
                f"DHT UDP port {dht_port} cannot be bound.\n"
                f"{port_error}\n\n"
                f"{resolution}"
            )
        else:
            resolution = get_port_conflict_resolution(dht_port, "udp")
            error_msg = (
                f"DHT UDP port {dht_port} is not available.\n"
                f"{port_error}\n\n"
                f"Port {dht_port} (UDP) may be already in use.\n"
                f"{resolution}"
            )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        dht_client = manager._make_dht_client(
            bind_ip=bind_ip, bind_port=config.discovery.dht_port
        )
        if not dht_client:
            logger.error("Failed to create DHT client (factory returned None)")
            manager.dht_client = None
            return None

        logger.info(
            "DHT client created (took %.2fs), starting bootstrap...",
            time.time() - start,
        )

        # CRITICAL FIX: Start DHT synchronously (not in background task) to ensure
        # bootstrap completes before other services try to use DHT
        boot_start = time.time()
        try:
            logger.info("Starting DHT client bootstrap...")
            await dht_client.start()
            logger.info(
                "DHT client started and bootstrapped (took %.2fs, routing table: %d nodes)",
                time.time() - boot_start,
                len(dht_client.routing_table.nodes),
            )
        except Exception as e:
            logger.warning(
                "Failed to start DHT client (took %.2fs): %s",
                time.time() - boot_start,
                e,
                exc_info=True,
            )
            manager.dht_client = None
            return None

        manager.dht_client = dht_client
        return dht_client
    except Exception:
        logger.exception(
            "Failed to create DHT client (took %.2fs)", time.time() - start
        )
        manager.dht_client = None
        return None


async def start_peer_service(manager: Any) -> None:
    """Start peer service if available."""
    logger = manager.logger
    start = time.time()
    logger.info("Starting peer service...")
    try:
        if manager.peer_service:
            await manager.peer_service.start()
            logger.info(
                "Peer service started successfully (took %.2fs)", time.time() - start
            )
        else:
            logger.debug("Peer service not available (took %.2fs)", time.time() - start)
    except Exception as e:
        logger.warning(
            "Peer service start failed (took %.2fs): %s",
            time.time() - start,
            e,
            exc_info=True,
        )


async def start_background_tasks(manager: Any) -> None:
    """Create session manager background tasks."""
    manager._cleanup_task = asyncio.create_task(manager._cleanup_loop())
    manager._metrics_task = asyncio.create_task(manager._metrics_loop())
    if manager.config.discovery.tracker_auto_scrape:
        manager.scrape_task = asyncio.create_task(manager._periodic_scrape_loop())


async def start_queue_manager(manager: Any) -> None:
    """Start queue manager if enabled."""
    if manager.config.queue.auto_manage_queue:
        from ccbt.queue.manager import TorrentQueueManager

        manager.queue_manager = TorrentQueueManager(manager, manager.config.queue)
        await manager.queue_manager.start()


async def start_nat(manager: Any) -> None:
    """Start NAT manager, discover UPnP/NAT-PMP, and map ports if enabled.

    CRITICAL: UPnP/NAT-PMP discovery happens FIRST and must complete before
    port mapping and other services start. This ensures the NAT device is
    properly configured before we attempt to use it.
    """
    config = manager.config
    logger = manager.logger
    if not config.nat.auto_map_ports:
        return
    try:
        logger.info("Starting NAT manager for port mapping...")
        start_time = time.time()

        # Step 1: Create NAT manager
        manager.nat_manager = manager._make_nat_manager()

        # Step 2: Start NAT manager (this does UPnP/NAT-PMP discovery internally)
        # CRITICAL: UPnP discovery happens here and MUST complete before proceeding
        logger.info(
            "Starting NAT manager (UPnP/NAT-PMP discovery will happen first)..."
        )
        await manager.nat_manager.start()

        # Step 3: Verify discovery completed and log results
        discovery_duration = time.time() - start_time
        discovered = manager.nat_manager.active_protocol is not None

        if discovered:
            logger.info(
                "NAT device discovered via %s (took %.2fs)",
                manager.nat_manager.active_protocol,
                discovery_duration,
            )
        else:
            logger.warning(
                "No NAT device discovered after %.2fs. Port mapping may not work. "
                "Ensure UPnP or NAT-PMP is enabled on your router. "
                "Downloads will continue but incoming connections may fail.",
                discovery_duration,
            )

        # Step 4: Only map ports if discovery was successful
        # (map_listen_ports will handle the case where discovery failed gracefully)
        mapping_start = time.time()
        await manager.nat_manager.map_listen_ports()
        mapping_duration = time.time() - mapping_start
        logger.info("NAT port mapping completed in %.2fs", mapping_duration)

        mappings = await manager.nat_manager.port_mapping_manager.get_all_mappings()
        mapped_ports: list[str] = []
        for m in mappings:
            port_info = f"{m.protocol.upper()}:{m.external_port}"
            if m.internal_port != m.external_port:
                port_info += f" (internal:{m.internal_port})"
            mapped_ports.append(port_info)
        if mapped_ports:
            logger.info(
                "NAT port mapping initialized successfully: %s (protocol: %s)",
                ", ".join(mapped_ports),
                manager.nat_manager.active_protocol or "unknown",
            )
        else:
            logger.warning(
                "NAT port mapping initialized but no ports mapped. "
                "This may prevent incoming peer connections and tracker responses. "
                "Check UPnP/NAT-PMP is enabled on your router."
            )
    except Exception as e:
        logger.warning(
            "NAT manager start failed: %s. Port mapping may not work, which could prevent incoming connections.",
            e,
            exc_info=True,
        )


async def start_udp_tracker_client(manager: Any) -> None:
    """Initialize UDP tracker client during daemon startup.

    CRITICAL: UDP tracker client socket must be initialized during daemon startup,
    not lazily, to prevent daemon/executor sync issues. The socket should never be
    recreated, so it must be created once at startup and remain valid.

    This ensures the executor can use the tracker client immediately without
    triggering socket creation, which would break session logic.
    """
    config = manager.config
    logger = manager.logger

    # Only initialize if UDP trackers are enabled
    if not config.discovery.enable_udp_trackers:
        logger.debug(
            "UDP trackers disabled, skipping UDP tracker client initialization"
        )
        return

    start = time.time()
    logger.info("Initializing UDP tracker client...")

    # CRITICAL FIX: Wait for NAT port mapping to complete before initializing UDP tracker client
    # UDP tracker client uses tracker_udp_port (or listen_port for backward compatibility)
    if manager.nat_manager and config.nat.auto_map_ports:
        logger.info(
            "Waiting for NAT port mapping to complete before initializing UDP tracker client..."
        )
        mapping_ready = await manager.nat_manager.wait_for_mapping(timeout=60.0)
        if mapping_ready:
            # Use tracker_udp_port if available, fallback to listen_port for backward compatibility
            tracker_port = (
                config.network.tracker_udp_port or config.network.listen_port
            )
            try:
                external_port = await manager.nat_manager.get_external_port(
                    tracker_port, "udp"
                )
                if external_port is not None:
                    logger.info(
                        "NAT port mapping confirmed (UDP tracker: %d -> %d), initializing UDP tracker client",
                        tracker_port,
                        external_port,
                    )
                else:
                    logger.warning(
                        "NAT port mapping exists but UDP tracker port %d mapping not found. "
                        "UDP tracker client will initialize anyway, but tracker communication may fail.",
                        tracker_port,
                    )
            except Exception as e:
                logger.debug(
                    "Failed to validate UDP port mapping: %s", e, exc_info=True
                )
                logger.info(
                    "NAT port mapping confirmed, initializing UDP tracker client (validation skipped)"
                )
        else:
            logger.warning(
                "NAT port mapping not confirmed after 60s timeout. "
                "UDP tracker client will initialize anyway, but tracker communication may fail."
            )

    # CRITICAL FIX: Check port availability before starting UDP tracker client
    tracker_port = (
        config.network.tracker_udp_port or config.network.listen_port
    )
    from ccbt.utils.port_checker import is_port_available

    port_available, port_error = is_port_available("0.0.0.0", tracker_port, "udp")
    if not port_available:
        from ccbt.utils.port_checker import (
            get_permission_error_resolution,
            get_port_conflict_resolution,
        )

        # CRITICAL FIX: Distinguish between permission errors and port conflicts
        # Check for permission denied in multiple ways (error code 10013 on Windows, 13 on Unix)
        is_permission_error = (
            port_error
            and (
                "Permission denied" in port_error
                or "10013" in str(port_error)
                or "WSAEACCES" in str(port_error)
                or "EACCES" in str(port_error)
                or "forbidden" in str(port_error).lower()
            )
        )
        if is_permission_error:
            resolution = get_permission_error_resolution(tracker_port, "udp")
            warning_msg = (
                f"UDP tracker port {tracker_port} cannot be bound.\n"
                f"{port_error}\n\n"
                f"{resolution}\n\n"
                "UDP tracker client will not be initialized. UDP tracker operations will not work."
            )
        else:
            resolution = get_port_conflict_resolution(tracker_port, "udp")
            warning_msg = (
                f"UDP tracker port {tracker_port} is not available.\n"
                f"{port_error}\n\n"
                f"Port {tracker_port} (UDP) may be already in use.\n"
                f"{resolution}\n\n"
                "UDP tracker client will not be initialized. UDP tracker operations will not work."
            )
        logger.warning(warning_msg)
        # Don't raise - allow daemon to continue without UDP tracker
        # UDP tracker is best-effort and not critical for daemon operation
        manager.udp_tracker_client = None
        return

    try:
        # CRITICAL FIX: Initialize UDP tracker client during startup
        # This ensures the socket is created once and never recreated
        # Singleton pattern removed - create instance directly and store in session manager
        from ccbt.discovery.tracker_udp_client import AsyncUDPTrackerClient

        udp_client = AsyncUDPTrackerClient()
        await udp_client.start()

        # CRITICAL FIX: Validate socket is ready after initialization
        if (
            udp_client.transport is None
            or udp_client.transport.is_closing()
            or not udp_client._socket_ready
        ):
            raise RuntimeError(
                "UDP tracker client socket initialization failed. "
                "Socket must be ready after initialization."
            )

        # CRITICAL FIX: Perform additional health check to ensure socket can send/receive
        # Wait a brief moment for socket to fully initialize
        await asyncio.sleep(0.1)

        # Verify socket health with detailed logging
        logger.debug("Performing socket health check for UDP tracker client...")
        socket_healthy = udp_client._check_socket_health()
        if not socket_healthy:
            logger.error(
                "UDP tracker client socket health check failed after initialization. "
                "Socket state: ready=%s, transport=%s, closing=%s, error_count=%d",
                udp_client._socket_ready,
                udp_client.transport is not None,
                udp_client.transport.is_closing() if udp_client.transport else None,
                udp_client._socket_error_count,
            )
            raise RuntimeError(
                "UDP tracker client socket health check failed after initialization. "
                "Socket may not be ready for use."
            )
        logger.debug("Socket health check passed for UDP tracker client")

        # CRITICAL FIX: Verify socket is bound to correct port
        if hasattr(udp_client, "transport") and udp_client.transport:
            try:
                sock = udp_client.transport.get_extra_info("socket")
                if sock:
                    bound_addr = sock.getsockname()
                    # Use tracker_udp_port if available, fallback to listen_port for backward compatibility
                    expected_port = (
                        config.network.tracker_udp_port
                        or config.network.listen_port
                    )
                    if bound_addr[1] != expected_port:
                        logger.warning(
                            "UDP tracker client socket bound to port %d, but expected %d. "
                            "This may cause tracker communication issues.",
                            bound_addr[1],
                            expected_port,
                        )
                    else:
                        logger.debug(
                            "UDP tracker client socket verified: bound to %s:%d (expected port: %d)",
                            bound_addr[0],
                            bound_addr[1],
                            expected_port,
                        )
            except Exception as sock_check_error:
                logger.debug("Could not verify socket binding: %s", sock_check_error)

        # CRITICAL FIX: Store reference in session manager
        # This ensures all torrent sessions and executors use the same initialized instance
        # No code should ever create a new UDP tracker client - always use this one
        manager.udp_tracker_client = udp_client

        # CRITICAL FIX: Verify storage was successful
        if manager.udp_tracker_client is not udp_client:
            raise RuntimeError(
                "Failed to store UDP tracker client in session manager. "
                "Reference mismatch detected."
            )

        logger.info(
            "UDP tracker client initialized successfully and verified (took %.2fs, socket_ready=%s, transport=%s)",
            time.time() - start,
            udp_client._socket_ready,
            udp_client.transport is not None,
        )
    except Exception as e:
        logger.warning(
            "Failed to initialize UDP tracker client (took %.2fs): %s. "
            "Tracker operations may fail until client is initialized.",
            time.time() - start,
            e,
            exc_info=True,
        )


async def start_tcp_server(manager: Any) -> None:
    """Start TCP server for incoming peer connections if enabled."""
    if not manager.config.network.enable_tcp:
        return
    start = time.time()
    logger = manager.logger
    logger.info("Starting TCP server for incoming peer connections...")

    # CRITICAL FIX: Wait for NAT port mapping to complete before starting TCP server
    # This ensures incoming connections can reach the client through NAT
    # Increased timeout to 60s to handle slow routers and retry logic
    if manager.nat_manager and manager.config.nat.auto_map_ports:
        logger.info(
            "Waiting for NAT port mapping to complete before starting TCP server..."
        )
        mapping_ready = await manager.nat_manager.wait_for_mapping(timeout=60.0)
        if mapping_ready:
            # CRITICAL FIX: Validate that TCP port mapping exists specifically
            listen_port = manager.config.network.listen_port
            try:
                external_port = await manager.nat_manager.get_external_port(
                    listen_port, "tcp"
                )
                if external_port is not None:
                    logger.info(
                        "NAT port mapping confirmed (TCP: %d -> %d), starting TCP server",
                        listen_port,
                        external_port,
                    )
                else:
                    logger.warning(
                        "NAT port mapping exists but TCP port %d mapping not found. "
                        "TCP server will start anyway, but incoming connections may fail.",
                        listen_port,
                    )
            except Exception as e:
                logger.debug(
                    "Failed to validate TCP port mapping: %s", e, exc_info=True
                )
                logger.info(
                    "NAT port mapping confirmed, starting TCP server (validation skipped)"
                )
        else:
            logger.warning(
                "NAT port mapping not confirmed after 60s timeout. "
                "TCP server will start anyway, but incoming connections may fail. "
                "This may indicate NAT-PMP/UPnP is disabled on your router or the router is slow to respond. "
                "Troubleshooting: Check router UPnP/NAT-PMP settings, firewall rules, and router logs."
            )

    # CRITICAL FIX: Check port availability before starting TCP server
    listen_interface = manager.config.network.listen_interface or "0.0.0.0"
    listen_port = (
        manager.config.network.listen_port_tcp or manager.config.network.listen_port
    )
    from ccbt.utils.port_checker import is_port_available

    port_available, port_error = is_port_available(listen_interface, listen_port, "tcp")
    if not port_available:
        from ccbt.utils.port_checker import (
            get_permission_error_resolution,
            get_port_conflict_resolution,
        )

        # CRITICAL FIX: Distinguish between permission errors and port conflicts
        # Check for permission denied in multiple ways (error code 10013 on Windows, 13 on Unix)
        is_permission_error = (
            port_error
            and (
                "Permission denied" in port_error
                or "10013" in str(port_error)
                or "WSAEACCES" in str(port_error)
                or "EACCES" in str(port_error)
                or "forbidden" in str(port_error).lower()
            )
        )
        if is_permission_error:
            resolution = get_permission_error_resolution(listen_port, "tcp")
            error_msg = (
                f"TCP listen port {listen_port} cannot be bound.\n"
                f"{port_error}\n\n"
                f"{resolution}"
            )
        else:
            resolution = get_port_conflict_resolution(listen_port, "tcp")
            error_msg = (
                f"TCP listen port {listen_port} is not available.\n"
                f"{port_error}\n\n"
                f"Port {listen_port} (TCP) may be already in use.\n"
                f"{resolution}"
            )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        manager.tcp_server = manager._make_tcp_server()
        if manager.tcp_server is None:
            error_msg = (
                "Failed to create TCP server (factory returned None). "
                "Check logs for detailed error information."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        await manager.tcp_server.start()

        # CRITICAL FIX: Validate TCP server is using configured port
        actual_port = None
        try:
            if hasattr(manager.tcp_server, "get_port"):
                actual_port = manager.tcp_server.get_port()
            elif hasattr(manager.tcp_server, "port"):
                actual_port = manager.tcp_server.port
            elif hasattr(manager.tcp_server, "_port"):
                actual_port = manager.tcp_server._port
        except Exception as e:
            logger.debug("Could not determine actual TCP server port: %s", e)

        if actual_port is not None and actual_port != listen_port:
            logger.warning(
                "TCP server port mismatch: configured=%d, actual=%d. "
                "This may cause NAT port mapping to fail. "
                "Check TCP server implementation uses configured port.",
                listen_port,
                actual_port,
            )
        else:
            logger.info(
                "TCP server started successfully on port %d (configured=%d, actual=%s, took %.2fs)",
                listen_port,
                listen_port,
                actual_port if actual_port is not None else "unknown",
                time.time() - start,
            )
    except Exception as e:
        logger.warning(
            "Failed to start TCP server for incoming connections (took %.2fs): %s",
            time.time() - start,
            e,
            exc_info=True,
        )
        logger.debug("TCP server start failed", exc_info=True)


async def start_webtorrent_components(manager: Any) -> None:
    """Initialize WebTorrent components during daemon startup.

    CRITICAL: WebTorrent WebSocket server and WebRTC manager must be initialized
    during daemon startup, not lazily, to prevent port conflicts and socket
    recreation issues. The WebSocket server socket should never be recreated.

    This ensures all WebTorrent protocol instances use the same initialized
    components, preventing duplicate socket creation and resource conflicts.
    """
    config = manager.config
    logger = manager.logger

    # Only initialize if WebTorrent is enabled
    if not config.network.webtorrent.enable_webtorrent:
        logger.debug(
            "WebTorrent disabled, skipping WebTorrent components initialization"
        )
        return

    start = time.time()
    logger.info("Initializing WebTorrent components...")

    try:
        # CRITICAL FIX: Initialize WebRTC connection manager during startup
        # This ensures the manager is shared across all WebTorrent protocol instances
        try:
            from ccbt.protocols.webtorrent.webrtc_manager import WebRTCConnectionManager

            webtorrent_config = config.network.webtorrent
            webrtc_manager = WebRTCConnectionManager(
                stun_servers=webtorrent_config.webtorrent_stun_servers,
                turn_servers=webtorrent_config.webtorrent_turn_servers,
                max_connections=webtorrent_config.webtorrent_max_connections,
            )

            # CRITICAL FIX: Store reference in session manager
            manager.webrtc_manager = webrtc_manager
            logger.info("WebRTC connection manager initialized successfully")
        except ImportError as e:
            logger.warning(
                "WebRTC manager not available (aiortc may not be installed): %s. "
                "WebTorrent WebRTC features will not work.",
                e,
            )
            manager.webrtc_manager = None
        except Exception as e:
            logger.warning(
                "Failed to initialize WebRTC connection manager: %s. "
                "WebTorrent WebRTC features may not work.",
                e,
                exc_info=True,
            )
            manager.webrtc_manager = None

        # CRITICAL FIX: Initialize WebSocket server for signaling during startup
        # WebSocket server socket must be initialized once and never recreated
        # This prevents port conflicts and socket recreation issues
        try:
            from aiohttp import web  # type: ignore[attr-defined]

            webtorrent_config = config.network.webtorrent
            host = webtorrent_config.webtorrent_host
            port = webtorrent_config.webtorrent_port

            # Create WebSocket application
            app = web.Application()  # type: ignore[attr-defined]

            # CRITICAL FIX: WebSocket endpoint must be added before server starts
            # Create a shared handler that protocol instances can use
            # Protocol instances will register themselves and handle their own connections
            async def webtorrent_signaling_handler(
                request: web.Request,
            ) -> web.WebSocketResponse:  # type: ignore[attr-defined]
                """Shared WebSocket handler for WebTorrent signaling.

                This handler delegates to registered WebTorrentProtocol instances.
                Each protocol instance handles its own WebSocket connections.
                """
                ws = web.WebSocketResponse()  # type: ignore[attr-defined]
                await ws.prepare(request)

                # CRITICAL FIX: Route to protocol instances registered in session manager
                # Protocol instances will handle their own signaling logic
                # Store active protocol instances in session manager for routing
                if (
                    hasattr(manager, "_webtorrent_protocols")
                    and manager._webtorrent_protocols
                ):
                    # Try to handle with first available protocol instance
                    # In practice, there's usually one protocol instance per session
                    for protocol in manager._webtorrent_protocols:
                        if hasattr(protocol, "_websocket_handler"):
                            try:
                                # Delegate to protocol's handler - it returns the WebSocketResponse
                                return await protocol._websocket_handler(request)
                            except Exception as e:
                                logger.debug("Protocol handler error: %s", e)
                                continue

                # No protocol instance available - close connection
                logger.warning(
                    "No WebTorrent protocol instance available to handle WebSocket connection"
                )
                await ws.close()
                return ws

            # Add WebSocket endpoint
            app.router.add_get("/signaling", webtorrent_signaling_handler)

            # CRITICAL FIX: Initialize protocol registry for routing
            manager._webtorrent_protocols = []  # type: ignore[attr-defined]

            # Start server
            runner = web.AppRunner(app)  # type: ignore[attr-defined]
            await runner.setup()

            try:
                site = web.TCPSite(runner, host, port)  # type: ignore[attr-defined]
                await site.start()
                logger.info(
                    "WebTorrent WebSocket signaling server started on %s:%d", host, port
                )
            except OSError as e:
                if "Address already in use" in str(e) or e.errno == 98:  # EADDRINUSE
                    logger.error(
                        "WebTorrent WebSocket port %d is already in use. "
                        "Please choose a different port or stop the conflicting service.",
                        port,
                    )
                    raise
                logger.exception("Failed to start WebTorrent WebSocket server")
                raise

            # CRITICAL FIX: Store reference in session manager
            # Store both app and runner for proper cleanup
            manager.webtorrent_websocket_server = {
                "app": app,
                "runner": runner,
                "site": site,
                "host": host,
                "port": port,
            }

            logger.info(
                "WebTorrent WebSocket server initialized successfully (took %.2fs)",
                time.time() - start,
            )
        except ImportError as e:
            logger.warning(
                "aiohttp not available for WebTorrent WebSocket server: %s. "
                "WebTorrent signaling will not work.",
                e,
            )
            manager.webtorrent_websocket_server = None
        except Exception as e:
            logger.warning(
                "Failed to initialize WebTorrent WebSocket server: %s. "
                "WebTorrent signaling may not work.",
                e,
                exc_info=True,
            )
            manager.webtorrent_websocket_server = None

    except Exception as e:
        logger.error(
            "Critical error initializing WebTorrent components: %s",
            e,
            exc_info=True,
        )
        # Don't fail daemon startup - WebTorrent is optional
        manager.webrtc_manager = None
        manager.webtorrent_websocket_server = None


async def start_utp_socket_manager(manager: Any) -> None:
    """Initialize uTP socket manager during daemon startup.

    CRITICAL: uTP socket manager socket must be initialized during daemon startup,
    not lazily, to prevent socket recreation issues. The socket should never be
    recreated, so it must be created once at startup and remain valid.

    This ensures all peer connections use the same initialized uTP socket.
    """
    config = manager.config
    logger = manager.logger

    # Only initialize if uTP is enabled (check config if available)
    # uTP is typically always enabled, but check for safety
    try:
        utp_enabled = getattr(config.network, "utp_enabled", True)
        if not utp_enabled:
            logger.debug("uTP disabled, skipping uTP socket manager initialization")
            return
    except AttributeError:
        # Config doesn't have uTP setting, assume enabled
        pass

    start = time.time()
    logger.info("Initializing uTP socket manager...")

    try:
        from ccbt.transport.utp_socket import UTPSocketManager

        # CRITICAL FIX: Create uTP socket manager instance directly
        # Singleton pattern removed - create instance and store in session manager
        utp_manager = UTPSocketManager()
        await utp_manager.start()

        # CRITICAL FIX: Validate socket is ready after initialization
        if utp_manager.transport is None or utp_manager.transport.is_closing():
            raise RuntimeError(
                "uTP socket manager socket initialization failed. "
                "Socket must be ready after initialization."
            )

        # CRITICAL FIX: Store reference in session manager
        manager.utp_socket_manager = utp_manager

        logger.info(
            "uTP socket manager initialized successfully (took %.2fs, transport=%s)",
            time.time() - start,
            utp_manager.transport is not None,
        )
    except Exception as e:
        logger.warning(
            "Failed to initialize uTP socket manager: %s. "
            "uTP connections may not work.",
            e,
            exc_info=True,
        )
        # Don't fail daemon startup - uTP is optional
        manager.utp_socket_manager = None
