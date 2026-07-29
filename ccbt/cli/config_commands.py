"""Configuration management CLI commands for ccBitTorrent.

Core commands:

- ``config show`` / ``get`` / ``set`` / ``apply`` / ``describe`` / ``reset``
- ``config validate`` / ``migrate``

Extended commands (same ``btbt config`` group; see ``config_commands_extended``) are
registered when this module finishes loading: ``schema``, ``import``, ``export``,
``template``, ``profile``, ``backup``, ``restore``, ``diff``, ``auto-tune``, etc.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Optional, Union

import click
import toml

from ccbt.cli.config_group import config
from ccbt.cli.config_utils import requires_daemon_restart, restart_daemon_if_needed
from ccbt.config.config import ConfigManager
from ccbt.config.config_cli_values import parse_cli_config_value, set_nested_dict
from ccbt.config.config_schema import ConfigDiscovery
from ccbt.i18n import _
from ccbt.utils.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def _find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
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
    config_file: Optional[Path], explicit_config_file: Optional[Union[str, Path]]
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


@config.command("show")
@click.option(
    "--format",
    "-f",
    "format_",
    type=click.Choice(["toml", "json", "yaml"]),
    default="toml",
)
@click.option(
    "--section",
    "-S",
    type=str,
    default=None,
    help=_("Show specific section key path (e.g. network)"),
)
@click.option(
    "--key",
    "-k",
    type=str,
    default=None,
    help=_("Show specific key path (e.g. network.listen_port)"),
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
def show_config(
    format_: str,
    section: Optional[str],
    key: Optional[str],
    config_file: Optional[str],
):
    """Show effective configuration (merged file, environment, and defaults).

    This prints resolved values only. For every option path with types and defaults,
    use ``btbt config describe`` (add ``--include-current`` to compare). For JSON
    Schema, use ``btbt config schema``. To merge a patch file into ``ccbt.toml``,
    use ``btbt config apply``.

    MSE / peer encryption (effective values): ``btbt config security-posture`` or
    ``btbt config show -S security -f json`` (see ``security.enable_encryption``,
    ``encryption_mode``) and ``network.enable_encryption`` (mirror).
    """
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


@config.command("security-posture")
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
def security_posture(config_file: Optional[str]):
    """Print effective MSE/PE and related security fields (file + env merged).

    Same merge order as ``config show``. Use this to verify why the session logs
    ``mse_enabled=`` (maps to ``security.enable_encryption``).
    """
    cm = ConfigManager(config_file)
    sec = cm.config.security
    net = cm.config.network
    out = {
        "security.enable_encryption": sec.enable_encryption,
        "security.encryption_mode": sec.encryption_mode,
        "security.encryption_allow_plain_fallback": sec.encryption_allow_plain_fallback,
        "security.encryption_dh_key_size": sec.encryption_dh_key_size,
        "network.enable_encryption": net.enable_encryption,
        "network.peer_quality_probation_timeout": net.peer_quality_probation_timeout,
    }
    click.echo(json.dumps(out, indent=2))


@config.command("peer-cap-provenance")
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
def peer_cap_provenance(config_file: Optional[str]) -> None:
    """Print max_peers_per_torrent resolution chain (file → profile → env → clamp).

    Same merge path as ``config show``. Does not include per-torrent overrides
    (those apply when a torrent session binds its peer manager).
    """
    cm = ConfigManager(config_file)
    prov = cm.max_peers_per_torrent_provenance
    if prov is None:
        click.echo(
            json.dumps(
                {
                    "error": "peer_cap_provenance_unavailable",
                    "hint": "Load failed before provenance was recorded.",
                },
                indent=2,
            )
        )
        return
    click.echo(json.dumps(prov.model_dump(mode="json"), indent=2))


@config.command("get")
@click.argument("key")
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
def get_value(key: str, config_file: Optional[str]):
    """Get one effective value by dotted path (same merge as ``config show``).

    See ``btbt config describe`` for all valid paths and defaults.
    """
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


@config.command("describe")
@click.option(
    "--format",
    "-f",
    "format_",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help=_("Output format for the option catalog"),
)
@click.option(
    "--section",
    "-S",
    type=str,
    default=None,
    help=_("Only options in this top-level section (e.g. network)"),
)
@click.option(
    "--path-prefix",
    "-p",
    type=str,
    default=None,
    help=_("Only paths starting with this prefix"),
)
@click.option(
    "--include-current",
    "-i",
    is_flag=True,
    help=_("Include effective runtime value from loaded config (file + env)"),
)
@click.option("-o", "--output", type=click.Path(), default=None)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
def describe_config(
    format_: str,
    section: Optional[str],
    path_prefix: Optional[str],
    include_current: bool,
    output: Optional[str],
    config_file: Optional[str],
):
    """List all configuration options (nested paths), types, defaults, descriptions.

    Complements ``config show`` / ``config get`` (values only) and
    ``btbt config schema`` (full JSON Schema). To change values use ``config set``
    or ``config apply`` / ``config import --mode merge``.
    """
    from ccbt.config.config_cli_values import get_nested_value

    rows = ConfigDiscovery.list_all_options_nested()
    if section:
        rows = [
            r
            for r in rows
            if r["section"] == section or r["path"].startswith(f"{section}.")
        ]
    if path_prefix:
        rows = [r for r in rows if r["path"].startswith(path_prefix)]

    current_data: dict = {}
    if include_current:
        cm = ConfigManager(config_file)
        current_data = cm.config.model_dump(mode="json")
        for r in rows:
            r["current"] = get_nested_value(current_data, r["path"])

    if format_ == "json":
        out = json.dumps(rows, indent=2, default=str)
    elif format_ == "yaml":
        try:
            import yaml
        except ImportError as e:
            raise click.ClickException(_("PyYAML is required for YAML output")) from e
        out = yaml.safe_dump(rows, sort_keys=False)
    else:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=_("Configuration options"))
        table.add_column(_("Path"), style="cyan", no_wrap=True)
        table.add_column(_("Type"), style="green")
        table.add_column(_("Required"), style="yellow")
        table.add_column(_("Default"), max_width=36)
        if include_current:
            table.add_column(_("Current"), max_width=36)
        table.add_column(_("Description"), max_width=48)
        for r in rows:
            row_cells = [
                r["path"],
                str(r["type"]),
                _("yes") if r["required"] else _("no"),
                json.dumps(r["default"], default=str)
                if r["default"] is not None
                else "",
            ]
            if include_current:
                cur = r.get("current", None)
                row_cells.append(
                    json.dumps(cur, default=str) if cur is not None else ""
                )
            row_cells.append((r.get("description") or "")[:2000])
            table.add_row(*row_cells)
        console = Console(record=True)
        console.print(table)
        out = console.export_text()

    if output:
        Path(output).write_text(out, encoding="utf-8")
        click.echo(_("Wrote catalog to {path}").format(path=output))
    else:
        click.echo(out)


@config.command("set")
@click.argument("key")
@click.argument("value", required=False, default=None)
@click.option(
    "--value",
    "-V",
    "value_opt",
    default=None,
    help=_(
        "Value to set (use for strings with spaces or JSON); overrides positional VALUE"
    ),
)
@click.option(
    "--dry-run",
    "-n",
    "dry_run",
    is_flag=True,
    help=_("Validate only; do not write the config file"),
)
@click.option(
    "--global",
    "-G",
    "global_flag",
    is_flag=True,
    help=_("Set value in global config file"),
)
@click.option(
    "--local",
    "-L",
    "local_flag",
    is_flag=True,
    help=_("Set value in project local ccbt.toml"),
)
@click.option("--config", "-c", "config_file", type=click.Path(), default=None)
@click.option(
    "--restart-daemon",
    "-R",
    "restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Automatically restart daemon if needed (without prompt)"),
)
@click.option(
    "--no-restart-daemon",
    "-N",
    "no_restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Skip daemon restart even if needed"),
)
def set_value(
    key: str,
    value: Optional[str],
    value_opt: Optional[str],
    dry_run: bool,
    global_flag: bool,
    local_flag: bool,
    config_file: Optional[str],
    restart_daemon_flag: Optional[bool],
    no_restart_daemon_flag: Optional[bool],
):
    """Set a configuration value and persist to TOML file.

    Values are parsed as JSON when valid (numbers, booleans, arrays, objects).
    Otherwise booleans, numbers, comma-separated lists (for known list paths), or strings.

    Precedence for destination: --config > --local (./ccbt.toml) > --global (~/.config/ccbt/ccbt.toml)

    After writing, effective runtime config still follows normal precedence: environment
    variables can override the same keys from the file. Use ``btbt config describe`` to
    list paths; use ``btbt config apply`` for multi-key patches.
    """
    raw = value_opt if value_opt is not None else value
    if raw is None:
        raise click.UsageError(
            _(
                "Provide a VALUE argument or use --value=... for values with spaces or JSON"
            )
        )

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

    proposed = copy.deepcopy(current)
    parsed = parse_cli_config_value(raw, key)
    set_nested_dict(proposed, key, parsed)

    validate_path = str(target) if target.exists() else config_file
    validate_cm = ConfigManager(validate_path)
    try:
        validate_cm.simulate_load_from_file_dict(proposed)
    except ConfigurationError as e:
        raise click.ClickException(str(e)) from e

    # Safety: avoid overwriting project-local config during tests
    if _should_skip_project_local_write(target, config_file):
        click.echo(_("OK"))  # pragma: no cover - Test mode protection path
        return  # pragma: no cover - Test mode protection path

    if dry_run:
        click.echo(_("OK (dry-run — configuration is valid)"))
        return

    # Load old config before modification
    old_config_manager = ConfigManager(config_file)
    old_config = old_config_manager.config

    target.write_text(toml.dumps(proposed), encoding="utf-8")
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


@config.command("apply")
@click.argument("input_file", required=False, type=click.Path(exists=True))
@click.option(
    "--format",
    "-f",
    "format_",
    type=click.Choice(["toml", "json", "yaml", "auto"]),
    default="auto",
    help=_("Patch file format (auto: infer from extension or try JSON then TOML)"),
)
@click.option(
    "--global",
    "-G",
    "global_flag",
    is_flag=True,
    help=_("Write merged config to global config file"),
)
@click.option(
    "--local",
    "-L",
    "local_flag",
    is_flag=True,
    help=_("Write merged config to project local ccbt.toml"),
)
@click.option("--config", "-c", "config_file", type=click.Path(), default=None)
@click.option(
    "--dry-run",
    "-n",
    "dry_run",
    is_flag=True,
    help=_("Validate merged file overlay only; do not write"),
)
@click.option(
    "--restart-daemon",
    "-R",
    "restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Automatically restart daemon if needed (without prompt)"),
)
@click.option(
    "--no-restart-daemon",
    "-N",
    "no_restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Skip daemon restart even if needed"),
)
def apply_config_patch(
    input_file: Optional[str],
    format_: str,
    global_flag: bool,
    local_flag: bool,
    config_file: Optional[str],
    dry_run: bool,
    restart_daemon_flag: Optional[bool],
    no_restart_daemon_flag: Optional[bool],
):
    """Merge a partial config object into the target TOML and validate before write.

    For a single key, prefer ``btbt config set``. For a full document replace, use
    ``btbt config import --mode replace``; for merge semantics similar to this command
    from a file, ``btbt config import --mode merge``. See ``btbt config describe`` for paths.
    """
    import sys

    from ccbt.config.config_templates import ConfigTemplates

    if input_file:
        raw = Path(input_file).read_text(encoding="utf-8")
        src = Path(input_file)
    else:
        raw = sys.stdin.read()
        src = None

    fmt = format_
    if fmt == "auto" and src is not None:
        suf = src.suffix.lower()
        if suf in {".yml", ".yaml"}:
            fmt = "yaml"
        elif suf == ".json":
            fmt = "json"
        elif suf == ".toml":
            fmt = "toml"

    if fmt == "auto":
        try:
            patch = json.loads(raw)
        except json.JSONDecodeError:
            patch = toml.loads(raw)
    elif fmt == "json":
        patch = json.loads(raw)
    elif fmt == "yaml":
        try:
            import yaml
        except ImportError as e:
            raise click.ClickException(_("PyYAML is required for YAML patches")) from e
        loaded = yaml.safe_load(raw)
        patch = loaded if isinstance(loaded, dict) else {}
    else:
        patch = toml.loads(raw)

    if not isinstance(patch, dict):
        raise click.ClickException(
            _("Patch must be a JSON/TOML object at the top level")
        )

    if config_file:
        target = Path(config_file)
    elif local_flag:
        target = Path.cwd() / "ccbt.toml"
    elif global_flag:
        target = Path.home() / ".config" / "ccbt" / "ccbt.toml"
    else:
        target = Path.cwd() / "ccbt.toml"

    target.parent.mkdir(parents=True, exist_ok=True)
    base: dict = {}
    if target.exists():
        try:
            base = toml.load(str(target))
        except Exception:
            base = {}

    merged = ConfigTemplates._deep_merge(base, patch)  # noqa: SLF001

    validate_path = str(target) if target.exists() else config_file
    validate_cm = ConfigManager(validate_path)
    try:
        validate_cm.simulate_load_from_file_dict(merged)
    except ConfigurationError as e:
        raise click.ClickException(str(e)) from e

    if _should_skip_project_local_write(target, config_file):
        click.echo(_("OK"))
        return

    if dry_run:
        click.echo(_("OK (dry-run — merged configuration is valid)"))
        return

    old_config_manager = ConfigManager(config_file)
    old_config = old_config_manager.config

    target.write_text(toml.dumps(merged), encoding="utf-8")
    click.echo(str(target))

    try:
        new_config_manager = ConfigManager(config_file)
        new_config = new_config_manager.config
        needs_restart = requires_daemon_restart(old_config, new_config)
        if needs_restart:
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


@config.command("reset")
@click.option("--section", "-S", type=str, default=None)
@click.option("--key", "-k", type=str, default=None)
@click.option("--confirm", "-y", is_flag=True, help=_("Skip confirmation prompt"))
@click.option("--config", "-c", "config_file", type=click.Path(), default=None)
@click.option(
    "--restart-daemon",
    "-R",
    "restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Automatically restart daemon if needed (without prompt)"),
)
@click.option(
    "--no-restart-daemon",
    "-N",
    "no_restart_daemon_flag",
    is_flag=True,
    default=None,
    help=_("Skip daemon restart even if needed"),
)
def reset_config(
    section: Optional[str],
    key: Optional[str],
    confirm: bool,
    config_file: Optional[str],
    restart_daemon_flag: Optional[bool],
    no_restart_daemon_flag: Optional[bool],
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
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help=_("Run additional system compatibility checks after model validation"),
)
def validate_config_cmd(config_file: Optional[str], detailed: bool):
    """Validate configuration file and print result."""
    try:
        from ccbt.config.config_conditional import ConditionalConfig

        cm = ConfigManager(config_file)
        if detailed:
            click.echo(_("✓ Configuration is valid"))
            conditional_config = ConditionalConfig()
            warnings = conditional_config.validate_against_system(cm.config)[1]
            if warnings:
                click.echo(_("Warnings:"))
                for warning in warnings:
                    click.echo(_("  ⚠ {warning}").format(warning=warning))
            else:
                click.echo(_("✓ No system compatibility warnings"))
        else:
            click.echo(_("VALID"))
    except Exception as e:  # pragma: no cover - CLI error handler, hard to trigger reliably in unit tests
        if detailed:
            click.echo(_("✗ Configuration validation failed: {e}").format(e=e))
        raise click.ClickException(str(e)) from e


@config.command("migrate")
@click.option("--from-version", "-F", type=str, default=None)
@click.option("--to-version", "-T", type=str, default=None)
@click.option("--backup", "-b", is_flag=True, help=_("Create backup before migration"))
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
)
def migrate_config_cmd(
    from_version: Optional[str],  # noqa: ARG001
    to_version: Optional[str],  # noqa: ARG001
    backup: bool,
    config_file: Optional[str],
):
    """Migrate configuration between versions (no-op placeholder)."""
    # For now, this is a placeholder that just validates and echoes
    cm = ConfigManager(config_file)
    if backup and cm.config_file:
        bak = Path(str(cm.config_file) + ".bak")
        bak.write_text(cm.config_file.read_text(encoding="utf-8"), encoding="utf-8")
    click.echo(_("MIGRATED"))


import ccbt.cli.config_commands_extended  # noqa: E402,F401 — attach extended subcommands
