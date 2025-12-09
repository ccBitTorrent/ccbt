"""Global configuration screens."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Static,
    )
else:
    try:
        from textual.app import ComposeResult
        from textual.containers import (
            Container,
            Horizontal,
            Vertical,
        )
        from textual.widgets import (
            Button,
            DataTable,
            Footer,
            Header,
            Static,
        )
    except ImportError:
        ComposeResult = None  # type: ignore[assignment, misc]
        Container = None  # type: ignore[assignment, misc]
        Horizontal = None  # type: ignore[assignment, misc]
        Vertical = None  # type: ignore[assignment, misc]
        Button = None  # type: ignore[assignment, misc]
        DataTable = None  # type: ignore[assignment, misc]
        Footer = None  # type: ignore[assignment, misc]
        Header = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from ccbt.session.session import AsyncSessionManager
else:
    try:
        from ccbt.session.session import AsyncSessionManager
    except ImportError:
        AsyncSessionManager = None  # type: ignore[assignment, misc]

from rich.panel import Panel
from rich.table import Table

from ccbt.config.config import set_config
from ccbt.interface.screens.base import GlobalConfigScreen
from ccbt.interface.screens.config.widgets import ConfigValueEditor

logger = logging.getLogger(__name__)


class GlobalConfigMainScreen(GlobalConfigScreen):  # type: ignore[misc]
    """Main screen for global configuration with section selector."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
        ("enter", "select", "Select Section"),
    ]

    CSS = """
    #sections {
        height: 1fr;
    }
    #info {
        height: 1fr;
        min-height: 5;
    }
    """

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the global config main screen."""
        yield Header()
        with Container():
            yield DataTable(id="sections", zebra_stripes=True)
            yield Static(id="info")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and populate sections."""
        sections_table = self.query_one("#sections", DataTable)
        sections_table.add_columns("Section", "Description", "Modified")

        # Define all config sections matching ccbt.toml.example
        # Include nested sections as separate entries for easier navigation
        sections = [
            ("network", "Network configuration (connections, timeouts, rate limits)"),
            ("network.protocol_v2", "BitTorrent Protocol v2 (BEP 52) settings"),
            ("network.utp", "uTP transport protocol (BEP 29) settings"),
            ("disk", "Disk I/O configuration (preallocation, hashing, checkpoints)"),
            (
                "disk.attributes",
                "File attributes (BEP 47: symlinks, executable, hidden)",
            ),
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

        for section_name, description in sections:
            # Use section_name as the key - RowKey will wrap it
            sections_table.add_row(section_name, description, "", key=section_name)

        sections_table.cursor_type = "row"
        # Ensure cursor is on first row and table is focused
        if sections_table.row_count > 0:
            sections_table.cursor_coordinate = (0, 0)
        sections_table.focus()

        # Update info panel
        info = self.query_one("#info", Static)
        info.update(
            Panel(
                "Select a section to configure. Press Enter to edit, Escape to go back.",
                title="Global Configuration",
            )
        )

    def _extract_row_key_value(self, row_key: Any) -> str | None:
        """Extract the actual value from a RowKey object.

        Args:
            row_key: The RowKey object from Textual DataTable

        Returns:
            The extracted section name as a string, or None if extraction fails
        """
        if row_key is None:
            return None

        # If it's already a string, return it directly
        if isinstance(row_key, str):
            return row_key

        # Try to get the value attribute
        if hasattr(row_key, "value"):
            val = row_key.value
            return str(val) if val is not None else None

        # Try string conversion - Textual RowKey should convert to string
        try:
            key_str = str(row_key)
            # If it looks like a section name (contains dots or underscores), return it
            if (
                "." in key_str
                or "_" in key_str
                or key_str.replace("_", "").replace(".", "").isalnum()
            ):
                # Remove any wrapper text like "RowKey('...')"
                import re

                match = re.search(r"['\"]([^'\"]+)['\"]", key_str)
                if match:
                    return match.group(1)
                # If no quotes, try to extract the actual value
                # RowKey might stringify as "RowKey(value)" or just "value"
                if "(" in key_str and ")" in key_str:
                    # Extract content between parentheses
                    match = re.search(r"\(([^)]+)\)", key_str)
                    if match:
                        return match.group(1).strip("'\"")
                return key_str.strip()
        except Exception:
            pass

        return None

    async def on_data_table_row_selected(self, event: Any) -> None:  # pragma: no cover
        """Handle section selection when Enter is pressed or row is clicked."""
        # Prevent double navigation - use a lock-like mechanism
        if not hasattr(self, "_navigating"):
            self._navigating = False  # type: ignore[attr-defined]

        # Check and set flag atomically to prevent race conditions
        if self._navigating:  # type: ignore[attr-defined]
            return

        # Set navigating flag immediately (synchronously) to prevent race conditions
        self._navigating = True  # type: ignore[attr-defined]

        try:
            # Navigate to section detail screen when row is selected
            # event.row_key should contain the section name
            section_name = None

            # Try to get row_key from event
            if hasattr(event, "row_key") and event.row_key is not None:
                section_name = self._extract_row_key_value(event.row_key)

            # Fallback: get from DataTable cursor_row_key
            if not section_name:
                try:
                    sections_table = self.query_one("#sections", DataTable)
                    if (
                        hasattr(sections_table, "cursor_row_key")
                        and sections_table.cursor_row_key
                    ):
                        section_name = self._extract_row_key_value(
                            sections_table.cursor_row_key
                        )
                except Exception as e:
                    self.logger.debug("Could not get cursor_row_key: %s", e)

            # Fallback: get from cursor coordinate
            if not section_name:
                try:
                    sections_table = self.query_one("#sections", DataTable)
                    if hasattr(sections_table, "cursor_coordinate"):
                        row, _ = sections_table.cursor_coordinate
                        if row is not None and 0 <= row < sections_table.row_count:
                            # Get the row data and use first column as section name
                            row_data = sections_table.get_row(row)
                            if row_data and len(row_data) > 0:
                                section_name = str(row_data[0])
                except Exception as e:
                    self.logger.debug("Could not get section from cursor: %s", e)

            if section_name:
                try:
                    # Use call_after_refresh to ensure screen is ready before navigation
                    await self.app.push_screen(  # type: ignore[attr-defined]
                        GlobalConfigDetailScreen(
                            self.session, section_name=section_name
                        )
                    )
                except Exception as e:
                    # Log error and show message instead of crashing
                    self.logger.exception(
                        "Failed to navigate to section '%s': %s", section_name, e
                    )
                    try:
                        info = self.query_one("#info", Static)
                        info.update(
                            Panel(
                                f"Error opening section '{section_name}': {e}\n\nPlease try again.",
                                title="Navigation Error",
                                border_style="red",
                            )
                        )
                    except Exception:
                        # If we can't show error, at least log it
                        self.logger.error("Could not display navigation error message")
            else:
                # Show error if we couldn't determine the section
                try:
                    info = self.query_one("#info", Static)
                    info.update(
                        Panel(
                            "Error: Could not determine selected section.\n\nPlease try selecting a section again.",
                            title="Navigation Error",
                            border_style="red",
                        )
                    )
                except Exception:
                    self.logger.error("Could not display navigation error message")
        finally:
            # Reset navigation flag immediately after navigation completes
            # Use a small delay to prevent immediate re-triggering, but make it shorter
            async def reset_navigation_flag():
                await asyncio.sleep(
                    0.1
                )  # Shorter delay - just enough to prevent immediate re-trigger
                self._navigating = False  # type: ignore[attr-defined]

            asyncio.create_task(reset_navigation_flag())

    async def action_select(self) -> None:  # pragma: no cover
        """Select and navigate to the selected section (bound to Enter key)."""
        # Prevent double navigation - check flag first
        if not hasattr(self, "_navigating"):
            self._navigating = False  # type: ignore[attr-defined]

        if self._navigating:  # type: ignore[attr-defined]
            return

        # When Enter is pressed on a DataTable, Textual triggers both:
        # 1. on_data_table_row_selected event (handled by DataTable)
        # 2. action_select action (this method)
        # We need to prevent both from running. The DataTable's on_data_table_row_selected
        # will handle navigation when the DataTable is focused.
        # So if DataTable is focused, we just return and let on_data_table_row_selected handle it.
        try:
            sections_table = self.query_one("#sections", DataTable)
            # If DataTable is focused, on_data_table_row_selected will handle navigation
            # We just return early to prevent double navigation
            if sections_table.has_focus:
                # Don't do anything - let on_data_table_row_selected handle it
                return

            # If DataTable is not focused, manually navigate
            # This shouldn't happen normally, but provides a fallback
            if (
                hasattr(sections_table, "cursor_row_key")
                and sections_table.cursor_row_key
            ):
                # Set navigating flag to prevent double navigation
                self._navigating = True  # type: ignore[attr-defined]
                try:
                    section_name = self._extract_row_key_value(
                        sections_table.cursor_row_key
                    )
                    if section_name:
                        await self.app.push_screen(  # type: ignore[attr-defined]
                            GlobalConfigDetailScreen(
                                self.session, section_name=section_name
                            )
                        )
                    else:
                        await self._navigate_to_section()
                except Exception as e:
                    self.logger.exception("Error in action_select")
                    try:
                        info = self.query_one("#info", Static)
                        info.update(
                            Panel(
                                f"Error: {e}\n\nPlease try again.",
                                title="Navigation Error",
                                border_style="red",
                            )
                        )
                    except Exception:
                        pass
                finally:
                    # Reset navigation flag after a short delay
                    async def reset_navigation_flag():
                        await asyncio.sleep(0.5)
                        self._navigating = False  # type: ignore[attr-defined]

                    asyncio.create_task(reset_navigation_flag())
            else:
                # Fallback to manual navigation
                await self._navigate_to_section()
        except Exception as e:
            self.logger.exception("Error in action_select")
            try:
                info = self.query_one("#info", Static)
                info.update(
                    Panel(
                        f"Error: {e}\n\nPlease try again.",
                        title="Navigation Error",
                        border_style="red",
                    )
                )
            except Exception:
                pass

    async def _navigate_to_section(self) -> None:  # pragma: no cover
        """Navigate to selected section's detail screen."""
        try:
            sections_table = self.query_one("#sections", DataTable)
        except Exception as e:
            self.logger.exception("Failed to get sections table")
            # Don't raise - show error to user instead
            try:
                info = self.query_one("#info", Static)
                info.update(
                    Panel(
                        f"Error: Could not access sections table.\n\n{e}\n\nPlease try again.",
                        title="Navigation Error",
                        border_style="red",
                    )
                )
            except Exception:
                pass
            return

        # Try multiple methods to get the selected section
        section_name = None

        # Method 1: Try cursor_row_key (most reliable)
        try:
            if (
                hasattr(sections_table, "cursor_row_key")
                and sections_table.cursor_row_key
            ):
                row_key = sections_table.cursor_row_key
                section_name = self._extract_row_key_value(row_key)
        except Exception as e:
            self.logger.debug("Method 1 failed: %s", e)

        # Method 2: Try get_row_key with cursor_row
        if not section_name:
            try:
                if (
                    hasattr(sections_table, "cursor_row")
                    and sections_table.cursor_row is not None
                ):
                    row_key = sections_table.get_row_key(sections_table.cursor_row)
                    if row_key:
                        section_name = self._extract_row_key_value(row_key)
            except Exception as e:
                self.logger.debug("Method 2 failed: %s", e)

        # Method 3: Use cursor coordinate to get row index, then get key
        if not section_name:
            try:
                if hasattr(sections_table, "cursor_coordinate"):
                    row, _ = sections_table.cursor_coordinate
                    if row is not None and row >= 0 and row < sections_table.row_count:
                        row_key = sections_table.get_row_key(row)
                        if row_key:
                            section_name = self._extract_row_key_value(row_key)
            except Exception as e:
                self.logger.debug("Method 3 failed: %s", e)

        # Method 4: Try highlighted_row
        if not section_name:
            try:
                if (
                    hasattr(sections_table, "highlighted_row")
                    and sections_table.highlighted_row is not None
                ):
                    row_key = sections_table.get_row_key(sections_table.highlighted_row)
                    if row_key:
                        section_name = self._extract_row_key_value(row_key)
            except Exception as e:
                self.logger.debug("Method 4 failed: %s", e)

        # Method 5: Fallback - get first column value from cursor row
        if not section_name:
            try:
                if (
                    hasattr(sections_table, "cursor_row")
                    and sections_table.cursor_row is not None
                ):
                    row_data = sections_table.get_row(sections_table.cursor_row)
                    if row_data and len(row_data) > 0:
                        section_name = str(row_data[0])
            except Exception as e:
                self.logger.debug("Method 5 failed: %s", e)

        if section_name:
            # Navigate to section detail screen
            # GlobalConfigDetailScreen handles all sections generically by dynamically
            # loading the section configuration and creating editable fields.
            # This approach is flexible and works for all configuration sections.
            try:
                await self.app.push_screen(  # type: ignore[attr-defined]
                    GlobalConfigDetailScreen(self.session, section_name=section_name)
                )
            except Exception as e:
                self.logger.exception("Failed to push GlobalConfigDetailScreen")
                # Show error to user instead of crashing
                try:
                    info = self.query_one("#info", Static)
                    info.update(
                        Panel(
                            f"Error opening section '{section_name}': {e}\n\nPlease try again.",
                            title="Navigation Error",
                            border_style="red",
                        )
                    )
                except Exception:
                    # If we can't show error, at least log it
                    self.logger.error("Could not display navigation error message")
                # Don't re-raise - prevent app crash
                return
        else:
            # Fallback: show error message with debug info
            try:
                info = self.query_one("#info", Static)
                debug_info = f"Row count: {sections_table.row_count}, Cursor: {getattr(sections_table, 'cursor_coordinate', 'N/A')}"
                info.update(
                    Panel(
                        f"Error: Could not determine selected section. Please try again.\n\nDebug: {debug_info}",
                        title="Error",
                        border_style="red",
                    )
                )
            except Exception as e:
                self.logger.exception("Failed to show error message")
                # Don't raise - prevent app crash


class GlobalConfigDetailScreen(GlobalConfigScreen):  # type: ignore[misc]
    """Detail screen for global configuration section with editable fields."""

    CSS = """
    #content {
        height: 1fr;
        overflow-y: auto;
    }
    #metrics_section {
        height: 1fr;
        min-height: 8;
    }
    #editors {
        height: 1fr;
        overflow-y: auto;
    }
    #actions {
        height: 3;
    }
    #errors {
        height: 5;
        min-height: 3;
    }
    """

    def __init__(
        self, session: AsyncSessionManager, section_name: str, *args: Any, **kwargs: Any
    ):  # pragma: no cover
        """Initialize config detail screen."""
        super().__init__(session, *args, **kwargs)
        self.section_name = section_name
        self._editors: dict[str, ConfigValueEditor] = {}
        self._original_config: Any = None
        self._section_schema: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        """Compose the config detail screen."""
        yield Header()
        with Vertical():
            yield Static(id="content")
            yield Static(id="metrics_section")
            yield Container(id="editors")
            yield Static(id="errors")
            with Horizontal(id="actions"):
                yield Button("Save (Runtime)", id="save_runtime", variant="primary")
                yield Button("Save to File", id="save_file", variant="success")
                yield Button("Cancel", id="cancel")
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]  # pragma: no cover
        """Mount the screen and populate config with editable fields."""
        # Query widgets first - if this fails, we can't proceed
        try:
            content = self.query_one("#content", Static)
            editors_container = self.query_one("#editors", Container)
            errors_widget = self.query_one("#errors", Static)
        except Exception as e:
            self.logger.exception("Failed to query widgets in on_mount")
            # Try to show error on screen if possible - query again with error handling
            try:
                # Query content again with proper error handling
                content_widget = self.query_one("#content", Static)
                content_widget.update(
                    Panel(
                        f"Error initializing screen: {e}\n\nPlease try again.",
                        title="Error",
                        border_style="red",
                    )
                )
            except Exception:
                # If we can't even show error, just log it - don't crash
                self.logger.error(
                    "Could not display error message - widgets not available"
                )
            return

        try:
            # Get config - session.config is a ConfigManager, config.config is the Config model
            # CRITICAL FIX: Add timeout to prevent hanging
            try:
                if hasattr(self.session, "config") and hasattr(
                    self.session.config, "config"
                ):
                    config = self.session.config.config
                    config_manager = self.session.config
                else:
                    # Fallback to get_config()
                    from ccbt.config.config import get_config, init_config

                    config = get_config()
                    config_manager = init_config()
            except AttributeError as e:
                # Catch "list object has no attribute get" or similar errors
                error_msg = str(e)
                self.logger.error(
                    "CRITICAL: AttributeError loading config: %s\n"
                    "session.config type: %s\n"
                    "Stack trace:",
                    error_msg,
                    type(getattr(self.session, "config", None)),
                    exc_info=True,
                )
                # Show error to user immediately
                try:
                    content.update(
                        Panel(
                            f"Error loading configuration: {error_msg}\n\n"
                            "This may indicate a configuration data structure issue.\n"
                            "Please check the logs for details.",
                            title="Configuration Error",
                            border_style="red",
                        )
                    )
                except Exception:
                    pass
                return
        except Exception as e:
            self.logger.exception("Failed to load config")
            try:
                content.update(
                    Panel(
                        f"Error loading configuration: {e}\n\nPlease try again.",
                        title="Error",
                        border_style="red",
                    )
                )
            except Exception:
                pass
            return

        # Handle nested sections (e.g., "network.protocol_v2")
        # Special case: "disk.xet" - xet settings are attributes of DiskConfig, not a nested object
        if self.section_name == "disk.xet":
            # Access disk config and filter for xet_* attributes
            section_config = config.disk
            if section_config is None:
                content.update(
                    Panel(
                        f"Section '{self.section_name}' not found",
                        title="Error",
                        border_style="red",
                    )
                )
                return
            # Get all xet-related attributes
            # Run model_dump in executor to avoid blocking UI for large configs
            # Use global asyncio import (already imported at module level)
            loop = asyncio.get_event_loop()
            if hasattr(section_config, "model_dump"):
                disk_dict = await loop.run_in_executor(None, section_config.model_dump)
            else:
                disk_dict = {}
            config_dict = {}
            for key, value in disk_dict.items():
                if key.startswith("xet_"):
                    config_dict[key] = value
            self._original_config = section_config
        else:
            # Normal nested section handling
            section_parts = self.section_name.split(".")
            section_config = config
            for part in section_parts:
                if hasattr(section_config, part):
                    section_config = getattr(section_config, part)
                else:
                    content.update(
                        Panel(
                            f"Section '{self.section_name}' not found (part '{part}' missing)",
                            title="Error",
                            border_style="red",
                        )
                    )
                    return

            if section_config is None:
                content.update(
                    Panel(
                        f"Section '{self.section_name}' not found",
                        title="Error",
                        border_style="red",
                    )
                )
                return

            self._original_config = section_config
            # Run model_dump in executor to avoid blocking UI for large configs
            loop = asyncio.get_event_loop()
            if hasattr(section_config, "model_dump"):
                config_dict = await loop.run_in_executor(
                    None, section_config.model_dump
                )
            else:
                config_dict = {}

        # Get schema for this section to get metadata
        # Run in executor to avoid blocking the UI thread
        try:
            loop = asyncio.get_event_loop()
            # Run schema retrieval in executor to prevent blocking
            self._section_schema = await loop.run_in_executor(
                None, config_manager.get_section_schema, self.section_name
            )
        except Exception as e:
            self.logger.debug(
                "Could not get schema for section %s: %s", self.section_name, e
            )
            self._section_schema = None

        # Create a table showing current values
        table = Table(title=f"{self.section_name.title()} Configuration", expand=True)
        table.add_column("Option", style="cyan", ratio=2)
        table.add_column("Current Value", style="green", ratio=3)
        table.add_column("Type", style="dim", ratio=1)

        # Limit to first 15 editable options to avoid overwhelming the UI
        editable_keys = list(config_dict.keys())[:15]

        for opt_key in editable_keys:
            value = config_dict[opt_key]

            # Format value for display
            if isinstance(value, bool):
                value_str = "true" if value else "false"
                type_str = "bool"
            elif isinstance(value, (int, float)):
                value_str = str(value)
                type_str = "number"
            elif isinstance(value, list):
                value_str = f"[{len(value)} items]"
                type_str = "list"
            elif isinstance(value, dict):
                value_str = f"{{ {len(value)} keys }}"
                type_str = "dict"
            else:
                value_str = str(value)[:50]  # Truncate long strings
                type_str = "string"

            table.add_row(opt_key, value_str, type_str)

        content.update(Panel(table))

        # Create editable inputs for each option
        for opt_key in editable_keys:
            value = config_dict[opt_key]

            # Determine type and constraints from schema
            value_type = "string"
            constraints: dict[str, Any] = {}
            description = ""

            if self._section_schema and "properties" in self._section_schema:
                prop_schema = self._section_schema["properties"].get(opt_key, {})
                value_type = prop_schema.get("type", "string")
                description = prop_schema.get("description", "")
                if "minimum" in prop_schema:
                    constraints["minimum"] = prop_schema["minimum"]
                if "maximum" in prop_schema:
                    constraints["maximum"] = prop_schema["maximum"]

            # Infer type from value if not in schema
            if value_type == "string" or value_type == "unknown":
                if isinstance(value, bool):
                    value_type = "bool"
                elif isinstance(value, int):
                    value_type = "int"
                elif isinstance(value, float):
                    value_type = "float"
                elif isinstance(value, list):
                    value_type = "list"

            # Create editor with label
            try:
                label = Static(
                    f"{opt_key}: {description[:60]}" if description else opt_key,
                    id=f"label_{opt_key}",
                )
                editors_container.mount(label)

                editor = ConfigValueEditor(
                    option_key=opt_key,
                    current_value=value,
                    value_type=value_type,
                    description=description,
                    constraints=constraints,
                    id=f"editor_{opt_key}",
                )
                self._editors[opt_key] = editor
                editors_container.mount(editor)
            except Exception as e:
                self.logger.exception("Failed to create editor for %s", opt_key)
                # Continue with other editors instead of crashing
                continue

        errors_widget.update("")

        # Store original values for change detection
        self._original_values = config_dict.copy()

        # Refresh metrics for this section (non-blocking - run in background)
        # Don't await - let it run in background to avoid blocking screen initialization
        async def refresh_metrics_background():
            try:
                await self._refresh_metrics()
                # Set up auto-refresh for metrics after initial load
                self.set_interval(3.0, self._refresh_metrics)
            except Exception as e:
                self.logger.debug("Could not refresh metrics: %s", e)
                # Metrics are optional, don't crash if they fail

        # Start metrics refresh in background task
        asyncio.create_task(refresh_metrics_background())

    def _check_unsaved_changes(self) -> bool:  # pragma: no cover
        """Check if there are unsaved changes by comparing current values with originals.

        Returns:
            True if there are unsaved changes, False otherwise
        """
        if not hasattr(self, "_original_values"):
            return False

        for key, editor in self._editors.items():
            try:
                current_value = editor.get_parsed_value()
                original_value = self._original_values.get(key)
                if current_value != original_value:
                    return True
            except Exception:
                # If we can't parse, assume no change
                pass
        return False

    async def on_button_pressed(self, event: Any) -> None:  # pragma: no cover
        """Handle button presses."""
        if event.button.id == "save_runtime":
            await self._save_config(runtime_only=True)
        elif event.button.id == "save_file":
            await self._save_config(runtime_only=False)
        elif event.button.id == "cancel":
            self.app.pop_screen()  # type: ignore[attr-defined]

    async def _save_config(self, runtime_only: bool) -> None:  # pragma: no cover
        """Save configuration changes."""
        errors_widget = self.query_one("#errors", Static)

        # Validate all editors
        validation_errors: list[str] = []
        for key, editor in self._editors.items():
            is_valid, error_msg = editor.validate_value()
            if not is_valid:
                validation_errors.append(f"{key}: {error_msg}")

        if validation_errors:
            error_text = "\n".join(validation_errors)
            errors_widget.update(
                Panel(error_text, title="Validation Errors", border_style="red")
            )
            return

        # Collect edited values
        edited_values = {}
        for key, editor in self._editors.items():
            try:
                edited_values[key] = editor.get_parsed_value()
            except Exception as e:
                validation_errors.append(f"{key}: {e}")

        if validation_errors:
            error_text = "\n".join(validation_errors)
            errors_widget.update(
                Panel(error_text, title="Parse Errors", border_style="red")
            )
            return

        # Get current config
        if hasattr(self.session, "config") and hasattr(self.session.config, "config"):
            config = self.session.config.config
            config_manager = self.session.config
        else:
            from ccbt.config.config import get_config, init_config

            config = get_config()
            config_manager = init_config()

        # Update section config (handle nested sections)
        # Special case: "disk.xet" - xet settings are attributes of DiskConfig, not a nested object
        if self.section_name == "disk.xet":
            # Update xet_* attributes directly on disk config
            section_config = config.disk
            section_dict = (
                section_config.model_dump()
                if hasattr(section_config, "model_dump")
                else {}
            )
            # Only update xet_* attributes
            for key, value in edited_values.items():
                if key.startswith("xet_"):
                    section_dict[key] = value

            # Reconstruct disk config object with updated xet attributes
            section_model_class = type(section_config)
            try:
                new_section_config = section_model_class(**section_dict)
                config.disk = new_section_config
            except Exception as e:
                errors_widget.update(
                    Panel(
                        f"Failed to create config object: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
                return
        else:
            # Normal nested section handling
            section_parts = self.section_name.split(".")
            parent_config = config
            for part in section_parts[:-1]:
                parent_config = getattr(parent_config, part)

            section_config = getattr(parent_config, section_parts[-1])
            section_dict = (
                section_config.model_dump()
                if hasattr(section_config, "model_dump")
                else {}
            )
            section_dict.update(edited_values)

            # Reconstruct section config object
            section_model_class = type(section_config)
            try:
                new_section_config = section_model_class(**section_dict)
                setattr(parent_config, section_parts[-1], new_section_config)
            except Exception as e:
                errors_widget.update(
                    Panel(
                        f"Failed to create config object: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
                return

        # Validate full config
        is_valid, config_errors = config_manager.validate_detailed()
        if not is_valid:
            error_text = "\n".join(config_errors)
            errors_widget.update(
                Panel(error_text, title="Configuration Errors", border_style="red")
            )
            return

        # Apply runtime changes
        try:
            set_config(config)
            # Mark changes as saved and update original values
            self._has_unsaved_changes = False
            # Update original values to current values after successful save
            if hasattr(self, "_original_values"):
                for key, editor in self._editors.items():
                    try:
                        self._original_values[key] = editor.get_parsed_value()
                    except Exception:
                        pass
            errors_widget.update(
                Panel(
                    "Configuration updated (runtime only)",
                    title="Success",
                    border_style="green",
                )
            )
        except Exception as e:
            errors_widget.update(
                Panel(f"Failed to apply config: {e}", title="Error", border_style="red")
            )
            return

        # Save to file if requested
        if not runtime_only:
            try:
                if (
                    hasattr(config_manager, "config_file")
                    and config_manager.config_file
                ):
                    config_file = config_manager.config_file
                else:
                    from pathlib import Path

                    config_file = Path.cwd() / "ccbt.toml"

                # Export and write to file
                toml_content = config_manager.export(fmt="toml")
                config_file.write_text(toml_content, encoding="utf-8")
                # Mark changes as saved and update original values
                self._has_unsaved_changes = False
                # Update original values to current values after successful save
                if hasattr(self, "_original_values"):
                    for key, editor in self._editors.items():
                        try:
                            self._original_values[key] = editor.get_parsed_value()
                        except Exception:
                            pass
                errors_widget.update(
                    Panel(
                        f"Configuration saved to {config_file}",
                        title="Success",
                        border_style="green",
                    )
                )
            except Exception as e:
                errors_widget.update(
                    Panel(
                        f"Failed to save to file: {e}",
                        title="Error",
                        border_style="red",
                    )
                )
                return

        # Close screen after successful save
        await asyncio.sleep(1.0)  # Show success message briefly
        self.app.pop_screen()  # type: ignore[attr-defined]

    async def _refresh_metrics(self) -> None:  # pragma: no cover
        """Refresh metrics display based on the current section."""
        try:
            metrics_widget = self.query_one("#metrics_section", Static)
            section_name = self.section_name

            # Map section names to their metrics display methods
            if section_name == "disk" or section_name.startswith("disk."):
                await self._display_disk_metrics_comprehensive(metrics_widget)
            elif section_name == "network" or section_name.startswith("network."):
                await self._display_network_metrics_comprehensive(metrics_widget)
            elif section_name == "queue":
                await self._display_queue_metrics(metrics_widget)
            elif (
                section_name == "discovery"
                or "tracker" in section_name.lower()
                or "dht" in section_name.lower()
            ):
                await self._display_discovery_metrics_comprehensive(metrics_widget)
            elif section_name == "observability":
                await self._display_system_resources_metrics(metrics_widget)
            else:
                # No metrics for this section
                metrics_widget.update("")
        except Exception as e:
            # Silently fail metrics refresh to avoid disrupting config editing
            logger.debug(
                f"Failed to refresh metrics for section {self.section_name}: {e}"
            )

    async def _display_disk_io_metrics(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display disk I/O metrics."""
        try:
            from rich.table import Table

            from ccbt.storage.disk_io_init import get_disk_io_manager

            disk_io = get_disk_io_manager()
            if not disk_io or not disk_io._running:  # type: ignore[attr-defined]
                widget.update("")
                return

            stats = disk_io.stats
            cache_stats = disk_io.get_cache_stats()

            table = Table(
                title="Disk I/O Metrics", expand=True, show_header=False, box=None
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            def format_bytes(b: int) -> str:
                if b >= 1024 * 1024 * 1024:
                    return f"{b / (1024**3):.2f} GB"
                if b >= 1024 * 1024:
                    return f"{b / (1024**2):.2f} MB"
                if b >= 1024:
                    return f"{b / 1024:.2f} KB"
                return f"{b} B"

            table.add_row("Total Writes", f"{stats.get('writes', 0):,}")
            table.add_row("Bytes Written", format_bytes(stats.get("bytes_written", 0)))
            table.add_row("Queue Full Errors", str(stats.get("queue_full_errors", 0)))
            table.add_row("Preallocations", str(stats.get("preallocations", 0)))

            if cache_stats:
                table.add_row("", "")
                table.add_row("[bold]Cache Stats[/bold]", "")
                table.add_row("Cache Hits", str(cache_stats.get("hits", 0)))
                table.add_row("Cache Misses", str(cache_stats.get("misses", 0)))
                hit_rate = cache_stats.get("hit_rate", 0.0)
                table.add_row("Hit Rate", f"{hit_rate:.1f}%")

            widget.update(Panel(table))
        except Exception:
            widget.update("")

    async def _display_network_quality_metrics(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display network quality metrics."""
        try:
            from rich.table import Table

            stats = await self.session.get_global_stats()
            all_status = await self.session.get_status()

            table = Table(
                title="Network Quality Metrics",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            def format_speed(s: float) -> str:
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"

            table.add_row("Total Torrents", str(stats.get("num_torrents", 0)))
            table.add_row("Active Torrents", str(stats.get("num_active", 0)))
            table.add_row(
                "Global Download Rate", format_speed(stats.get("download_rate", 0.0))
            )
            table.add_row(
                "Global Upload Rate", format_speed(stats.get("upload_rate", 0.0))
            )

            # Count active peers (with timeout to prevent blocking)
            total_peers = 0
            peer_count_tasks = []
            for ih in list(all_status.keys())[
                :10
            ]:  # Limit to first 10 torrents to avoid blocking
                try:
                    # Use timeout to prevent hanging
                    task = asyncio.create_task(
                        asyncio.wait_for(
                            self.session.get_peers_for_torrent(ih), timeout=1.0
                        )
                    )
                    peer_count_tasks.append(task)
                except Exception:
                    pass

            # Wait for all peer count tasks with timeout
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*peer_count_tasks, return_exceptions=True),
                    timeout=2.0,
                )
                for peers in results:
                    if isinstance(peers, Exception):
                        continue
                    total_peers += len(peers) if peers else 0
            except (asyncio.TimeoutError, Exception):
                # If timeout or error, just show what we got
                pass

            table.add_row("Total Connected Peers", str(total_peers))

            widget.update(Panel(table))
        except Exception:
            widget.update("")

    async def _display_queue_metrics(self, widget: Static) -> None:  # pragma: no cover
        """Display queue metrics."""
        try:
            from rich.table import Table

            queue_manager = getattr(self.session, "queue_manager", None)
            if not queue_manager:
                widget.update("")
                return

            # Use timeout to prevent blocking
            try:
                queue_status = await asyncio.wait_for(
                    queue_manager.get_queue_status(), timeout=2.0
                )
            except (asyncio.TimeoutError, Exception):
                widget.update("")
                return

            statistics = queue_status.get("statistics", {})

            table = Table(
                title="Queue Metrics", expand=True, show_header=False, box=None
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            table.add_row("Total Torrents", str(statistics.get("total_torrents", 0)))
            table.add_row(
                "Active Downloading", str(statistics.get("active_downloading", 0))
            )
            table.add_row("Active Seeding", str(statistics.get("active_seeding", 0)))
            table.add_row("Queued", str(statistics.get("queued", 0)))
            table.add_row("Paused", str(statistics.get("paused", 0)))

            widget.update(Panel(table))
        except Exception:
            widget.update("")

    async def _display_tracker_metrics(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display tracker metrics."""
        try:
            from rich.table import Table

            tracker_client = getattr(self.session, "tracker", None) or getattr(
                self.session, "tracker_client", None
            )
            if not tracker_client:
                widget.update("")
                return

            session_stats = tracker_client.get_session_stats()
            if not session_stats:
                widget.update("")
                return

            table = Table(title="Tracker Metrics", expand=True)
            table.add_column("Tracker", style="cyan", ratio=2)
            table.add_column("Requests", style="green", ratio=1)
            table.add_column("Avg Response", style="yellow", ratio=1)
            table.add_column("Error Rate", style="red", ratio=1)

            for host, stats in list(session_stats.items())[:5]:  # Limit to 5 trackers
                request_count = stats.get("request_count", 0)
                avg_response = stats.get("average_request_time", 0.0)
                error_rate = stats.get("error_rate", 0.0)

                if avg_response < 0.001:
                    response_str = f"{avg_response * 1000:.2f} ms"
                else:
                    response_str = f"{avg_response:.3f} s"

                error_display = f"{error_rate:.2f}%"
                if error_rate == 0:
                    error_display = f"[green]{error_display}[/green]"
                elif error_rate < 10:
                    error_display = f"[yellow]{error_display}[/yellow]"
                else:
                    error_display = f"[red]{error_display}[/red]"

                table.add_row(
                    host[:40], str(request_count), response_str, error_display
                )

            widget.update(Panel(table))
        except Exception:
            widget.update("")

    async def _display_system_resources_metrics(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display system resources metrics."""
        try:
            from rich.table import Table

            if not self.metrics_collector or not self.metrics_collector.running:
                widget.update("")
                return

            system_metrics = self.metrics_collector.get_system_metrics()

            table = Table(
                title="System Resources Metrics",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Resource", style="cyan", ratio=1)
            table.add_column("Usage", style="green", ratio=2)

            cpu = system_metrics.get("cpu_usage", 0.0)
            memory = system_metrics.get("memory_usage", 0.0)
            disk = system_metrics.get("disk_usage", 0.0)
            process_count = system_metrics.get("process_count", 0)

            table.add_row("CPU", f"{cpu:.1f}%")
            table.add_row("Memory", f"{memory:.1f}%")
            table.add_row("Disk", f"{disk:.1f}%")
            table.add_row("Processes", str(process_count))

            widget.update(Panel(table))
        except Exception:
            widget.update("")

    async def _display_disk_metrics_comprehensive(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display comprehensive disk metrics including I/O stats and analysis."""
        try:
            from rich.table import Table

            from ccbt.config.config import get_config
            from ccbt.config.config_capabilities import SystemCapabilities
            from ccbt.storage.disk_io_init import get_disk_io_manager

            # Start with disk I/O metrics
            await self._display_disk_io_metrics(widget)

            # Get the current content and append analysis
            current_content = (
                widget.renderable if hasattr(widget, "renderable") else None
            )

            # Get storage detection info
            config = get_config()
            capabilities = SystemCapabilities()
            download_path = config.disk.download_path or "."
            storage_type = capabilities.detect_storage_type(download_path)
            storage_speed = capabilities.detect_storage_speed(download_path)

            # Create comprehensive table
            table = Table(
                title="Disk Configuration & Analysis",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            # Storage detection
            table.add_row("[bold]Storage Detection[/bold]", "")
            table.add_row("Storage Type", storage_type.upper())
            table.add_row(
                "Speed Category", storage_speed.get("speed_category", "unknown")
            )
            table.add_row(
                "Est. Read Speed",
                f"{storage_speed.get('estimated_read_mbps', 0):.0f} MB/s",
            )
            table.add_row(
                "Est. Write Speed",
                f"{storage_speed.get('estimated_write_mbps', 0):.0f} MB/s",
            )

            # Configuration recommendations
            table.add_row("", "")
            table.add_row("[bold]Current Configuration[/bold]", "")
            table.add_row("Disk Workers", str(config.disk.disk_workers))
            table.add_row(
                "Write Batch Timeout", f"{config.disk.write_batch_timeout_ms} ms"
            )
            table.add_row(
                "Hash Chunk Size", f"{config.disk.hash_chunk_size // 1024} KB"
            )

            # Combine with I/O stats if available
            disk_io = get_disk_io_manager()
            if disk_io and disk_io._running:  # type: ignore[attr-defined]
                stats = disk_io.stats
                cache_stats = disk_io.get_cache_stats()

                table.add_row("", "")
                table.add_row("[bold]I/O Statistics[/bold]", "")
                table.add_row("Total Writes", f"{stats.get('writes', 0):,}")

                def format_bytes(b: int) -> str:
                    if b >= 1024 * 1024 * 1024:
                        return f"{b / (1024**3):.2f} GB"
                    if b >= 1024 * 1024:
                        return f"{b / (1024**2):.2f} MB"
                    if b >= 1024:
                        return f"{b / 1024:.2f} KB"
                    return f"{b} B"

                table.add_row(
                    "Bytes Written", format_bytes(stats.get("bytes_written", 0))
                )

                if cache_stats:
                    hit_rate = cache_stats.get("hit_rate_percent", 0.0)
                    table.add_row("Cache Hit Rate", f"{hit_rate:.2f}%")

            widget.update(Panel(table))
        except Exception as e:
            logger.debug(f"Error displaying comprehensive disk metrics: {e}")
            await self._display_disk_io_metrics(widget)

    async def _display_network_metrics_comprehensive(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display comprehensive network metrics including quality and performance."""
        try:
            from rich.table import Table

            # Start with network quality metrics (with timeout to prevent blocking)
            try:
                stats = await asyncio.wait_for(
                    self.session.get_global_stats(), timeout=2.0
                )
                all_status = await asyncio.wait_for(
                    self.session.get_status(), timeout=2.0
                )
            except (asyncio.TimeoutError, Exception):
                widget.update("")
                return

            table = Table(
                title="Network Performance Metrics",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            def format_speed(s: float) -> str:
                if s >= 1024 * 1024:
                    return f"{s / (1024**2):.2f} MB/s"
                if s >= 1024:
                    return f"{s / 1024:.2f} KB/s"
                return f"{s:.2f} B/s"

            table.add_row("[bold]Global Statistics[/bold]", "")
            table.add_row("Total Torrents", str(stats.get("num_torrents", 0)))
            table.add_row("Active Torrents", str(stats.get("num_active", 0)))
            table.add_row(
                "Global Download Rate", format_speed(stats.get("download_rate", 0.0))
            )
            table.add_row(
                "Global Upload Rate", format_speed(stats.get("upload_rate", 0.0))
            )

            # Count active peers (with timeout to prevent blocking)
            total_peers = 0
            peer_count_tasks = []
            for ih in list(all_status.keys())[
                :10
            ]:  # Limit to first 10 torrents to avoid blocking
                try:
                    task = asyncio.create_task(
                        asyncio.wait_for(
                            self.session.get_peers_for_torrent(ih), timeout=1.0
                        )
                    )
                    peer_count_tasks.append(task)
                except Exception:
                    pass

            # Wait for all peer count tasks with timeout
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*peer_count_tasks, return_exceptions=True),
                    timeout=2.0,
                )
                for peers in results:
                    if isinstance(peers, Exception):
                        continue
                    total_peers += len(peers) if peers else 0
            except (asyncio.TimeoutError, Exception):
                pass

            table.add_row("Total Connected Peers", str(total_peers))

            # Add configuration info
            from ccbt.config.config import get_config

            config = get_config()
            table.add_row("", "")
            table.add_row("[bold]Network Configuration[/bold]", "")
            table.add_row("Max Global Peers", str(config.network.max_global_peers))
            table.add_row(
                "Max Peers Per Torrent", str(config.network.max_peers_per_torrent)
            )
            table.add_row(
                "Connection Timeout", f"{config.network.connection_timeout} s"
            )

            widget.update(Panel(table))
        except Exception as e:
            logger.debug(f"Error displaying comprehensive network metrics: {e}")
            await self._display_network_quality_metrics(widget)

    async def _display_discovery_metrics_comprehensive(
        self, widget: Static
    ) -> None:  # pragma: no cover
        """Display comprehensive discovery metrics including DHT and tracker stats."""
        try:
            from rich.table import Table

            # Create combined table
            table = Table(
                title="Discovery Metrics (DHT & Trackers)",
                expand=True,
                show_header=False,
                box=None,
            )
            table.add_column("Metric", style="cyan", ratio=1)
            table.add_column("Value", style="green", ratio=2)

            # DHT Metrics
            try:
                dht_client = self.session.dht()
                if dht_client:
                    dht_stats = dht_client.get_stats()
                    routing_stats = dht_stats.get("routing_table", {})

                    table.add_row("[bold]DHT Statistics[/bold]", "")
                    table.add_row(
                        "Total Nodes", str(routing_stats.get("total_nodes", 0))
                    )
                    table.add_row("Good Nodes", str(routing_stats.get("good_nodes", 0)))
                    table.add_row("Bad Nodes", str(routing_stats.get("bad_nodes", 0)))
                    table.add_row(
                        "Pending Queries", str(dht_stats.get("pending_queries", 0))
                    )

                    query_stats = dht_stats.get("query_statistics", {})
                    queries_sent = query_stats.get("queries_sent", 0)
                    queries_successful = query_stats.get("queries_successful", 0)
                    if queries_sent > 0:
                        success_rate = (queries_successful / queries_sent) * 100
                        table.add_row("Query Success Rate", f"{success_rate:.1f}%")
            except Exception:
                table.add_row("[bold]DHT Statistics[/bold]", "Not available")

            # Tracker Metrics
            table.add_row("", "")
            try:
                tracker_client = getattr(self.session, "tracker", None) or getattr(
                    self.session, "tracker_client", None
                )
                if tracker_client:
                    session_stats = tracker_client.get_session_stats()
                    if session_stats:
                        table.add_row("[bold]Tracker Statistics[/bold]", "")
                        total_requests = sum(
                            s.get("request_count", 0) for s in session_stats.values()
                        )
                        total_errors = sum(
                            s.get("error_count", 0) for s in session_stats.values()
                        )
                        table.add_row("Total Requests", str(total_requests))
                        table.add_row("Total Errors", str(total_errors))
                        if total_requests > 0:
                            error_rate = (total_errors / total_requests) * 100
                            table.add_row("Error Rate", f"{error_rate:.1f}%")
                        table.add_row("Active Trackers", str(len(session_stats)))
            except Exception:
                table.add_row("[bold]Tracker Statistics[/bold]", "Not available")

            widget.update(Panel(table))
        except Exception as e:
            logger.debug(f"Error displaying comprehensive discovery metrics: {e}")
            await self._display_tracker_metrics(widget)

