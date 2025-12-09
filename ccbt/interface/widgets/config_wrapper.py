"""Wrapper widget to embed configuration screens in the tabbed interface.

This allows existing ConfigScreen classes to be used within the
tabbed interface without requiring full screen push.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ccbt.interface.commands.executor import CommandExecutor
    from ccbt.interface.data_provider import DataProvider
else:
    try:
        from ccbt.interface.commands.executor import CommandExecutor
        from ccbt.interface.data_provider import DataProvider
    except ImportError:
        CommandExecutor = None  # type: ignore[assignment, misc]
        DataProvider = None  # type: ignore[assignment, misc]

try:
    from textual.containers import Container, Vertical, Horizontal
    from textual.widgets import Static, DataTable, Button, Input, Switch, Select
except ImportError:
    # Fallback for when textual is not available
    class Container:  # type: ignore[no-redef]
        pass

    class Vertical:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Static:  # type: ignore[no-redef]
        pass

    class DataTable:  # type: ignore[no-redef]
        pass

    class Button:  # type: ignore[no-redef]
        pass

    class Input:  # type: ignore[no-redef]
        pass

    class Switch:  # type: ignore[no-redef]
        pass

    class Select:  # type: ignore[no-redef]
        pass

from ccbt.i18n import _
from ccbt.config.config_schema import ConfigSchema
from ccbt.interface.screens.config.widgets import ConfigValueEditor
from ccbt.interface.screens.config.widget_factory import (
    create_config_widget,
    get_widget_value,
    validate_widget_value,
)

logger = logging.getLogger(__name__)


class ConfigScreenWrapper(Container):  # type: ignore[misc]
    """Wrapper to embed config screen content in a container widget.
    
    This extracts the content from existing ConfigScreen classes
    and displays it within the tabbed interface without requiring a full screen push.
    """

    DEFAULT_CSS = """
    ConfigScreenWrapper {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
    }
    
    #config-content {
        height: 1fr;
        overflow-y: auto;
    }
    
    #config-sections {
        height: 1fr;
    }
    
    #config-editors {
        height: 1fr;
        overflow-y: auto;
    }
    
    #config-editors-title {
        height: 3;
        text-style: bold;
        padding: 1;
    }
    
    #config-editors-container {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    
    #config-editors-container Static {
        margin-top: 1;
        margin-bottom: 0;
    }
    
    #config-editors-container ConfigValueEditor {
        margin-bottom: 1;
    }
    
    #config-editors-container ConfigValueEditor.-changed {
        border: solid $warning;
    }
    
    #config-editors-container ConfigValueEditor.-invalid {
        border: solid $error;
    }
    
    #config-editors-container ConfigValueEditor.-valid {
        border: solid $success;
    }
    
    #config-editors-errors {
        height: auto;
        min-height: 3;
        max-height: 10;
        overflow-y: auto;
        padding: 1;
    }
    
    #config-actions {
        height: auto;
        padding: 1;
        align-horizontal: center;
    }
    
    #config-actions Button {
        margin-right: 1;
    }
    """
    
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("enter", "select", _("Select Section")),
        ("s", "save_config", _("Save Config")),
        ("escape", "cancel_editing", _("Cancel Editing")),
    ]

    def __init__(
        self,
        config_type: str,
        data_provider: DataProvider,
        command_executor: CommandExecutor,
        info_hash: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize config screen wrapper.

        Args:
            config_type: Type of config screen (e.g., "global", "torrent", "network", "bandwidth")
            data_provider: DataProvider instance for reading config
            command_executor: CommandExecutor instance for updating config
            info_hash: Optional torrent info hash for per-torrent config
        """
        super().__init__(*args, **kwargs)
        self._config_type = config_type
        self._data_provider = data_provider
        self._command_executor = command_executor
        self._info_hash = info_hash
        self._content_widget: Static | None = None
        self._sections_table: DataTable | None = None
        self._selected_section: str | None = None
        self._editors: dict[str, ConfigValueEditor] = {}
        self._editors_container: Container | None = None
        self._original_values: dict[str, Any] = {}
        self._editing_mode = False
        self._changed_values: set[str] = set()

    def compose(self) -> Any:  # pragma: no cover
        """Compose the config wrapper."""
        with Vertical(id="config-content"):
            if self._config_type == "global":
                # For global config, show sections table
                yield DataTable(id="config-sections", zebra_stripes=True)
                yield Static(_("Select a section to configure"), id="config-info")
                # Container for form editors (hidden initially)
                with Vertical(id="config-editors", display=False):
                    yield Static(id="config-editors-title")
                    yield Container(id="config-editors-container")
                    yield Static(id="config-editors-errors")
            elif self._config_type == "torrent" and self._info_hash:
                # For per-torrent config, show editors container directly
                with Vertical(id="config-editors", display=True):
                    yield Static(_("Per-Torrent Configuration"), id="config-editors-title")
                    yield Container(id="config-editors-container")
                    yield Static(id="config-editors-errors")
            else:
                # For other config types, show placeholder
                yield Static(_("Loading configuration..."), id="config-placeholder")
        
        # Action buttons at bottom
        with Vertical(id="config-actions"):
            yield Button(_("Save Configuration"), id="save-button", variant="primary")
            yield Button(_("Cancel Editing"), id="cancel-button", variant="default", display=False)

    def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the config wrapper and populate content."""
        try:
            if self._config_type == "global":
                self._sections_table = self.query_one("#config-sections", DataTable)  # type: ignore[attr-defined]
                self._content_widget = self.query_one("#config-info", Static)  # type: ignore[attr-defined]
                self._populate_global_sections()
                # Update info message
                if self._content_widget:
                    from rich.panel import Panel
                    self._content_widget.update(
                        Panel(
                            _("Select a section to configure. Press Enter to edit, Escape to go back."),
                            title=_("Global Configuration"),
                        )
                    )
                # CRITICAL FIX: Ensure table receives focus
                if self._sections_table:
                    self.call_later(self._sections_table.focus)  # type: ignore[attr-defined]
            else:
                self._content_widget = self.query_one("#config-placeholder", Static)  # type: ignore[attr-defined]
                self._populate_config_content()
        except Exception as e:
            logger.debug("Error mounting config wrapper: %s", e)
            # Show error message if possible
            try:
                if self._content_widget:
                    from rich.panel import Panel
                    self._content_widget.update(
                        Panel(
                            _("Error loading configuration: {error}").format(error=str(e)),
                            title=_("Error"),
                            border_style="red",
                        )
                    )
            except Exception:
                pass

    def _populate_global_sections(self) -> None:  # pragma: no cover
        """Populate global config sections table.
        
        Uses the same sections as GlobalConfigMainScreen but displays
        them in a container widget instead of a full screen.
        """
        if not self._sections_table:
            return
        
        try:
            self._sections_table.add_columns(_("Section"), _("Description"), _("Modified"))
            self._sections_table.cursor_type = "row"
            
            # Define config sections matching GlobalConfigMainScreen
            # (matching the sections list from GlobalConfigMainScreen.on_mount)
            sections = [
                ("network", "Network configuration (connections, timeouts, rate limits)"),
                ("network.protocol_v2", "BitTorrent Protocol v2 (BEP 52) settings"),
                ("network.utp", "uTP transport protocol (BEP 29) settings"),
                ("disk", "Disk I/O configuration (preallocation, hashing, checkpoints)"),
                ("disk.attributes", "File attributes (BEP 47: symlinks, executable, hidden)"),
                ("disk.xet", "Xet protocol (content-defined chunking) settings"),
                ("strategy", "Piece selection strategy configuration"),
                ("discovery", "Peer discovery (DHT, PEX, trackers)"),
                ("observability", "Logging, metrics, and tracing"),
                ("limits", "Rate limit configuration"),
                ("security", "Security settings (encryption, IP filtering, SSL)"),
                ("security.ip_filter", "IP filtering configuration"),
                ("security.ssl", "SSL/TLS settings for trackers and peers"),
                ("proxy", "Proxy configuration"),
                ("ml", "Machine learning configuration"),
                ("dashboard", "Dashboard/web UI configuration"),
                ("queue", "Torrent queue management"),
                ("nat", "NAT traversal configuration"),
                ("ipfs", "IPFS protocol configuration"),
                ("webtorrent", "WebTorrent protocol configuration"),
            ]
            
            for section, description in sections:
                self._sections_table.add_row(
                    section,
                    description,
                    "",  # Modified status (empty for now)
                    key=section,
                )
            
            # Set cursor to first row if available
            if self._sections_table.row_count > 0:
                self._sections_table.cursor_coordinate = (0, 0)
                self._sections_table.focus()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error populating global sections: %s", e)

    async def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle row selection in sections table.
        
        Args:
            event: DataTable.RowSelected event
        """
        if not self._sections_table or not hasattr(event, "row_key"):
            return
        
        try:
            # Extract section name from row key
            row_key = event.row_key
            section = str(row_key) if row_key else None
            
            if section:
                self._selected_section = section
                await self._show_section_info(section)
        except Exception as e:
            logger.debug("Error handling row selection: %s", e)

    async def on_data_table_cursor_row_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle cursor row change in sections table.
        
        Args:
            event: DataTable.CursorRowChanged event
        """
        if not self._sections_table:
            return
        
        try:
            # Get the row key at cursor position
            cursor_row = event.cursor_row
            if cursor_row is not None and cursor_row >= 0:
                # Get row key from cursor position
                row_key = self._sections_table.get_row_key_at(cursor_row)  # type: ignore[attr-defined]
                if row_key:
                    section = str(row_key)
                    await self._show_section_info(section)
        except Exception as e:
            logger.debug("Error handling cursor change: %s", e)

    async def _show_section_info(self, section: str) -> None:  # pragma: no cover
        """Show information about the selected section.
        
        Args:
            section: Section name (e.g., "network", "security.ssl")
        """
        if not self._content_widget:
            return
        
        try:
            from rich.panel import Panel
            from rich.table import Table
            
            # Create info table
            table = Table(show_header=False, box=None, expand=True)
            table.add_column("Field", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)
            
            # Get section description
            section_descriptions = {
                "network": "Network configuration (connections, timeouts, rate limits)",
                "network.protocol_v2": "BitTorrent Protocol v2 (BEP 52) settings",
                "network.utp": "uTP transport protocol (BEP 29) settings",
                "disk": "Disk I/O configuration (preallocation, hashing, checkpoints)",
                "disk.attributes": "File attributes (BEP 47: symlinks, executable, hidden)",
                "disk.xet": "Xet protocol (content-defined chunking) settings",
                "strategy": "Piece selection strategy configuration",
                "discovery": "Peer discovery (DHT, PEX, trackers)",
                "observability": "Logging, metrics, and tracing",
                "limits": "Rate limit configuration",
                "security": "Security settings (encryption, IP filtering, SSL)",
                "security.ip_filter": "IP filtering configuration",
                "security.ssl": "SSL/TLS settings for trackers and peers",
                "proxy": "Proxy configuration",
                "ml": "Machine learning configuration",
                "dashboard": "Dashboard/web UI configuration",
                "queue": "Torrent queue management",
                "nat": "NAT traversal configuration",
                "ipfs": "IPFS protocol configuration",
                "webtorrent": "WebTorrent protocol configuration",
            }
            
            description = section_descriptions.get(section, _("Configuration section"))
            
            table.add_row(_("Section"), section)
            table.add_row(_("Description"), description)
            table.add_row(_("Status"), _("Press Enter to configure this section"))
            table.add_row("", "")
            table.add_row(_("Note"), _("Full configuration editing requires navigating to the Global Config screen"))
            
            self._content_widget.update(
                Panel(
                    table,
                    title=_("Section: {section}").format(section=section),
                    border_style="blue",
                )
            )
        except Exception as e:
            logger.debug("Error showing section info: %s", e)

    async def action_select(self) -> None:  # pragma: no cover
        """Handle Enter key to select/navigate to section."""
        # If in editing mode, don't handle Enter (let inputs handle it)
        if self._editing_mode:
            return
        
        if not self._sections_table:
            return
        
        try:
            # Get selected section from cursor
            cursor_row = self._sections_table.cursor_row  # type: ignore[attr-defined]
            if cursor_row is not None and cursor_row >= 0:
                row_key = self._sections_table.get_row_key_at(cursor_row)  # type: ignore[attr-defined]
                if row_key:
                    section = str(row_key)
                    self._selected_section = section
                    # Load section and show form inputs
                    await self._load_section_for_editing(section)
        except Exception as e:
            logger.debug("Error handling section selection: %s", e)
            if hasattr(self, "app"):
                self.app.notify(  # type: ignore[attr-defined]
                    _("Error loading section: {error}").format(error=str(e)),
                    severity="error",
                )

    def _populate_config_content(self) -> None:  # pragma: no cover
        """Populate config content based on type.
        
        Maps config sub-tabs to appropriate global config sections:
        - "network" -> "network" section
        - "bandwidth" -> "limits" section  
        - "storage" -> "disk" section
        - "security" -> "security" section
        - "advanced" -> shows advanced sections
        - "torrent" -> per-torrent config (if info_hash provided)
        """
        if not self._content_widget:
            return
        
        try:
            # Map config types to sections
            section_map = {
                "network": "network",
                "bandwidth": "limits",
                "storage": "disk",
                "security": "security",
                "advanced": "advanced",
            }
            
            if self._config_type in section_map:
                # For mapped types, show section info
                section = section_map[self._config_type]
                from rich.panel import Panel
                from rich.table import Table
                
                # Create a simple info table
                table = Table(show_header=False, box=None, expand=True)
                table.add_column(_("Info"), style="cyan", ratio=1)
                table.add_column(_("Value"), style="green", ratio=2)
                
                descriptions = {
                    "network": _("Network configuration (connections, timeouts, rate limits)"),
                    "limits": _("Rate limit configuration (global and per-torrent)"),
                    "disk": _("Disk I/O configuration (preallocation, hashing, checkpoints)"),
                    "security": _("Security settings (encryption, IP filtering, SSL)"),
                    "advanced": _("Advanced configuration (experimental features)"),
                }
                
                table.add_row(_("Section"), section)
                table.add_row(_("Description"), descriptions.get(section, _("Configuration section")))
                table.add_row(_("Status"), _("Click on 'Global' tab to configure this section"))
                
                self._content_widget.update(
                    Panel(
                        table,
                        title=_("{type} Configuration").format(type=self._config_type.title()),
                        border_style="blue",
                    )
                )
            elif self._config_type == "torrent" and self._info_hash:
                # Per-torrent config - editors container is already in compose
                # Load torrent config for editing
                self.call_later(self._load_torrent_config_for_editing)  # type: ignore[attr-defined]
            else:
                content = _("Configuration: {type}\n\nThis configuration section is not yet fully implemented.").format(type=self._config_type)
                self._content_widget.update(content)
        except Exception as e:
            logger.debug("Error populating config content: %s", e)

    async def _load_section_for_editing(self, section: str) -> None:  # pragma: no cover
        """Load a section and create form inputs for editing.
        
        Args:
            section: Section name (e.g., "network", "security.ssl")
        """
        if not self._command_executor or not self._data_provider:
            error_msg = _("Command executor or data provider not available")
            if hasattr(self, "app"):
                self.app.notify(error_msg, severity="error")  # type: ignore[attr-defined]
            logger.debug("ConfigWrapper: %s", error_msg)
            return
        
        try:
            # Get current config with error handling
            try:
                result = await self._command_executor.execute_command("config.get")
            except Exception as e:
                error_msg = _("Error executing config.get command: {error}").format(error=str(e))
                logger.debug("ConfigWrapper: %s", error_msg)
                if hasattr(self, "app"):
                    self.app.notify(error_msg, severity="error")  # type: ignore[attr-defined]
                return
            
            if not result or not hasattr(result, "success") or not result.success:
                error_msg = result.error if result and hasattr(result, "error") else _("Unknown error")
                logger.debug("ConfigWrapper: Failed to get config: %s", error_msg)
                if hasattr(self, "app"):
                    self.app.notify(_("Failed to get config: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
                return
            
            config_dict = result.data.get("config", {}) if result.data else {}
            
            # Navigate to section in config dict
            section_parts = section.split(".")
            section_config = config_dict
            for part in section_parts:
                if isinstance(section_config, dict) and part in section_config:
                    section_config = section_config[part]
                else:
                    if hasattr(self, "app"):
                        self.app.notify(_("Section '{section}' not found").format(section=section), severity="error")  # type: ignore[attr-defined]
                    return
            
            if not isinstance(section_config, dict):
                if hasattr(self, "app"):
                    self.app.notify(_("Section '{section}' is not a configuration section").format(section=section), severity="error")  # type: ignore[attr-defined]
                return
            
            # Hide sections table and info, show editors
            if self._sections_table:
                self._sections_table.display = False
            if self._content_widget:
                self._content_widget.display = False
            
            # Show editors container
            editors_widget = self.query_one("#config-editors", Vertical)  # type: ignore[attr-defined]
            editors_widget.display = True
            title_widget = self.query_one("#config-editors-title", Static)  # type: ignore[attr-defined]
            self._editors_container = self.query_one("#config-editors-container", Container)  # type: ignore[attr-defined]
            errors_widget = self.query_one("#config-editors-errors", Static)  # type: ignore[attr-defined]
            
            # Clear existing editors
            self._editors_container.remove_children()  # type: ignore[attr-defined]
            self._editors.clear()
            
            # Set title
            title_widget.update(_("Editing: {section}").format(section=section))
            
            # Get section schema for metadata
            section_schema = ConfigSchema.get_schema_for_section(section_parts[0])
            section_properties = {}
            if section_schema and "properties" in section_schema:
                section_properties = section_schema["properties"]
            
            # Create editors for each config option (limit to first 20 to avoid overwhelming UI)
            editable_keys = sorted(section_config.keys())[:20]
            self._original_values = {}
            
            for opt_key in editable_keys:
                value = section_config[opt_key]
                self._original_values[opt_key] = value
                
                # Get option metadata from schema
                option_metadata = section_properties.get(opt_key)
                
                # Create label and widget using factory
                try:
                    label = Static(f"{opt_key}:", id=f"label_{opt_key}")
                    self._editors_container.mount(label)  # type: ignore[attr-defined]
                    
                    widget = create_config_widget(
                        option_key=opt_key,
                        current_value=value,
                        section_name=section_parts[0],
                        option_metadata=option_metadata,
                        id=f"editor_{opt_key}",
                    )
                    
                    # Make widget focusable
                    widget.can_focus = True  # type: ignore[attr-defined]
                    self._editors[opt_key] = widget
                    self._editors_container.mount(widget)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.debug("Error creating widget for %s: %s", opt_key, e)
                    continue
            
            errors_widget.update("")
            self._editing_mode = True
            self._changed_values.clear()
            
            # Show cancel button
            cancel_button = self.query_one("#cancel-button", Button)  # type: ignore[attr-defined]
            cancel_button.display = True
            
            # Focus first editor if available
            if self._editors:
                first_editor = next(iter(self._editors.values()))
                first_editor.focus()  # type: ignore[attr-defined]
            
        except Exception as e:
            logger.debug("Error loading section for editing: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error loading section: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def _load_torrent_config_for_editing(self) -> None:  # pragma: no cover
        """Load per-torrent configuration for editing."""
        if not self._info_hash or not self._command_executor or not self._data_provider:
            return
        
        try:
            # Get torrent status
            status = await self._data_provider.get_torrent_status(self._info_hash)
            if not status:
                errors_widget = self.query_one("#config-editors-errors", Static)  # type: ignore[attr-defined]
                errors_widget.update(_("Torrent not found"))
                return
            
            # Get editors container
            self._editors_container = self.query_one("#config-editors-container", Container)  # type: ignore[attr-defined]
            if not self._editors_container:
                return
            
            # Clear existing editors
            self._editors_container.remove_children()  # type: ignore[attr-defined]
            self._editors.clear()
            self._original_values.clear()
            self._changed_values.clear()
            
            # Create editable fields for per-torrent settings
            # Note: These would need to be fetched from config or torrent session
            # For now, we'll create placeholders that can be edited
            
            # Download rate limit (in bytes/sec, 0 = unlimited)
            download_limit = status.get("download_rate_limit", 0)
            self._original_values["download_rate_limit"] = download_limit
            
            label_dl = Static(_("Download Rate Limit (bytes/sec, 0 = unlimited):"), id="label_download_rate_limit")
            self._editors_container.mount(label_dl)  # type: ignore[attr-defined]
            
            editor_dl = ConfigValueEditor(
                option_key="download_rate_limit",
                current_value=download_limit,
                value_type="int",
                description=_("Maximum download rate for this torrent"),
                constraints={"minimum": 0},
                id="editor_download_rate_limit",
            )
            editor_dl.can_focus = True  # type: ignore[attr-defined]
            self._editors["download_rate_limit"] = editor_dl
            self._editors_container.mount(editor_dl)  # type: ignore[attr-defined]
            
            # Upload rate limit (in bytes/sec, 0 = unlimited)
            upload_limit = status.get("upload_rate_limit", 0)
            self._original_values["upload_rate_limit"] = upload_limit
            
            label_ul = Static(_("Upload Rate Limit (bytes/sec, 0 = unlimited):"), id="label_upload_rate_limit")
            self._editors_container.mount(label_ul)  # type: ignore[attr-defined]
            
            editor_ul = ConfigValueEditor(
                option_key="upload_rate_limit",
                current_value=upload_limit,
                value_type="int",
                description=_("Maximum upload rate for this torrent"),
                constraints={"minimum": 0},
                id="editor_upload_rate_limit",
            )
            editor_ul.can_focus = True  # type: ignore[attr-defined]
            self._editors["upload_rate_limit"] = editor_ul
            self._editors_container.mount(editor_ul)  # type: ignore[attr-defined]
            
            # Priority (0 = normal, 1 = high, -1 = low)
            priority = status.get("priority", 0)
            self._original_values["priority"] = priority
            
            label_prio = Static(_("Priority (0 = normal, 1 = high, -1 = low):"), id="label_priority")
            self._editors_container.mount(label_prio)  # type: ignore[attr-defined]
            
            editor_prio = ConfigValueEditor(
                option_key="priority",
                current_value=priority,
                value_type="int",
                description=_("Torrent priority"),
                constraints={"minimum": -1, "maximum": 1},
                id="editor_priority",
            )
            editor_prio.can_focus = True  # type: ignore[attr-defined]
            self._editors["priority"] = editor_prio
            self._editors_container.mount(editor_prio)  # type: ignore[attr-defined]
            
            # Update title
            title_widget = self.query_one("#config-editors-title", Static)  # type: ignore[attr-defined]
            torrent_name = status.get("name", _("Unknown"))[:30]
            title_widget.update(_("Per-Torrent Configuration: {name}").format(name=torrent_name))
            
            # Clear errors
            errors_widget = self.query_one("#config-editors-errors", Static)  # type: ignore[attr-defined]
            errors_widget.update("")
            
            self._editing_mode = True
            self._selected_section = "torrent"  # Mark as torrent config
            
            # Show cancel button
            cancel_button = self.query_one("#cancel-button", Button)  # type: ignore[attr-defined]
            cancel_button.display = True
            
            # Focus first editor
            if self._editors:
                first_editor = next(iter(self._editors.values()))
                first_editor.focus()  # type: ignore[attr-defined]
                
        except Exception as e:
            logger.debug("Error loading torrent config for editing: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error loading torrent config: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_save_config(self) -> None:  # pragma: no cover
        """Save configuration using executor."""
        if not self._command_executor:
            if hasattr(self, "app"):
                self.app.notify(_("Command executor not available"), severity="error")  # type: ignore[attr-defined]
            return
        
        if not self._editing_mode or not self._selected_section:
            # Not in editing mode, show info
            if hasattr(self, "app"):
                self.app.notify(_("No section selected for editing"), severity="info")  # type: ignore[attr-defined]
            return
        
        # Validate all inputs before saving
        errors_widget = self.query_one("#config-editors-errors", Static)  # type: ignore[attr-defined]
        validation_errors: list[str] = []
        
        for option_key, widget in self._editors.items():
            is_valid, error_msg = validate_widget_value(widget)
            if not is_valid:
                validation_errors.append(f"{option_key}: {error_msg}")
                if hasattr(widget, "add_class"):
                    widget.add_class("-invalid")  # type: ignore[attr-defined]
            else:
                if hasattr(widget, "remove_class"):
                    widget.remove_class("-invalid")  # type: ignore[attr-defined]
        
        if validation_errors:
            error_text = "\n".join(f"[red]•[/red] {err}" for err in validation_errors)
            errors_widget.update(f"[red]Validation errors (fix before saving):[/red]\n{error_text}")
            if hasattr(self, "app"):
                self.app.notify(_("Please fix validation errors before saving"), severity="error")  # type: ignore[attr-defined]
            return
        
        try:
            # Collect edited values (re-validate during collection)
            edited_values = {}
            parse_errors: list[str] = []
            
            for key, widget in self._editors.items():
                try:
                    # Re-validate before getting value
                    is_valid, error_msg = validate_widget_value(widget)
                    if not is_valid:
                        parse_errors.append(f"{key}: {error_msg}")
                        continue
                    edited_values[key] = get_widget_value(widget)
                except Exception as e:
                    parse_errors.append(f"{key}: {str(e)}")
            
            if parse_errors:
                error_text = "\n".join(f"[red]•[/red] {err}" for err in parse_errors)
                errors_widget.update(f"[red]Parse errors (fix before saving):[/red]\n{error_text}")
                if hasattr(self, "app"):
                    self.app.notify(_("Please fix parse errors before saving"), severity="error")  # type: ignore[attr-defined]
                return
            
            # Handle per-torrent config differently
            if self._config_type == "torrent" and self._info_hash:
                # Per-torrent config - use torrent-specific commands
                save_results = []
                
                # Set rate limits if changed
                if "download_rate_limit" in edited_values or "upload_rate_limit" in edited_values:
                    download_kib = edited_values.get("download_rate_limit", 0) // 1024
                    upload_kib = edited_values.get("upload_rate_limit", 0) // 1024
                    
                    rate_result = await self._command_executor.execute_command(
                        "torrent.set_rate_limits",
                        info_hash=self._info_hash,
                        download_kib=download_kib,
                        upload_kib=upload_kib,
                    )
                    save_results.append(("rate_limits", rate_result))
                
                # Set priority if changed
                if "priority" in edited_values:
                    priority_value = edited_values["priority"]
                    # Map numeric priority to string
                    priority_map = {-1: "low", 0: "normal", 1: "high"}
                    priority_str = priority_map.get(priority_value, "normal")
                    
                    priority_result = await self._command_executor.execute_command(
                        "queue.add",
                        info_hash=self._info_hash,
                        priority=priority_str,
                    )
                    save_results.append(("priority", priority_result))
                
                # Check if all saves succeeded
                all_success = all(
                    result and hasattr(result, "success") and result.success
                    for _, result in save_results
                )
                
                if all_success:
                    # Per-torrent configs don't require daemon restart (they're immediate)
                    update_result = type("Result", (), {"success": True, "data": {"restart_required": False}})()
                    if hasattr(self, "app"):
                        self.app.notify(_("Per-torrent configuration saved successfully"), severity="success")  # type: ignore[attr-defined]
                else:
                    errors = [
                        f"{name}: {result.error if result and hasattr(result, 'error') else 'Unknown error'}"
                        for name, result in save_results
                        if not (result and hasattr(result, "success") and result.success)
                    ]
                    error_msg = "; ".join(errors)
                    update_result = type("Result", (), {"success": False, "error": error_msg})()
            else:
                # Global config - build config update dict with nested structure
                section_parts = self._selected_section.split(".")
                config_update = {}
                current = config_update
                for part in section_parts[:-1]:
                    current[part] = {}
                    current = current[part]
                current[section_parts[-1]] = edited_values
                
                # Save via executor
                update_result = await self._command_executor.execute_command(
                    "config.update",
                    config_dict=config_update
                )
            
            if update_result and hasattr(update_result, "success") and update_result.success:
                restart_required = update_result.data.get("restart_required", False) if update_result.data else False
                if restart_required:
                    if hasattr(self, "app"):
                        from rich.panel import Panel
                        from rich.text import Text
                        restart_msg = Text()
                        restart_msg.append(_("Configuration saved successfully.\n"), style="green")
                        restart_msg.append(_("⚠️  Daemon restart required to apply changes.\n"), style="yellow")
                        restart_msg.append(_("Use 'btbt daemon restart' or restart the daemon manually."), style="dim")
                        self.app.notify(  # type: ignore[attr-defined]
                            Panel(restart_msg, title=_("Restart Required"), border_style="yellow"),
                            severity="warning",
                            timeout=10.0,
                        )
                else:
                    if hasattr(self, "app"):
                        self.app.notify(_("Configuration saved successfully"), severity="success")  # type: ignore[attr-defined]
                
                # Update original values
                self._original_values.update(edited_values)
                
                # Clear changed values tracking
                self._changed_values.clear()
                
                # Remove change indicators from widgets
                for widget in self._editors.values():
                    if hasattr(widget, "remove_class"):
                        widget.remove_class("-changed")  # type: ignore[attr-defined]
                        widget.remove_class("-invalid")  # type: ignore[attr-defined]
                        widget.add_class("-valid")  # type: ignore[attr-defined]
                
                # Clear errors
                errors_widget = self.query_one("#config-editors-errors", Static)  # type: ignore[attr-defined]
                errors_widget.update(_("Configuration saved successfully!"))
            else:
                error_msg = update_result.error if update_result and hasattr(update_result, "error") else _("Unknown error")
                if hasattr(self, "app"):
                    self.app.notify(_("Failed to save config: {error}").format(error=error_msg), severity="error")  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("Error saving config: %s", e)
            if hasattr(self, "app"):
                self.app.notify(_("Error saving configuration: {error}").format(error=str(e)), severity="error")  # type: ignore[attr-defined]

    async def action_cancel_editing(self) -> None:  # pragma: no cover
        """Cancel editing and return to section list."""
        try:
            # Hide editors, show sections table and info
            editors_widget = self.query_one("#config-editors", Vertical)  # type: ignore[attr-defined]
            editors_widget.display = False
            
            if self._sections_table:
                self._sections_table.display = True
            if self._content_widget:
                self._content_widget.display = True
            
            # Clear editors
            if self._editors_container:
                self._editors_container.remove_children()  # type: ignore[attr-defined]
            self._editors.clear()
            self._original_values.clear()
            self._changed_values.clear()
            self._editing_mode = False
            self._selected_section = None
            
            # Hide cancel button
            cancel_button = self.query_one("#cancel-button", Button)  # type: ignore[attr-defined]
            cancel_button.display = False
        except Exception as e:
            logger.debug("Error canceling editing: %s", e)

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if hasattr(event, "button") and event.button:
            button_id = getattr(event.button, "id", None)
            if button_id == "save-button":
                await self.action_save_config()
            elif button_id == "cancel-button":
                await self.action_cancel_editing()

    async def on_input_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle input value changes for real-time validation.
        
        Args:
            event: Input.Changed event
        """
        if not hasattr(event, "input") or not hasattr(event.input, "id"):
            return
        
        try:
            widget_id = event.input.id
            if not widget_id or not widget_id.startswith("editor_"):
                return
            
            # Extract option key from widget ID
            option_key = widget_id.replace("editor_", "")
            widget = self._editors.get(option_key)
            
            if not widget:
                return
            
            # Validate the widget
            is_valid, error_msg = validate_widget_value(widget)
            
            # Update visual feedback (only for Input-based widgets)
            if hasattr(widget, "remove_class") and hasattr(widget, "add_class"):
                if is_valid:
                    widget.remove_class("-invalid")  # type: ignore[attr-defined]
                    widget.add_class("-valid")  # type: ignore[attr-defined]
                else:
                    widget.remove_class("-valid")  # type: ignore[attr-defined]
                    widget.add_class("-invalid")  # type: ignore[attr-defined]
            
            # Check if value has changed from original
            try:
                current_value = get_widget_value(widget)
                original_value = self._original_values.get(option_key)
                
                # Compare values (handle different types)
                if current_value != original_value:
                    self._changed_values.add(option_key)
                    if hasattr(widget, "add_class"):
                        widget.add_class("-changed")  # type: ignore[attr-defined]
                else:
                    self._changed_values.discard(option_key)
                    if hasattr(widget, "remove_class"):
                        widget.remove_class("-changed")  # type: ignore[attr-defined]
            except Exception:
                # If parsing fails, mark as changed
                self._changed_values.add(option_key)
                if hasattr(widget, "add_class"):
                    widget.add_class("-changed")  # type: ignore[attr-defined]
            
            # Update errors display
            await self._update_validation_errors()
            
        except Exception as e:
            logger.debug("Error handling input change: %s", e)

    async def on_checkbox_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle checkbox value changes.
        
        Args:
            event: Checkbox.Changed event
        """
        if not hasattr(event, "checkbox") or not hasattr(event.checkbox, "id"):
            return
        
        try:
            widget_id = event.checkbox.id
            if not widget_id or not widget_id.startswith("editor_"):
                return
            
            option_key = widget_id.replace("editor_", "")
            widget = self._editors.get(option_key)
            
            if not widget:
                return
            
            # Check if value has changed
            current_value = get_widget_value(widget)
            original_value = self._original_values.get(option_key)
            
            if current_value != original_value:
                self._changed_values.add(option_key)
                if hasattr(widget, "add_class"):
                    widget.add_class("-changed")  # type: ignore[attr-defined]
            else:
                self._changed_values.discard(option_key)
                if hasattr(widget, "remove_class"):
                    widget.remove_class("-changed")  # type: ignore[attr-defined]
            
            await self._update_validation_errors()
            
        except Exception as e:
            logger.debug("Error handling checkbox change: %s", e)

    async def on_select_changed(self, event: Any) -> None:  # pragma: no cover
        """Handle select value changes.
        
        Args:
            event: Select.Changed event
        """
        if not hasattr(event, "select") or not hasattr(event.select, "id"):
            return
        
        try:
            widget_id = event.select.id
            if not widget_id or not widget_id.startswith("editor_"):
                return
            
            option_key = widget_id.replace("editor_", "")
            widget = self._editors.get(option_key)
            
            if not widget:
                return
            
            # Check if value has changed
            current_value = get_widget_value(widget)
            original_value = self._original_values.get(option_key)
            
            if current_value != original_value:
                self._changed_values.add(option_key)
                if hasattr(widget, "add_class"):
                    widget.add_class("-changed")  # type: ignore[attr-defined]
            else:
                self._changed_values.discard(option_key)
                if hasattr(widget, "remove_class"):
                    widget.remove_class("-changed")  # type: ignore[attr-defined]
            
            await self._update_validation_errors()
            
        except Exception as e:
            logger.debug("Error handling select change: %s", e)

    async def on_input_submitted(self, event: Any) -> None:  # pragma: no cover
        """Handle input submission (Enter key).
        
        Args:
            event: Input.Submitted event
        """
        if not hasattr(event, "input") or not hasattr(event.input, "id"):
            return
        
        try:
            editor_id = event.input.id
            if not editor_id or not editor_id.startswith("editor_"):
                return
            
            # Extract option key from editor ID
            option_key = editor_id.replace("editor_", "")
            editor = self._editors.get(option_key)
            
            if not editor:
                return
            
            # Validate and update
            is_valid, error_msg = editor.validate_value()
            
            if is_valid:
                # Move focus to next editor or save button
                editors_list = list(self._editors.items())
                current_idx = next((i for i, (k, _) in enumerate(editors_list) if k == option_key), -1)
                
                if current_idx >= 0 and current_idx < len(editors_list) - 1:
                    # Focus next editor
                    next_key, next_editor = editors_list[current_idx + 1]
                    next_editor.focus()  # type: ignore[attr-defined]
                else:
                    # Focus save button
                    save_button = self.query_one("#save-button", Button)  # type: ignore[attr-defined]
                    save_button.focus()  # type: ignore[attr-defined]
            else:
                # Show error and keep focus
                await self._update_validation_errors()
                
        except Exception as e:
            logger.debug("Error handling input submission: %s", e)

    async def _update_validation_errors(self) -> None:  # pragma: no cover
        """Update the validation errors display."""
        try:
            errors_widget = self.query_one("#config-editors-errors", Static)  # type: ignore[attr-defined]
            errors: list[str] = []
            
            # Collect validation errors from all editors
            for option_key, editor in self._editors.items():
                is_valid, error_msg = editor.validate_value()
                if not is_valid:
                    errors.append(f"{option_key}: {error_msg}")
            
            if errors:
                error_text = "\n".join(f"[red]•[/red] {err}" for err in errors)
                errors_widget.update(error_text)
            else:
                # Show changed values count if any
                if self._changed_values:
                    errors_widget.update(
                        f"[yellow]{len(self._changed_values)} value(s) changed. Press 's' to save or 'Escape' to cancel.[/yellow]"
                    )
                else:
                    errors_widget.update("")
                    
        except Exception as e:
            logger.debug("Error updating validation errors: %s", e)

