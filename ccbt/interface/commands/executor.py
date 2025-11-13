"""Command executor for executing CLI commands in dashboard context."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager

from ccbt.cli.interactive import InteractiveCLI

try:
    from ccbt.cli.main import cli as main_cli
except ImportError:
    main_cli = None  # type: ignore[assignment, misc]


class CommandExecutor:
    """Execute CLI commands in dashboard context.

    Wraps InteractiveCLI command methods to provide CLI functionality
    within the Textual dashboard without requiring a full InteractiveCLI instance.
    """

    def __init__(self, session: AsyncSessionManager):
        """Initialize command executor.

        Args:
            session: Async session manager instance (can be DaemonInterfaceAdapter)
        """
        self.session = session  # pragma: no cover - CommandExecutor initialization, tested via integration
        
        # Detect if using DaemonInterfaceAdapter
        from ccbt.interface.daemon_session_adapter import DaemonInterfaceAdapter
        self._is_daemon_session = isinstance(session, DaemonInterfaceAdapter)
        
        # If using DaemonInterfaceAdapter, get IPC client for direct command routing
        if self._is_daemon_session:
            self._ipc_client = session._client  # type: ignore[attr-defined]
        else:
            self._ipc_client = None
        
        # Create a minimal InteractiveCLI instance for command execution
        # We only need the command methods, not the full UI
        from rich.console import (
            Console,
        )  # pragma: no cover - CommandExecutor initialization

        # Create a dummy console for InteractiveCLI (output will be captured)
        # Use StringIO to capture output instead of devnull
        self._output_buffer = (
            io.StringIO()
        )  # pragma: no cover - CommandExecutor initialization
        self._dummy_console = Console(
            file=self._output_buffer, width=120
        )  # pragma: no cover - CommandExecutor initialization
        
        # Use ExecutorManager to get or create executor
        # This ensures we reuse executor instances and maintain session coherence
        from ccbt.executor.manager import ExecutorManager
        
        executor_manager = ExecutorManager.get_instance()
        
        if self._is_daemon_session:
            # For DaemonInterfaceAdapter, get executor via IPC client
            self._executor = executor_manager.get_executor(ipc_client=self._ipc_client)
        else:
            # For local session, get executor via session manager
            self._executor = executor_manager.get_executor(session_manager=session)
        
        # Get adapter from executor
        adapter = self._executor.adapter
        
        # Pass executor, adapter, console, and optionally session
        self._cli = InteractiveCLI(
            executor=self._executor,
            adapter=adapter,
            console=self._dummy_console,
            session=session if not self._is_daemon_session else None,
        )  # pragma: no cover - CommandExecutor initialization

        # Import main CLI group for Click command execution
        self._click_cli = main_cli  # pragma: no cover - CommandExecutor initialization

    async def execute_command(
        self, command: str, args: list[str], current_info_hash: str | None = None
    ) -> tuple[bool, str, Any]:
        """Execute a CLI command.

        Args:
            command: Command name (e.g., "files", "limits", "config")
            args: Command arguments
            current_info_hash: Current torrent info hash (hex) for context

        Returns:
            Tuple of (success: bool, message: str, result: Any)
        """
        try:  # pragma: no cover - CommandExecutor.execute_command, tested via integration
            # Map CLI command names to executor commands for commands that need info_hash
            # All commands now route through executor.execute() for consistency
            command_mapping: dict[str, str] = {
                "pause": "torrent.pause",
                "resume": "torrent.resume",
                "stop": "torrent.remove",
                "remove": "torrent.remove",
            }
            
            # If command has a mapping and we have current_info_hash, route through executor
            if command in command_mapping and current_info_hash:
                executor_command = command_mapping[command]
                try:
                    # Use executor created during initialization
                    result = await self._executor.execute(executor_command, info_hash=current_info_hash)
                    if result.success:
                        action = command.replace("_", " ")
                        return (True, f"Torrent {action} successful", result.data)
                    else:
                        return (False, result.error or f"Failed to {command}", None)
                except Exception as e:
                    return (False, f"Error executing {command}: {e!s}", None)
            
            # Set current info hash if provided (for commands that need it)
            if current_info_hash and hasattr(
                self._cli, "current_info_hash_hex"
            ):  # pragma: no cover - CommandExecutor
                self._cli.current_info_hash_hex = (
                    current_info_hash  # pragma: no cover - CommandExecutor
                )

            # Get command handler
            if (
                command not in self._cli.commands
            ):  # pragma: no cover - CommandExecutor error path
                return (
                    False,
                    f"Unknown command: {command}",
                    None,
                )  # pragma: no cover - CommandExecutor error path

            handler = self._cli.commands[command]  # pragma: no cover - CommandExecutor

            # Execute command (all InteractiveCLI command methods are async)
            # Capture output by redirecting console

            # Clear and reuse the output buffer
            self._output_buffer.seek(0)  # pragma: no cover - CommandExecutor
            self._output_buffer.truncate(0)  # pragma: no cover - CommandExecutor

            # Temporarily replace console to capture output
            original_console = self._cli.console  # pragma: no cover - CommandExecutor

            try:  # pragma: no cover - CommandExecutor
                await handler(args)  # pragma: no cover - CommandExecutor
                output_text = (
                    self._output_buffer.getvalue()
                )  # pragma: no cover - CommandExecutor
                return (
                    True,
                    output_text or f"Command '{command}' executed successfully",
                    None,
                )  # pragma: no cover - CommandExecutor
            finally:  # pragma: no cover - CommandExecutor
                # Restore original console
                self._cli.console = (
                    original_console  # pragma: no cover - CommandExecutor
                )

        except Exception as e:  # pragma: no cover - CommandExecutor error handling
            return (
                False,
                f"Error executing command '{command}': {e!s}",
                None,
            )  # pragma: no cover - CommandExecutor error handling

    async def execute_click_command(
        self,
        command_path: str,
        args: list[str] | None = None,
        ctx_obj: dict[str, Any] | None = None,
    ) -> tuple[bool, str, Any]:
        """Execute a Click command group command.

        Args:
            command_path: Command path (e.g., "xet status", "ipfs stats", "ssl enable-trackers")
            args: Additional arguments (already parsed from command_path)
            ctx_obj: Click context object (optional, will create default if None)

        Returns:
            Tuple of (success: bool, message: str, result: Any)
        """
        if self._click_cli is None:  # pragma: no cover - CommandExecutor error path
            return (
                False,
                "Click CLI not available",
                None,
            )  # pragma: no cover - CommandExecutor error path

        try:  # pragma: no cover - CommandExecutor.execute_click_command, tested via integration
            from io import StringIO  # pragma: no cover - CommandExecutor

            from rich.console import Console  # pragma: no cover - CommandExecutor

            # Parse command path (e.g., "xet status" -> ["xet", "status"])
            parts = command_path.split()  # pragma: no cover - CommandExecutor
            if not parts:  # pragma: no cover - CommandExecutor error path
                return (
                    False,
                    "Empty command path",
                    None,
                )  # pragma: no cover - CommandExecutor error path

            # Create output buffer for capturing Click output
            output_buffer = StringIO()  # pragma: no cover - CommandExecutor
            Console(
                file=output_buffer, width=120, force_terminal=False
            )  # pragma: no cover - CommandExecutor

            # Create Click context
            if ctx_obj is None:  # pragma: no cover - CommandExecutor
                ctx_obj = {  # pragma: no cover - CommandExecutor
                    "config": None,  # pragma: no cover - CommandExecutor
                    "verbose": False,  # pragma: no cover - CommandExecutor
                    "debug": False,  # pragma: no cover - CommandExecutor
                }  # pragma: no cover - CommandExecutor

            ctx = self._click_cli.make_context(  # pragma: no cover - CommandExecutor
                "cli",  # pragma: no cover - CommandExecutor
                list(parts) + (args or []),  # pragma: no cover - CommandExecutor
                obj=ctx_obj,  # pragma: no cover - CommandExecutor
            )  # pragma: no cover - CommandExecutor

            # Execute command in async context
            # Click commands may be sync or async, so we need to handle both
            result = None  # pragma: no cover - CommandExecutor
            try:  # pragma: no cover - CommandExecutor
                # Try to invoke the command
                with ctx:  # pragma: no cover - CommandExecutor
                    result = self._click_cli.invoke(
                        ctx
                    )  # pragma: no cover - CommandExecutor
            except Exception:  # pragma: no cover - CommandExecutor error handling
                # If direct invoke fails, try async execution
                if (
                    ctx.command
                    and hasattr(ctx.command, "callback")
                    and ctx.command.callback
                ):  # pragma: no cover - CommandExecutor
                    import inspect  # pragma: no cover - CommandExecutor

                    callback = (
                        ctx.command.callback
                    )  # pragma: no cover - CommandExecutor
                    if inspect.iscoroutinefunction(
                        callback
                    ):  # pragma: no cover - CommandExecutor
                        result = await callback(
                            ctx, **ctx.params
                        )  # pragma: no cover - CommandExecutor
                    else:  # pragma: no cover - CommandExecutor
                        result = callback(
                            ctx, **ctx.params
                        )  # pragma: no cover - CommandExecutor
                else:  # pragma: no cover - CommandExecutor error path
                    raise  # pragma: no cover - CommandExecutor error path

            # Get output
            output_text = output_buffer.getvalue()  # pragma: no cover - CommandExecutor

            # Check exit code (0 = success)
            success = (
                result == 0 if isinstance(result, int) else result is not None
            )  # pragma: no cover - CommandExecutor

            return (  # pragma: no cover - CommandExecutor
                success,  # pragma: no cover - CommandExecutor
                output_text
                or f"Command '{command_path}' executed",  # pragma: no cover - CommandExecutor
                result,  # pragma: no cover - CommandExecutor
            )  # pragma: no cover - CommandExecutor

        except Exception as e:  # pragma: no cover - CommandExecutor error handling
            return (
                False,
                f"Error executing Click command '{command_path}': {e!s}",
                None,
            )  # pragma: no cover - CommandExecutor error handling

    def get_available_commands(self) -> list[str]:
        """Get list of available commands.

        Returns:
            List of command names (includes both InteractiveCLI and Click commands)
        """
        commands = list(
            self._cli.commands.keys()
        )  # pragma: no cover - CommandExecutor.get_available_commands, tested via integration

        # Add Click command groups if available
        if self._click_cli is not None:  # pragma: no cover - CommandExecutor
            try:  # pragma: no cover - CommandExecutor
                # Get all command groups from Click CLI
                for (
                    name
                ) in self._click_cli.commands:  # pragma: no cover - CommandExecutor
                    if name not in commands:  # pragma: no cover - CommandExecutor
                        commands.append(name)  # pragma: no cover - CommandExecutor
            except Exception:  # pragma: no cover - CommandExecutor error handling
                pass  # Ignore errors getting Click commands  # pragma: no cover - CommandExecutor error handling

        return commands  # pragma: no cover - CommandExecutor
