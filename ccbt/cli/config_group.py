"""Shared Click ``config`` group (avoids circular imports with extended commands)."""

from __future__ import annotations

import click


@click.group()
def config():
    """Manage configuration commands."""
