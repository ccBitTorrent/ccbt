"""Security command executor.

Handles security-related commands (blacklist, whitelist, IP filter, etc.).
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class SecurityExecutor(CommandExecutor):
    """Executor for security commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute security command.

        Args:
            command: Command name (e.g., "security.get_blacklist", "security.load_ip_filter")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "security.get_blacklist":
            return await self._get_blacklist()
        if command == "security.get_whitelist":
            return await self._get_whitelist()
        if command == "security.add_to_blacklist":
            return await self._add_to_blacklist(**kwargs)
        if command == "security.remove_from_blacklist":
            return await self._remove_from_blacklist(**kwargs)
        if command == "security.add_to_whitelist":
            return await self._add_to_whitelist(**kwargs)
        if command == "security.remove_from_whitelist":
            return await self._remove_from_whitelist(**kwargs)
        if command == "security.load_ip_filter":
            return await self._load_ip_filter()
        if command == "security.get_ip_filter_stats":
            return await self._get_ip_filter_stats()
        if command == "security.ban_peer":
            return await self._ban_peer(**kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown security command: {command}",
        )

    async def _get_blacklist(self) -> CommandResult:
        """Get blacklisted IPs."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=True,
                    data={"blacklist": []},
                )

            blacklist = security_manager.get_blacklisted_ips()
            return CommandResult(
                success=True,
                data={"blacklist": list(blacklist)},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_whitelist(self) -> CommandResult:
        """Get whitelisted IPs."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=True,
                    data={"whitelist": []},
                )

            whitelist = security_manager.get_whitelisted_ips()
            return CommandResult(
                success=True,
                data={"whitelist": list(whitelist)},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _add_to_blacklist(self, ip: str, reason: str = "") -> CommandResult:
        """Add IP to blacklist."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=False,
                    error="Security manager not available",
                )

            security_manager.add_to_blacklist(ip, reason)
            return CommandResult(success=True, data={"added": True})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _remove_from_blacklist(self, ip: str) -> CommandResult:
        """Remove IP from blacklist."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=False,
                    error="Security manager not available",
                )

            security_manager.remove_from_blacklist(ip)
            return CommandResult(success=True, data={"removed": True})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _add_to_whitelist(self, ip: str, reason: str = "") -> CommandResult:
        """Add IP to whitelist."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=False,
                    error="Security manager not available",
                )

            security_manager.add_to_whitelist(ip, reason)
            return CommandResult(success=True, data={"added": True})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _remove_from_whitelist(self, ip: str) -> CommandResult:
        """Remove IP from whitelist."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=False,
                    error="Security manager not available",
                )

            security_manager.remove_from_whitelist(ip)
            return CommandResult(success=True, data={"removed": True})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _load_ip_filter(self) -> CommandResult:
        """Load IP filter from config."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=False,
                    error="Security manager not available",
                )

            await security_manager.load_ip_filter(session.config)
            return CommandResult(success=True, data={"loaded": True})
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _get_ip_filter_stats(self) -> CommandResult:
        """Get IP filter statistics."""
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager or not security_manager.ip_filter:
                return CommandResult(
                    success=True,
                    data={"enabled": False, "stats": {}},
                )

            stats = security_manager.ip_filter.get_filter_statistics()
            return CommandResult(
                success=True,
                data={
                    "enabled": security_manager.ip_filter.enabled,
                    "stats": stats,
                },
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))

    async def _ban_peer(self, ip: str, reason: str = "") -> CommandResult:
        """Ban a peer by IP address.
        
        Args:
            ip: IP address to ban
            reason: Reason for banning (optional)
            
        Returns:
            CommandResult with execution result
        """
        try:
            from ccbt.executor.session_adapter import LocalSessionAdapter

            if not isinstance(self.adapter, LocalSessionAdapter):
                return CommandResult(
                    success=False,
                    error="Security commands only available in local mode",
                )

            session = self.adapter.session_manager
            security_manager = getattr(session, "security_manager", None)
            if not security_manager:
                return CommandResult(
                    success=False,
                    error="Security manager not available",
                )

            # Add to blacklist with reason
            ban_reason = reason or f"Manually banned peer: {ip}"
            security_manager.add_to_blacklist(ip, ban_reason, source="manual")
            
            # Also disconnect the peer if connected
            # Get all torrent sessions and disconnect peers with this IP
            if hasattr(session, "torrent_sessions"):
                for torrent_session in session.torrent_sessions.values():
                    if hasattr(torrent_session, "download_manager"):
                        download_manager = torrent_session.download_manager
                        if hasattr(download_manager, "peer_manager"):
                            peer_manager = download_manager.peer_manager
                            if hasattr(peer_manager, "disconnect_peer_by_ip"):
                                await peer_manager.disconnect_peer_by_ip(ip)
                            elif hasattr(peer_manager, "peers"):
                                # Fallback: iterate through peers and disconnect matching IPs
                                for peer in list(peer_manager.peers.values()):
                                    if hasattr(peer, "ip") and peer.ip == ip:
                                        if hasattr(peer, "disconnect"):
                                            await peer.disconnect()
                                        elif hasattr(peer, "close"):
                                            await peer.close()
            
            return CommandResult(
                success=True,
                data={"banned": True, "ip": ip, "reason": ban_reason},
            )
        except Exception as e:
            return CommandResult(success=False, error=str(e))
