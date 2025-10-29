"""Extended configuration management CLI commands for ccBitTorrent.

Adds advanced commands:
- config schema
- config template
- config profile
- config backup
- config diff
- config capabilities
- config auto-tune
- config export
- config import
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click
import toml
from rich.console import Console
from rich.table import Table

from ccbt.config import ConfigManager
from ccbt.config_backup import ConfigBackup
from ccbt.config_capabilities import SystemCapabilities
from ccbt.config_conditional import ConditionalConfig
from ccbt.config_diff import ConfigDiff
from ccbt.config_schema import ConfigSchema
from ccbt.config_templates import ConfigProfiles, ConfigTemplates

logger = logging.getLogger(__name__)
console = Console()


@click.group(name="config-extended")
def config_extended():
    """Extended configuration management commands."""


@config_extended.command("schema")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["json", "yaml"]),
    default="json",
    help="Output format",
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="Specific model to generate schema for (e.g., Config, NetworkConfig)",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def schema_cmd(format_: str, model: str | None, output: str | None):
    """Generate JSON schema for configuration models."""
    try:
        if model:
            # Generate schema for specific model
            # Import the model dynamically
            from ccbt.models import Config

            if hasattr(Config, model):
                model_class = getattr(Config, model)
                schema = ConfigSchema.generate_schema(model_class)
            else:
                click.echo(f"Model '{model}' not found in Config")
                return
        else:
            # Generate full schema
            schema = ConfigSchema.generate_full_schema()

        # Format output
        if format_ == "yaml":
            try:
                import yaml  # type: ignore[import-untyped]

                output_text = yaml.safe_dump(schema, sort_keys=False)
            except ImportError:
                click.echo("PyYAML is required for YAML output")
                return
        else:
            output_text = json.dumps(schema, indent=2)

        # Output
        if output:
            Path(output).write_text(output_text, encoding="utf-8")
            click.echo(f"Schema written to {output}")
        else:
            click.echo(output_text)

    except Exception as e:
        click.echo(f"Error generating schema: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("template")
@click.argument("template_name")
@click.option(
    "--apply",
    is_flag=True,
    help="Apply template to current configuration",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path for template config",
)
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def template_cmd(
    template_name: str,
    apply: bool,
    output: str | None,
    config_file: str | None,
):
    """Manage configuration templates."""
    try:
        # Validate template
        is_valid, errors = ConfigTemplates.validate_template(template_name)
        if not is_valid:
            click.echo(f"Invalid template '{template_name}': {', '.join(errors)}")
            return

        # Get template info
        template_config = ConfigTemplates.get_template(template_name)
        if not template_config:
            click.echo(f"Template '{template_name}' not found")
            return

        # Get template metadata
        template_metadata = ConfigTemplates.TEMPLATES.get(template_name)
        if template_metadata:
            click.echo(f"Template: {template_metadata['name']}")
            click.echo(f"Description: {template_metadata['description']}")
        else:
            click.echo(f"Template: {template_name}")

        if apply:
            # Apply template to current config
            cm = ConfigManager(config_file)
            config_data = cm.config.model_dump(mode="json")
            applied_config = ConfigTemplates.apply_template(config_data, template_name)

            # Save to file
            target_path = Path(output) if output else Path.cwd() / "ccbt.toml"

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(toml.dumps(applied_config), encoding="utf-8")
            click.echo(f"Template applied to {target_path}")
        elif output:
            # Show template configuration
            Path(output).write_text(toml.dumps(template_config), encoding="utf-8")
            click.echo(f"Template config written to {output}")
        else:
            click.echo(toml.dumps(template_config))

    except Exception as e:
        click.echo(f"Error with template: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("profile")
@click.argument("profile_name")
@click.option(
    "--apply",
    is_flag=True,
    help="Apply profile to current configuration",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path for profile config",
)
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def profile_cmd(
    profile_name: str,
    apply: bool,
    output: str | None,
    config_file: str | None,
):
    """Manage configuration profiles."""
    try:
        # Validate profile
        is_valid, errors = ConfigProfiles.validate_profile(profile_name)
        if not is_valid:
            click.echo(f"Invalid profile '{profile_name}': {', '.join(errors)}")
            return

        # Get profile info
        profile_config = ConfigProfiles.get_profile(profile_name)
        if not profile_config:
            click.echo(f"Profile '{profile_name}' not found")
            return

        # Get profile metadata
        profile_metadata = ConfigProfiles.PROFILES.get(profile_name)
        if profile_metadata:
            click.echo(f"Profile: {profile_metadata['name']}")
            click.echo(f"Description: {profile_metadata['description']}")
            click.echo(f"Templates: {', '.join(profile_metadata['templates'])}")
        else:
            click.echo(f"Profile: {profile_name}")

        if apply:
            # Apply profile to current config
            cm = ConfigManager(config_file)
            config_data = cm.config.model_dump(mode="json")
            applied_config = ConfigProfiles.apply_profile(config_data, profile_name)

            # Save to file
            target_path = Path(output) if output else Path.cwd() / "ccbt.toml"

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(toml.dumps(applied_config), encoding="utf-8")
            click.echo(f"Profile applied to {target_path}")
        else:
            # Show profile configuration
            profile_config = ConfigProfiles.apply_profile({}, profile_name)
            if output:
                Path(output).write_text(toml.dumps(profile_config), encoding="utf-8")
                click.echo(f"Profile config written to {output}")
            else:
                click.echo(toml.dumps(profile_config))

    except Exception as e:
        click.echo(f"Error with profile: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("backup")
@click.option(
    "--description",
    "-d",
    type=str,
    default="Manual backup",
    help="Backup description",
)
@click.option(
    "--compress",
    is_flag=True,
    default=True,
    help="Compress backup",
)
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def backup_cmd(description: str, compress: bool, config_file: str | None):
    """Create configuration backup."""
    try:
        cm = ConfigManager(config_file)
        if not cm.config_file:
            click.echo("No configuration file to backup")
            return

        backup_manager = ConfigBackup()

        success, backup_path, log_messages = backup_manager.create_backup(
            cm.config_file,
            description=description,
            compress=compress,
        )

        if success:
            click.echo(f"Backup created: {backup_path}")
            for message in log_messages:
                click.echo(f"  {message}")
        else:
            click.echo("Backup failed")
            for message in log_messages:
                click.echo(f"  {message}")

    except Exception as e:
        click.echo(f"Error creating backup: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("restore")
@click.argument("backup_file", type=click.Path(exists=True))
@click.option(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option("--config", "config_file", type=click.Path(), default=None)
def restore_cmd(backup_file: str, confirm: bool, config_file: str | None):
    """Restore configuration from backup."""
    try:
        if not confirm:
            click.echo("Use --confirm to proceed with restore")
            return

        backup_manager = ConfigBackup()
        success, log_messages = backup_manager.restore_backup(
            Path(backup_file),
            target_file=Path(config_file) if config_file else None,
        )

        if success:
            click.echo(f"Configuration restored from {backup_file}")
            for message in log_messages:
                click.echo(f"  {message}")
        else:
            click.echo("Restore failed")
            for message in log_messages:
                click.echo(f"  {message}")

    except Exception as e:
        click.echo(f"Error restoring backup: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("list-backups")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_backups_cmd(format_: str):
    """List available configuration backups."""
    try:
        backup_manager = ConfigBackup()
        backups = backup_manager.list_backups()

        if not backups:
            click.echo("No backups found")
            return

        if format_ == "json":
            click.echo(json.dumps(backups, indent=2))
        else:
            # Create table
            table = Table(title="Configuration Backups")
            table.add_column("File", style="cyan")
            table.add_column("Timestamp", style="green")
            table.add_column("Description", style="blue")
            table.add_column("Size", style="magenta")

            for backup in backups:
                table.add_row(
                    backup["file"],
                    backup["timestamp"],
                    backup["description"],
                    f"{backup['size']:,} bytes",
                )

            console.print(table)

    except Exception as e:
        click.echo(f"Error listing backups: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("diff")
@click.argument("config1", type=click.Path(exists=True))
@click.argument("config2", type=click.Path(exists=True))
@click.option(
    "--format",
    "format_",
    type=click.Choice(["unified", "json"]),
    default="unified",
    help="Diff format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path",
)
def diff_cmd(config1: str, config2: str, format_: str, output: str | None):
    """Compare two configuration files."""
    try:
        # ConfigDiff instance is not required; use classmethod compare_files
        diff_result = ConfigDiff.compare_files(Path(config1), Path(config2))

        if output:
            Path(output).write_text(json.dumps(diff_result, indent=2), encoding="utf-8")
            click.echo(f"Diff written to {output}")
        elif format_ == "json":
            click.echo(json.dumps(diff_result, indent=2))
        else:
            # Unified format
            click.echo("Configuration differences:")
            for key, value in diff_result.items():
                click.echo(f"{key}: {value}")

    except Exception as e:
        click.echo(f"Error comparing configs: {e}")
        raise click.ClickException(str(e)) from e


def _print_capabilities_table() -> None:
    capabilities = SystemCapabilities()
    all_caps = capabilities.get_all_capabilities()

    table = Table(title="System Capabilities")
    table.add_column("Capability", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="blue")

    for cap_name, cap_value in all_caps.items():
        if isinstance(cap_value, bool):
            status = "Yes" if cap_value else "No"
            details = "Supported" if cap_value else "Not supported"
        elif isinstance(cap_value, dict):
            status = "Yes" if any(cap_value.values()) else "No"
            details = f"{len(cap_value)} features"
        elif isinstance(cap_value, list):
            status = "Yes" if cap_value else "No"
            details = f"{len(cap_value)} items"
        else:
            status = "Yes"
            details = str(cap_value)

        table.add_row(cap_name, status, details)

    console.print(table)


def _print_capabilities_summary() -> None:
    capabilities = SystemCapabilities()
    summary = capabilities.get_capability_summary()

    table = Table(title="System Capabilities Summary")
    table.add_column("Capability", style="cyan")
    table.add_column("Supported", style="green")

    for cap_name, supported in summary.items():
        table.add_row(cap_name, "Yes" if supported else "No")

    console.print(table)


@config_extended.group("capabilities", invoke_without_command=True)
@click.pass_context
def capabilities_group(ctx):
    """Manage system capabilities."""
    # Default behavior: show table when no subcommand provided
    if ctx.invoked_subcommand is None:
        _print_capabilities_table()


@capabilities_group.command("show")
def capabilities_show_cmd():
    """Show detailed system capabilities."""
    _print_capabilities_table()


@capabilities_group.command("summary")
def capabilities_summary_cmd():
    """Show a summary of key capabilities."""
    _print_capabilities_summary()


@config_extended.command("auto-tune")
@click.option(
    "--apply",
    is_flag=True,
    help="Apply auto-tuning to current configuration",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path for tuned config",
)
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def auto_tune_cmd(apply: bool, output: str | None, config_file: str | None):
    """Auto-tune configuration based on system capabilities."""
    try:
        cm = ConfigManager(config_file)
        conditional_config = ConditionalConfig()

        if apply:
            # Apply auto-tuning
            tuned_config, warnings = conditional_config.adjust_for_system(cm.config)

            # Show warnings
            if warnings:
                click.echo("Auto-tuning warnings:")
                for warning in warnings:
                    click.echo(f"  {warning}")

            # Save tuned configuration
            target_path = Path(output) if output else Path.cwd() / "ccbt_tuned.toml"

            config_data = tuned_config.model_dump(mode="json")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(toml.dumps(config_data), encoding="utf-8")
            click.echo(f"Auto-tuned configuration saved to {target_path}")
        else:
            # Show recommendations
            recommendations = conditional_config.get_system_recommendations()
            click.echo("System recommendations:")
            click.echo(json.dumps(recommendations, indent=2))

    except Exception as e:
        click.echo(f"Error with auto-tuning: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("export")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["toml", "json", "yaml"]),
    default="toml",
    help="Export format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    required=True,
    help="Output file path",
)
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
def export_cmd(format_: str, output: str, config_file: str | None):
    """Export configuration to file."""
    try:
        cm = ConfigManager(config_file)
        config_data = cm.config.model_dump(mode="json")

        # Format output
        if format_ == "json":
            output_text = json.dumps(config_data, indent=2)
        elif format_ == "yaml":
            try:
                import yaml  # type: ignore[import-untyped]

                output_text = yaml.safe_dump(config_data, sort_keys=False)
            except ImportError:
                click.echo("PyYAML is required for YAML export")
                return
        else:
            output_text = toml.dumps(config_data)

        # Write to file
        Path(output).write_text(output_text, encoding="utf-8")
        click.echo(f"Configuration exported to {output}")

    except Exception as e:
        click.echo(f"Error exporting configuration: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("import")
@click.argument("import_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "format_",
    type=click.Choice(["toml", "json", "yaml"]),
    default=None,
    help="Import format (auto-detect if not specified)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: overwrite current config)",
)
@click.option("--config", "config_file", type=click.Path(), default=None)
def import_cmd(
    import_file: str,
    format_: str | None,
    output: str | None,
    config_file: str | None,
):
    """Import configuration from file."""
    try:
        import_path = Path(import_file)

        # Auto-detect format if not specified
        if not format_:
            if import_path.suffix.lower() == ".json":
                format_ = "json"
            elif import_path.suffix.lower() in [".yml", ".yaml"]:
                format_ = "yaml"
            else:
                format_ = "toml"

        # Read file
        file_content = import_path.read_text(encoding="utf-8")

        # Parse based on format
        if format_ == "json":
            config_data = json.loads(file_content)
        elif format_ == "yaml":
            try:
                import yaml  # type: ignore[import-untyped]

                config_data = yaml.safe_load(file_content)
            except ImportError:
                click.echo("PyYAML is required for YAML import")
                return
        else:
            config_data = toml.loads(file_content)

        # Validate configuration
        try:
            # Validate by creating a Config object
            from ccbt.models import Config

            Config.model_validate(config_data)
        except Exception as e:
            click.echo(f"Invalid configuration: {e}")
            return

        # Save to target
        if output:
            target_path = Path(output)
        elif config_file:
            target_path = Path(config_file)
        else:
            target_path = Path.cwd() / "ccbt.toml"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(toml.dumps(config_data), encoding="utf-8")
        click.echo(f"Configuration imported to {target_path}")

    except Exception as e:
        click.echo(f"Error importing configuration: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("validate")
@click.option("--config", "config_file", type=click.Path(exists=True), default=None)
@click.option(
    "--detailed",
    is_flag=True,
    help="Show detailed validation results",
)
def validate_cmd(config_file: str | None, detailed: bool):
    """Validate configuration file."""
    try:
        cm = ConfigManager(config_file)
        config = cm.config

        # Basic validation (this happens during ConfigManager creation)
        click.echo("✓ Configuration is valid")

        if detailed:
            # Additional validation using conditional config
            conditional_config = ConditionalConfig()
            _is_valid, warnings = conditional_config.validate_against_system(config)

            if warnings:
                click.echo("Warnings:")
                for warning in warnings:
                    click.echo(f"  ⚠ {warning}")
            else:
                click.echo("✓ No system compatibility warnings")

    except Exception as e:
        click.echo(f"✗ Configuration validation failed: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("list-templates")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_templates_cmd(format_: str):
    """List available configuration templates."""
    try:
        templates = ConfigTemplates.list_templates()

        if format_ == "json":
            click.echo(json.dumps(templates, indent=2))
        else:
            # Create table
            table = Table(title="Available Templates")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="green")

            for template in templates:
                table.add_row(template["key"], template["description"])

            console.print(table)

    except Exception as e:
        click.echo(f"Error listing templates: {e}")
        raise click.ClickException(str(e)) from e


@config_extended.command("list-profiles")
@click.option(
    "--format",
    "format_",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list_profiles_cmd(format_: str):
    """List available configuration profiles."""
    try:
        profiles = ConfigProfiles.list_profiles()

        if format_ == "json":
            click.echo(json.dumps(profiles, indent=2))
        else:
            # Create table
            table = Table(title="Available Profiles")
            table.add_column("Name", style="cyan")
            table.add_column("Description", style="green")
            table.add_column("Templates", style="blue")

            for profile in profiles:
                templates_str = ", ".join(profile["templates"])
                table.add_row(profile["key"], profile["description"], templates_str)

            console.print(table)

    except Exception as e:
        click.echo(f"Error listing profiles: {e}")
        raise click.ClickException(str(e)) from e
