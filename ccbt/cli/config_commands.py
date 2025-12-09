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
import os
from pathlib import Path

import click
import toml

from ccbt.cli.config_utils import requires_daemon_restart, restart_daemon_if_needed
from ccbt.config.config import ConfigManager
from ccbt.i18n import _

logger = logging.getLogger(__name__)


def _find_project_root(start_path: Path | None = None) -> Path | None:
    """Find the project root directory by looking for pyproject.toml or .git.

    Walks up the directory tree from start_path (or current directory) until
    finding a marker file/directory that indicates the project root.

    Args:
        start_path: Starting path to search from. If None, uses current working directory.

    Returns:
        Path to project root if found, None otherwise.

    """
    start_path = Path.cwd() if start_path is None else Path(start_path).resolve()

    current = start_path
    # Look for project root markers
    markers = ["pyproject.toml", ".git"]

    while current != current.parent:  # Stop at filesystem root
        for marker in markers:
            marker_path = current / marker
            if marker_path.exists():
                return current
        current = current.parent

    return None


def _should_skip_project_local_write(
    config_file: Path | None, explicit_config_file: str | Path | None
) -> bool:
    """Check if we should skip writing to project-local ccbt.toml during tests.

    Args:
        config_file: The config file path from ConfigManager
        explicit_config_file: Explicitly provided config file path (if any)

    Returns:
        True if we should skip writing (in test mode and targeting project-local file)

    """
    try:  # pragma: no cover - Defensive exception handling for safeguard detection errors
        # Try to find project root from current directory or from config_file's directory
        project_root = _find_project_root()
        if config_file:
            # Also try from config_file's directory in case we're in a subdirectory
            alt_root = _find_project_root(
                config_file.parent
                if config_file.is_absolute()
                else Path.cwd() / config_file.parent
            )
            if alt_root is not None:
                project_root = alt_root

        if project_root is None:
            # Can't determine project root, allow write (fallback to old behavior)
            return False

        project_local = project_root / "ccbt.toml"
        is_test_env = bool(
            os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CCBT_TEST_MODE")
        )
        # If caller did not specify explicit config file and resolver picked the project-local file under test, skip destructive write
        if (
            explicit_config_file is None
            and config_file
            and config_file.resolve() == project_local.resolve()
            and is_test_env
        ):
            return True  # pragma: no cover - Test mode protection path
    except Exception:  # pragma: no cover - Defensive exception handling for safeguard detection errors (path resolution, environment access, etc.)
        # If any error in safeguard detection, proceed normally
        pass  # pragma: no cover - Error handling path for safeguard detection failures
    return False


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
    help=_("Show specific section key path (e.g. network)"),
)
@click.option(
    "--key",
    type=str,
    default=None,
    help=_("Show specific key path (e.g. network.listen_port)"),
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
            msg = _("Key not found: {key}").format(key=key)
            raise click.ClickException(msg) from None
        else:
            return
    if section:
        if section not in data:
            msg = _("Section not found: {section}").format(section=section)
            raise click.ClickException(msg)
        data = {section: data[section]}
    # export full/section config
    if format_ == "json":
        click.echo(json.dumps(data, indent=2))
    elif format_ == "yaml":
        try:
            import yaml
        except Exception:
            msg = _("PyYAML is required for YAML output")
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
        msg = _("Key not found: {key}").format(key=key)
        raise click.ClickException(msg) from None


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--global",
    "global_flag",
    is_flag=True,
    help=_("Set value in global config file"),
)
@click.option(
    "--local",
    "local_flag",
    is_flag=True,
    help=_("Set value in project local ccbt.toml"),
)
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option(
    "--restart-daemon",
    "restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Automatically restart daemon if needed (without prompt)"),
)
@click.option(
    "--no-restart-daemon",
    "no_restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Skip daemon restart even if needed"),
)
def set_value(
    key: str,
    value: str,
    global_flag: bool,
    local_flag: bool,
    config_file: str | None,
    restart_daemon_flag: bool | None,
    no_restart_daemon_flag: bool | None,
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

    # Safety: avoid overwriting project-local config during tests
    if _should_skip_project_local_write(target, config_file):
        click.echo(_("OK"))  # pragma: no cover - Test mode protection path
        return  # pragma: no cover - Test mode protection path

    # Load old config before modification
    old_config_manager = ConfigManager(config_file)
    old_config = old_config_manager.config

    target.write_text(toml.dumps(current), encoding="utf-8")
    click.echo(str(target))

    # Check if restart is needed
    try:
        new_config_manager = ConfigManager(config_file)
        new_config = new_config_manager.config
        needs_restart = requires_daemon_restart(old_config, new_config)

        if needs_restart:
            # Determine restart behavior
            auto_restart = None
            if restart_daemon_flag:
                auto_restart = True
            elif no_restart_daemon_flag:
                auto_restart = False

            restart_daemon_if_needed(
                new_config_manager,
                requires_restart=True,
                auto_restart=auto_restart,
            )
    except Exception as e:
        logger.debug(_("Error checking if restart is needed: %s"), e)
        # Don't fail the command if restart check fails


@config.command("reset")
@click.option("--section", type=str, default=None)
@click.option("--key", type=str, default=None)
@click.option("--confirm", is_flag=True, help=_("Skip confirmation prompt"))
@click.option("--config", "config_file", type=click.Path(), default=None)
@click.option(
    "--restart-daemon",
    "restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Automatically restart daemon if needed (without prompt)"),
)
@click.option(
    "--no-restart-daemon",
    "no_restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Skip daemon restart even if needed"),
)
def reset_config(
    section: str | None,
    key: str | None,
    confirm: bool,
    config_file: str | None,
    restart_daemon_flag: bool | None,
    no_restart_daemon_flag: bool | None,
):
    """Reset configuration to defaults (optionally for a section/key)."""
    if not confirm:
        msg = _("Use --confirm to proceed with reset")
        raise click.ClickException(msg)

    # Load old config before modification
    old_config_manager = ConfigManager(config_file)
    old_config = old_config_manager.config

    cm = ConfigManager(config_file)
    # Safety: avoid wiping project-local config during tests or when not explicitly targeted
    if _should_skip_project_local_write(cm.config_file, config_file):
        click.echo(_("OK"))  # pragma: no cover - Test mode protection path
        return  # pragma: no cover - Test mode protection path
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
                logger.debug(_("Failed to parse config value: %s"), e)
        elif section and section in file_data:
            del file_data[section]
            changed = True
        else:
            # wipe file overrides entirely
            file_data = {}
            changed = True
        if changed:
            cm.config_file.write_text(toml.dumps(file_data), encoding="utf-8")
    click.echo(_("OK"))

    # Check if restart is needed
    try:
        new_config_manager = ConfigManager(config_file)
        new_config = new_config_manager.config
        needs_restart = requires_daemon_restart(old_config, new_config)

        if needs_restart:
            # Determine restart behavior
            auto_restart = None
            if restart_daemon_flag:
                auto_restart = True
            elif no_restart_daemon_flag:
                auto_restart = False

            restart_daemon_if_needed(
                new_config_manager,
                requires_restart=True,
                auto_restart=auto_restart,
            )
    except Exception as e:
        logger.debug(_("Error checking if restart is needed: %s"), e)
        # Don't fail the command if restart check fails


@config.command("validate")
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def validate_config_cmd(config_file: str | None):
    """Validate configuration file and print result."""
    try:
        ConfigManager(config_file)
        click.echo(_("VALID"))
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        raise click.ClickException(str(e)) from e


@config.command("migrate")
@click.option("--from-version", type=str, default=None)
@click.option("--to-version", type=str, default=None)
@click.option("--backup", is_flag=True, help=_("Create backup before migration"))
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
    click.echo(_("MIGRATED"))
