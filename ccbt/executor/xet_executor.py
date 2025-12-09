"""XET command executor.

Handles XET folder synchronization commands (tonic.create, tonic.sync, etc.).
"""

from __future__ import annotations

from typing import Any

from ccbt.executor.base import CommandExecutor, CommandResult


class XetExecutor(CommandExecutor):
    """Executor for XET folder synchronization commands."""

    async def execute(
        self,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute XET command.

        Args:
            command: Command name (e.g., "xet.create_tonic", "xet.sync")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            CommandResult with execution result

        """
        if command == "xet.create_tonic":
            return await self._create_tonic(*args, **kwargs)
        if command == "xet.generate_link":
            return await self._generate_link(*args, **kwargs)
        if command == "xet.sync":
            return await self._sync_folder(*args, **kwargs)
        if command == "xet.add_xet_folder":
            return await self._add_xet_folder_session(*args, **kwargs)
        if command == "xet.remove_xet_folder":
            return await self._remove_xet_folder_session(*args, **kwargs)
        if command == "xet.list_xet_folders":
            return await self._list_xet_folders_session(*args, **kwargs)
        if command == "xet.get_xet_folder_status":
            return await self._get_xet_folder_status_session(*args, **kwargs)
        if command == "xet.status":
            return await self._get_status(*args, **kwargs)
        if command == "xet.allowlist_add":
            return await self._allowlist_add(*args, **kwargs)
        if command == "xet.allowlist_remove":
            return await self._allowlist_remove(*args, **kwargs)
        if command == "xet.allowlist_list":
            return await self._allowlist_list(*args, **kwargs)
        if command == "xet.allowlist_alias_add":
            return await self._allowlist_alias_add(*args, **kwargs)
        if command == "xet.allowlist_alias_remove":
            return await self._allowlist_alias_remove(*args, **kwargs)
        if command == "xet.allowlist_alias_list":
            return await self._allowlist_alias_list(*args, **kwargs)
        if command == "xet.allowlist_alias_set":
            return await self._allowlist_alias_set(*args, **kwargs)
        if command == "xet.set_sync_mode":
            return await self._set_sync_mode(*args, **kwargs)
        if command == "xet.get_sync_mode":
            return await self._get_sync_mode(*args, **kwargs)
        if command == "xet.get_file_tree":
            return await self._get_file_tree(*args, **kwargs)
        if command == "xet.enable":
            return await self._enable_xet(*args, **kwargs)
        if command == "xet.disable":
            return await self._disable_xet(*args, **kwargs)
        if command == "xet.set_port":
            return await self._set_port(*args, **kwargs)
        if command == "xet.get_config":
            return await self._get_config(*args, **kwargs)
        return CommandResult(
            success=False,
            error=f"Unknown XET command: {command}",
        )

    async def _create_tonic(
        self,
        folder_path: str,
        output_path: str | None = None,
        sync_mode: str = "best_effort",
        source_peers: list[str] | None = None,
        allowlist_path: str | None = None,
        git_ref: str | None = None,
        announce: str | None = None,
    ) -> CommandResult:
        """Create .tonic file from folder."""
        try:
            from ccbt.cli.tonic_generator import generate_tonic_from_folder

            tonic_path, link = await generate_tonic_from_folder(
                folder_path=folder_path,
                output_path=output_path,
                sync_mode=sync_mode,
                source_peers=source_peers,
                allowlist_path=allowlist_path,
                git_ref=git_ref,
                announce=announce,
                generate_link=False,
            )
            return CommandResult(
                success=True,
                data={"tonic_path": tonic_path, "link": link},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to create tonic file: {e}",
            )

    async def _generate_link(
        self,
        folder_path: str | None = None,
        tonic_file: str | None = None,
    ) -> CommandResult:
        """Generate tonic?: link."""
        try:
            from ccbt.core.tonic import TonicFile
            from ccbt.core.tonic_link import generate_tonic_link

            if tonic_file:
                tonic_parser = TonicFile()
                parsed_data = tonic_parser.parse(tonic_file)
                info_hash = tonic_parser.get_info_hash(parsed_data)
                display_name = parsed_data["info"]["name"]
                trackers = parsed_data.get("announce_list") or (
                    [[parsed_data["announce"]]] if parsed_data.get("announce") else None
                )
                git_refs = parsed_data.get("git_refs")
                sync_mode = parsed_data.get("sync_mode", "best_effort")
                source_peers = parsed_data.get("source_peers")
                allowlist_hash = parsed_data.get("allowlist_hash")

                tracker_list: list[str] | None = None
                if trackers:
                    tracker_list = [url for tier in trackers for url in tier]

                link = generate_tonic_link(
                    info_hash=info_hash,
                    display_name=display_name,
                    trackers=tracker_list,
                    git_refs=git_refs,
                    sync_mode=sync_mode,
                    source_peers=source_peers,
                    allowlist_hash=allowlist_hash,
                )
            else:
                from ccbt.cli.tonic_generator import generate_tonic_from_folder

                _, link = await generate_tonic_from_folder(
                    folder_path=folder_path or ".",
                    generate_link=True,
                )

            return CommandResult(success=True, data={"link": link})
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to generate link: {e}",
            )

    async def _sync_folder(
        self,
        tonic_input: str,
        output_dir: str | None = None,
        check_interval: float = 5.0,
    ) -> CommandResult:
        """Start syncing folder from .tonic file or tonic?: link."""
        try:
            from ccbt.storage.xet_folder_manager import XetFolder

            if tonic_input.startswith("tonic?:"):
                from ccbt.core.tonic_link import parse_tonic_link

                link_info = parse_tonic_link(tonic_input)
                # For now, just return that we would sync
                # Full implementation would fetch .tonic file and start sync
                return CommandResult(
                    success=True,
                    data={"status": "sync_started", "link_info": link_info.model_dump()},
                )
            from ccbt.core.tonic import TonicFile

            tonic_parser = TonicFile()
            parsed_data = tonic_parser.parse(tonic_input)
            folder_name = parsed_data["info"]["name"]
            sync_mode = parsed_data.get("sync_mode", "best_effort")

            if not output_dir:
                output_dir = folder_name

            folder = XetFolder(
                folder_path=output_dir,
                sync_mode=sync_mode,
                check_interval=check_interval,
            )
            await folder.start()

            return CommandResult(
                success=True,
                data={"status": "sync_started", "folder_path": output_dir},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to start sync: {e}",
            )

    async def _get_status(self, folder_path: str) -> CommandResult:
        """Get sync status for folder."""
        try:
            from ccbt.storage.xet_folder_manager import XetFolder

            folder = XetFolder(folder_path=folder_path)
            status = folder.get_status()
            return CommandResult(
                success=True,
                data=status.model_dump(),
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get status: {e}",
            )

    async def _allowlist_add(
        self,
        allowlist_path: str,
        peer_id: str,
        public_key: str | None = None,
    ) -> CommandResult:
        """Add peer to allowlist."""
        try:
            from ccbt.security.xet_allowlist import XetAllowlist

            allowlist = XetAllowlist(allowlist_path=allowlist_path)
            await allowlist.load()

            public_key_bytes = None
            if public_key:
                public_key_bytes = bytes.fromhex(public_key)
                if len(public_key_bytes) != 32:
                    return CommandResult(
                        success=False,
                        error="Public key must be 32 bytes (64 hex characters)",
                    )

            allowlist.add_peer(peer_id=peer_id, public_key=public_key_bytes)
            await allowlist.save()

            return CommandResult(success=True, data={"peer_id": peer_id})
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to add peer to allowlist: {e}",
            )

    async def _allowlist_remove(
        self,
        allowlist_path: str,
        peer_id: str,
    ) -> CommandResult:
        """Remove peer from allowlist."""
        try:
            from ccbt.security.xet_allowlist import XetAllowlist

            allowlist = XetAllowlist(allowlist_path=allowlist_path)
            await allowlist.load()

            removed = allowlist.remove_peer(peer_id)
            if removed:
                await allowlist.save()
                return CommandResult(success=True, data={"peer_id": peer_id, "removed": True})
            return CommandResult(
                success=True,
                data={"peer_id": peer_id, "removed": False},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to remove peer from allowlist: {e}",
            )

    async def _allowlist_list(self, allowlist_path: str) -> CommandResult:
        """List peers in allowlist."""
        try:
            from ccbt.security.xet_allowlist import XetAllowlist

            allowlist = XetAllowlist(allowlist_path=allowlist_path)
            await allowlist.load()

            peers = allowlist.get_peers()
            peer_list = []
            for peer_id in peers:
                peer_info = allowlist.get_peer_info(peer_id)
                # Get alias from metadata
                alias = None
                if peer_info:
                    metadata = peer_info.get("metadata", {})
                    if isinstance(metadata, dict):
                        alias = metadata.get("alias")

                peer_list.append(
                    {
                        "peer_id": peer_id,
                        "alias": alias,
                        "public_key": peer_info.get("public_key", "").hex()
                        if peer_info and peer_info.get("public_key")
                        else None,
                        "added_at": peer_info.get("added_at") if peer_info else None,
                    }
                )

            return CommandResult(success=True, data={"peers": peer_list})
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to list allowlist: {e}",
            )

    async def _allowlist_alias_add(
        self,
        allowlist_path: str,
        peer_id: str,
        alias: str,
    ) -> CommandResult:
        """Add or update alias for a peer."""
        try:
            from ccbt.security.xet_allowlist import XetAllowlist

            allowlist = XetAllowlist(allowlist_path=allowlist_path)
            await allowlist.load()

            if not allowlist.is_allowed(peer_id):
                return CommandResult(
                    success=False,
                    error=f"Peer {peer_id} not found in allowlist",
                )

            success = allowlist.set_alias(peer_id, alias)
            if success:
                await allowlist.save()
                return CommandResult(
                    success=True,
                    data={"peer_id": peer_id, "alias": alias},
                )
            return CommandResult(
                success=False,
                error=f"Failed to set alias for peer {peer_id}",
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to set alias: {e}",
            )

    async def _allowlist_alias_set(
        self,
        allowlist_path: str,
        peer_id: str,
        alias: str,
    ) -> CommandResult:
        """Set alias for a peer (alias for alias_add)."""
        return await self._allowlist_alias_add(allowlist_path, peer_id, alias)

    async def _allowlist_alias_remove(
        self,
        allowlist_path: str,
        peer_id: str,
    ) -> CommandResult:
        """Remove alias for a peer."""
        try:
            from ccbt.security.xet_allowlist import XetAllowlist

            allowlist = XetAllowlist(allowlist_path=allowlist_path)
            await allowlist.load()

            removed = allowlist.remove_alias(peer_id)
            if removed:
                await allowlist.save()
                return CommandResult(
                    success=True,
                    data={"peer_id": peer_id, "removed": True},
                )
            return CommandResult(
                success=True,
                data={"peer_id": peer_id, "removed": False},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to remove alias: {e}",
            )

    async def _allowlist_alias_list(self, allowlist_path: str) -> CommandResult:
        """List all aliases in allowlist."""
        try:
            from ccbt.security.xet_allowlist import XetAllowlist

            allowlist = XetAllowlist(allowlist_path=allowlist_path)
            await allowlist.load()

            peers = allowlist.get_peers()
            aliases = []

            for peer_id in peers:
                alias = allowlist.get_alias(peer_id)
                if alias:
                    aliases.append({"peer_id": peer_id, "alias": alias})

            return CommandResult(success=True, data={"aliases": aliases})
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to list aliases: {e}",
            )

    async def _set_sync_mode(
        self,
        folder_path: str,
        sync_mode: str,
        source_peers: list[str] | None = None,
    ) -> CommandResult:
        """Set synchronization mode for folder."""
        try:
            from ccbt.storage.xet_folder_manager import XetFolder

            folder = XetFolder(folder_path=folder_path)
            folder.set_sync_mode(sync_mode, source_peers)
            return CommandResult(
                success=True,
                data={"sync_mode": sync_mode, "source_peers": source_peers},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to set sync mode: {e}",
            )

    async def _get_sync_mode(self, folder_path: str) -> CommandResult:
        """Get current synchronization mode for folder."""
        try:
            from ccbt.storage.xet_folder_manager import XetFolder

            folder = XetFolder(folder_path=folder_path)
            status = folder.get_status()
            return CommandResult(
                success=True,
                data={"sync_mode": status.sync_mode},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get sync mode: {e}",
            )

    async def _get_file_tree(self, tonic_file: str) -> CommandResult:
        """Get parseable file tree from .tonic file."""
        try:
            from ccbt.core.tonic import TonicFile

            tonic_parser = TonicFile()
            parsed_data = tonic_parser.parse(tonic_file)
            file_tree = tonic_parser.get_file_tree(parsed_data)
            return CommandResult(
                success=True,
                data={"file_tree": file_tree},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get file tree: {e}",
            )

    async def _enable_xet(self) -> CommandResult:
        """Enable XET globally."""
        try:
            from ccbt.config.config import get_config_manager

            config_manager = get_config_manager()
            config_manager.config.xet_sync.enable_xet = True
            config_manager.save()
            return CommandResult(
                success=True,
                data={"enabled": True},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to enable XET: {e}",
            )

    async def _disable_xet(self) -> CommandResult:
        """Disable XET globally."""
        try:
            from ccbt.config.config import get_config_manager

            config_manager = get_config_manager()
            config_manager.config.xet_sync.enable_xet = False
            config_manager.save()
            return CommandResult(
                success=True,
                data={"enabled": False},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to disable XET: {e}",
            )

    async def _set_port(self, port: int) -> CommandResult:
        """Set XET port."""
        try:
            from ccbt.config.config import get_config_manager

            config_manager = get_config_manager()
            config_manager.config.network.xet_port = port
            config_manager.save()
            return CommandResult(
                success=True,
                data={"port": port},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to set XET port: {e}",
            )

    async def _get_config(self) -> CommandResult:
        """Get XET configuration."""
        try:
            from ccbt.config.config import get_config

            config = get_config()
            return CommandResult(
                success=True,
                data={
                    "enable_xet": config.xet_sync.enable_xet,
                    "check_interval": config.xet_sync.check_interval,
                    "default_sync_mode": config.xet_sync.default_sync_mode,
                    "enable_git_versioning": config.xet_sync.enable_git_versioning,
                    "xet_port": config.network.xet_port,
                },
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get XET config: {e}",
            )

    async def _add_xet_folder_session(
        self,
        folder_path: str,
        tonic_file: str | None = None,
        tonic_link: str | None = None,
        sync_mode: str | None = None,
        source_peers: list[str] | None = None,
        check_interval: float | None = None,
    ) -> CommandResult:
        """Add XET folder session via session manager."""
        try:
            folder_key = await self.adapter.add_xet_folder(
                folder_path=folder_path,
                tonic_file=tonic_file,
                tonic_link=tonic_link,
                sync_mode=sync_mode,
                source_peers=source_peers,
                check_interval=check_interval,
            )
            return CommandResult(
                success=True,
                data={"folder_key": folder_key, "folder_path": folder_path},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to add XET folder session: {e}",
            )

    async def _remove_xet_folder_session(
        self,
        folder_key: str,
    ) -> CommandResult:
        """Remove XET folder session via session manager."""
        try:
            removed = await self.adapter.remove_xet_folder(folder_key)
            return CommandResult(
                success=True,
                data={"removed": removed, "folder_key": folder_key},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to remove XET folder session: {e}",
            )

    async def _list_xet_folders_session(self) -> CommandResult:
        """List XET folder sessions via session manager."""
        try:
            folders = await self.adapter.list_xet_folders()
            return CommandResult(
                success=True,
                data={"folders": folders},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to list XET folder sessions: {e}",
            )

    async def _get_xet_folder_status_session(
        self,
        folder_key: str,
    ) -> CommandResult:
        """Get XET folder status via session manager."""
        try:
            status = await self.adapter.get_xet_folder_status(folder_key)
            if status is None:
                return CommandResult(
                    success=False,
                    error=f"XET folder {folder_key} not found",
                )
            return CommandResult(
                success=True,
                data={"status": status},
            )
        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to get XET folder status: {e}",
            )

