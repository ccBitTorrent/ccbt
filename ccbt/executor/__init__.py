"""Command executor module for unified CLI and daemon command execution.

This module provides a unified command execution layer that eliminates duplication
between CLI commands and daemon IPC handlers.
"""

from __future__ import annotations

from ccbt.executor.base import CommandContext, CommandExecutor, CommandResult
from ccbt.executor.executor import UnifiedCommandExecutor
from ccbt.executor.protocol_executor import ProtocolExecutor
from ccbt.executor.registry import CommandRegistry
from ccbt.executor.security_executor import SecurityExecutor
from ccbt.executor.session_adapter import (
    DaemonSessionAdapter,
    LocalSessionAdapter,
    SessionAdapter,
)
from ccbt.executor.session_executor import SessionExecutor

__all__ = [
    "CommandContext",
    "CommandExecutor",
    "CommandRegistry",
    "CommandResult",
    "DaemonSessionAdapter",
    "LocalSessionAdapter",
    "ProtocolExecutor",
    "SecurityExecutor",
    "SessionAdapter",
    "SessionExecutor",
    "UnifiedCommandExecutor",
]
