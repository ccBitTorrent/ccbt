"""Git versioning integration for XET folder synchronization.

This module provides git commit hash tracking, change detection via git diff,
and version management for XET-enabled folders.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GitVersioningError(Exception):
    """Exception raised for git versioning errors."""


class GitVersioning:
    """Git versioning manager for XET folders."""

    def __init__(
        self,
        folder_path: str | Path,
        auto_commit: bool = False,
    ) -> None:
        """Initialize git versioning.

        Args:
            folder_path: Path to git repository folder
            auto_commit: Whether to automatically commit changes

        """
        self.folder_path = Path(folder_path).resolve()
        self.auto_commit = auto_commit
        self.logger = logging.getLogger(__name__)

    def is_git_repo(self) -> bool:
        """Check if folder is a git repository.

        Returns:
            True if folder is a git repository

        """
        git_dir = self.folder_path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    async def get_current_commit(self) -> str | None:
        """Get current git commit hash.

        Returns:
            Commit hash string or None if not a git repo or no commits

        """
        if not self.is_git_repo():
            return None

        try:
            result = await self._run_git_command(["rev-parse", "HEAD"])
            if result and result.strip():
                return result.strip()
        except Exception as e:
            self.logger.debug("Error getting current commit: %s", e)

        return None

    async def get_commit_refs(self, max_refs: int = 10) -> list[str]:
        """Get list of recent git commit hashes.

        Args:
            max_refs: Maximum number of refs to return

        Returns:
            List of commit hashes (most recent first)

        """
        if not self.is_git_repo():
            return []

        try:
            result = await self._run_git_command(
                ["log", f"--max-count={max_refs}", "--format=%H"]
            )
            if result:
                refs = [ref.strip() for ref in result.strip().split("\n") if ref.strip()]
                return refs[:max_refs]
        except Exception as e:
            self.logger.debug("Error getting commit refs: %s", e)

        return []

    async def get_changed_files(self, since_ref: str | None = None) -> list[str]:
        """Get list of changed files since a git ref.

        Args:
            since_ref: Git commit hash/ref to compare against (None = working tree)

        Returns:
            List of changed file paths (relative to repo root)

        """
        if not self.is_git_repo():
            return []

        try:
            if since_ref:
                # Compare against specific ref
                result = await self._run_git_command(
                    ["diff", "--name-only", since_ref, "HEAD"]
                )
            else:
                # Compare working tree against HEAD
                result = await self._run_git_command(["diff", "--name-only", "HEAD"])

            if result:
                files = [
                    f.strip() for f in result.strip().split("\n") if f.strip()
                ]
                return files
        except Exception as e:
            self.logger.debug("Error getting changed files: %s", e)

        return []

    async def get_diff(self, since_ref: str | None = None) -> str | None:
        """Get git diff since a ref.

        Args:
            since_ref: Git commit hash/ref to compare against (None = working tree)

        Returns:
            Diff string or None

        """
        if not self.is_git_repo():
            return None

        try:
            if since_ref:
                result = await self._run_git_command(["diff", since_ref, "HEAD"])
            else:
                result = await self._run_git_command(["diff", "HEAD"])

            if result and result.strip():
                return result
        except Exception as e:
            self.logger.debug("Error getting diff: %s", e)

        return None

    async def has_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if there are uncommitted changes

        """
        if not self.is_git_repo():
            return False

        try:
            # Check for changes in working tree
            result = await self._run_git_command(
                ["status", "--porcelain", "--untracked-files=no"]
            )
            return bool(result and result.strip())
        except Exception as e:
            self.logger.debug("Error checking for changes: %s", e)
            return False

    async def create_commit(
        self, message: str | None = None, files: list[str] | None = None
    ) -> str | None:
        """Create a git commit.

        Args:
            message: Commit message (default: auto-generated)
            files: List of files to commit (None = all changes)

        Returns:
            Commit hash or None if commit failed

        """
        if not self.is_git_repo():
            return None

        if not message:
            message = f"XET sync update {asyncio.get_event_loop().time()}"

        try:
            # Stage files
            if files:
                for file_path in files:
                    await self._run_git_command(["add", file_path])
            else:
                await self._run_git_command(["add", "-A"])

            # Create commit
            result = await self._run_git_command(
                ["commit", "-m", message]
            )

            # Get new commit hash
            commit_hash = await self.get_current_commit()
            if commit_hash:
                self.logger.info("Created git commit: %s", commit_hash[:16])
                return commit_hash

        except Exception as e:
            self.logger.warning("Error creating git commit: %s", e)

        return None

    async def auto_commit_if_changes(self) -> str | None:
        """Automatically commit changes if auto_commit is enabled and changes exist.

        Returns:
            Commit hash if commit was created, None otherwise

        """
        if not self.auto_commit:
            return None

        if await self.has_changes():
            return await self.create_commit()

        return None

    async def get_file_hash(self, file_path: str) -> str | None:
        """Get git hash (blob SHA-1) for a file.

        Args:
            file_path: Path to file (relative to repo root)

        Returns:
            Git blob hash or None

        """
        if not self.is_git_repo():
            return None

        try:
            result = await self._run_git_command(["hash-object", file_path])
            if result and result.strip():
                return result.strip()
        except Exception as e:
            self.logger.debug("Error getting file hash: %s", e)

        return None

    async def get_file_at_ref(self, file_path: str, ref: str) -> bytes | None:
        """Get file contents at a specific git ref.

        Args:
            file_path: Path to file (relative to repo root)
            ref: Git commit hash/ref

        Returns:
            File contents as bytes or None

        """
        if not self.is_git_repo():
            return None

        try:
            cmd = ["git", "show", f"{ref}:{file_path}"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.folder_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                return stdout
            error_msg = stderr.decode("utf-8", errors="ignore")
            self.logger.debug("Error getting file at ref: %s", error_msg)
        except Exception as e:
            self.logger.debug("Error getting file at ref: %s", e)

        return None

    async def _run_git_command(
        self, args: list[str], capture_output: bool = True
    ) -> str | None:
        """Run a git command and return output.

        Args:
            args: Git command arguments
            capture_output: Whether to capture output

        Returns:
            Command output as string or None

        Raises:
            GitVersioningError: If command fails

        """
        try:
            cmd = ["git"] + args
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.folder_path),
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
            )

            if capture_output:
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    return stdout.decode("utf-8", errors="ignore")
                error_msg = stderr.decode("utf-8", errors="ignore")
                self.logger.debug("Git command failed: %s", error_msg)
                return None
            await process.wait()
            return None if process.returncode != 0 else ""

        except FileNotFoundError:
            msg = "Git command not found. Is git installed?"
            raise GitVersioningError(msg) from None
        except Exception as e:
            msg = f"Error running git command: {e}"
            raise GitVersioningError(msg) from e

    def get_repo_info(self) -> dict[str, Any]:
        """Get git repository information.

        Returns:
            Dictionary with repo info (remote_url, branch, etc.)

        """
        if not self.is_git_repo():
            return {}

        info: dict[str, Any] = {}

        try:
            # Get remote URL
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to use run_coroutine_threadsafe
                # For now, return basic info
                info["is_git_repo"] = True
            else:
                remote_url = asyncio.run(
                    self._run_git_command(["config", "--get", "remote.origin.url"])
                )
                if remote_url:
                    info["remote_url"] = remote_url.strip()

                # Get current branch
                branch = asyncio.run(
                    self._run_git_command(
                        ["rev-parse", "--abbrev-ref", "HEAD"]
                    )
                )
                if branch:
                    info["branch"] = branch.strip()

        except Exception as e:
            self.logger.debug("Error getting repo info: %s", e)

        info["is_git_repo"] = True
        return info

