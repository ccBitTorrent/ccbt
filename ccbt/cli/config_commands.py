"""Configuration management CLI commands for ccBitTorrent.

Adds commands:
- config show
- config get
- config set
- config reset
- config validate
- config migrate
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click
import toml

from ccbt.config import ConfigManager

logger = logging.getLogger(__name__)


@click.group()
def config():
    """Configuration management commands."""


@config.command("show")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["toml", "json", "yaml"]),
    default="toml",
)
@click.option(
    "--section",
    type=str,
    default=None,
    help="Show specific section key path (e.g. network)",
)
@click.option(
    "--key",
    type=str,
    default=None,
    help="Show specific key path (e.g. network.listen_port)",
)
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def show_config(
    format_: str,
    section: str | None,
    key: str | None,
    config_file: str | None,
):
    """Show current configuration in the desired format."""
    cm = ConfigManager(config_file)
    data = cm.config.model_dump(mode="json")
    # filter by section/key
    if key:
        # nested key path
        parts = key.split(".")
        ref = data
        try:
            for p in parts:
                ref = ref[p]
            # output single value in JSON regardless of format
            click.echo(json.dumps(ref, indent=2))
        except Exception:
            msg = f"Key not found: {key}"
            raise click.ClickException(msg) from None
        else:
            return
    if section:
        if section not in data:
            msg = f"Section not found: {section}"
            raise click.ClickException(msg)
        data = {section: data[section]}
    # export full/section config
    if format_ == "json":
        click.echo(json.dumps(data, indent=2))
    elif format_ == "yaml":
        try:
            import yaml  # type: ignore[import-untyped]
        except Exception:
            msg = "PyYAML is required for YAML output"
            raise click.ClickException(msg) from None
        click.echo(yaml.safe_dump(data, sort_keys=False))
    else:
        click.echo(toml.dumps(data))


@config.command("get")
@click.argument("key")
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def get_value(key: str, config_file: str | None):
    """Get a specific configuration value by dotted path."""
    cm = ConfigManager(config_file)
    data = cm.config.model_dump(mode="json")
    ref = data
    try:
        for p in key.split("."):
            ref = ref[p]
        click.echo(json.dumps(ref, indent=2))
    except Exception:
        msg = f"Key not found: {key}"
        raise click.ClickException(msg) from None


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--global",
    "global_flag",
    is_flag=True,
    help="Set value in global config file",
)
@click.option(
    "--local",
    "local_flag",
    is_flag=True,
    help="Set value in project local ccbt.toml",
)
@click.option("--config", "config_file", type=click.Path(), default=None)
def set_value(
    key: str,
    value: str,
    global_flag: bool,
    local_flag: bool,
    config_file: str | None,
):
    """Set a configuration value and persist to TOML file.

    Precedence for destination: --config > --local (./ccbt.toml) > --global (~/.config/ccbt/ccbt.toml)
    """
    # choose target file
    if config_file:
        target = Path(config_file)
    elif local_flag:
        target = Path.cwd() / "ccbt.toml"
    elif global_flag:
        target = Path.home() / ".config" / "ccbt" / "ccbt.toml"
    else:
        # default local
        target = Path.cwd() / "ccbt.toml"

    target.parent.mkdir(parents=True, exist_ok=True)
    current: dict = {}
    if target.exists():
        try:
            current = toml.load(str(target))
        except Exception:
            current = {}

    def parse_value(raw: str):
        low = raw.lower()
        if low in {"true", "1", "yes", "on"}:
            return True
        if low in {"false", "0", "no", "off"}:
            return False
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw

    parts = key.split(".")
    ref = current
    for p in parts[:-1]:
        ref = ref.setdefault(p, {})
    ref[parts[-1]] = parse_value(value)

    target.write_text(toml.dumps(current), encoding="utf-8")
    click.echo(str(target))


@config.command("reset")
@click.option("--section", type=str, default=None)
@click.option("--key", type=str, default=None)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.option("--config", "config_file", type=click.Path(), default=None)
def reset_config(
    section: str | None,
    key: str | None,
    confirm: bool,
    config_file: str | None,
):
    """Reset configuration to defaults (optionally for a section/key)."""
    if not confirm:
        msg = "Use --confirm to proceed with reset"
        raise click.ClickException(msg)
    cm = ConfigManager(config_file)
    cm.config.model_dump(mode="json")
    # if section/key provided, just remove overrides from file
    if cm.config_file and cm.config_file.exists():
        file_data = toml.load(str(cm.config_file))
        changed = False
        if key:
            parts = key.split(".")
            ref = file_data
            try:
                for p in parts[:-1]:
                    ref = ref[p]
                if parts[-1] in ref:
                    del ref[parts[-1]]
                    changed = True
            except Exception as e:
                logger.debug("Failed to parse config value: %s", e)
        elif section and section in file_data:
            del file_data[section]
            changed = True
        else:
            # wipe file overrides entirely
            file_data = {}
            changed = True
        if changed:
            cm.config_file.write_text(toml.dumps(file_data), encoding="utf-8")
    click.echo("OK")


@config.command("validate")
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def validate_config_cmd(config_file: str | None):
    """Validate configuration file and print result."""
    try:
        _ = ConfigManager(config_file)
        click.echo("VALID")
    except Exception as e:
        raise click.ClickException(str(e)) from e


@config.command("migrate")
@click.option("--from-version", type=str, default=None)
@click.option("--to-version", type=str, default=None)
@click.option("--backup", is_flag=True, help="Create backup before migration")
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def migrate_config_cmd(
    from_version: str | None,  # noqa: ARG001
    to_version: str | None,  # noqa: ARG001
    backup: bool,
    config_file: str | None,
):
    """Migrate configuration between versions (no-op placeholder)."""
    # For now, this is a placeholder that just validates and echoes
    cm = ConfigManager(config_file)
    if backup and cm.config_file:
        bak = Path(str(cm.config_file) + ".bak")
        bak.write_text(cm.config_file.read_text(encoding="utf-8"), encoding="utf-8")
    click.echo("MIGRATED")
