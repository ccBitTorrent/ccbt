"""Factory for creating appropriate config widgets based on schema metadata."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ccbt.config.config_schema import ConfigSchema

if TYPE_CHECKING:
    from textual.widgets import Checkbox, Input, Select, Static
else:
    try:
        from textual.widgets import Checkbox, Input, Select, Static
    except ImportError:
        Checkbox = None  # type: ignore[assignment, misc]
        Input = None  # type: ignore[assignment, misc]
        Select = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]

from ccbt.interface.screens.config.widgets import ConfigValueEditor
from ccbt.i18n import _

logger = logging.getLogger(__name__)


def create_config_widget(
    option_key: str,
    current_value: Any,
    section_name: str,
    option_metadata: dict[str, Any] | None = None,
    *args: Any,
    **kwargs: Any,
) -> Checkbox | Select | ConfigValueEditor:
    """Create appropriate widget for a configuration option.
    
    Args:
        option_key: Configuration option key
        current_value: Current value
        section_name: Section name (e.g., "network", "security.ssl")
        option_metadata: Optional metadata dict from schema
        *args: Additional positional args for widget
        **kwargs: Additional keyword args for widget
    
    Returns:
        Appropriate widget (Checkbox, Select, or ConfigValueEditor)
    """
    # Get metadata from schema if not provided
    if option_metadata is None:
        key_path = f"{section_name}.{option_key}"
        option_metadata = ConfigSchema.get_option_metadata(key_path)
    
    # Determine value type
    value_type = option_metadata.get("type", "string") if option_metadata else "string"
    description = option_metadata.get("description", "") if option_metadata else ""
    constraints = {}
    
    if option_metadata:
        if "minimum" in option_metadata:
            constraints["minimum"] = option_metadata["minimum"]
        if "maximum" in option_metadata:
            constraints["maximum"] = option_metadata["maximum"]
    
    # Infer type from value if not in schema
    if value_type == "string" or value_type == "unknown":
        if isinstance(current_value, bool):
            value_type = "bool"
        elif isinstance(current_value, int):
            value_type = "int"
        elif isinstance(current_value, float):
            value_type = "float"
        elif isinstance(current_value, list):
            value_type = "list"
    
    # Check for enum values
    enum_values = None
    if option_metadata:
        # Check for enum in schema
        if "enum" in option_metadata:
            enum_values = option_metadata["enum"]
        elif "anyOf" in option_metadata:
            # Pydantic Literal types generate anyOf with const values
            any_of = option_metadata["anyOf"]
            const_values = []
            for item in any_of:
                if "const" in item:
                    const_values.append(item["const"])
            if const_values:
                enum_values = const_values
    
    # Create appropriate widget
    widget_id = kwargs.pop("id", f"editor_{option_key}")
    
    if value_type == "bool":
        # Use Checkbox for boolean values
        try:
            checkbox = Checkbox(
                description or option_key,
                value=bool(current_value),
                id=widget_id,
                *args,
                **kwargs,
            )
            # Store metadata for value retrieval
            checkbox.option_key = option_key  # type: ignore[attr-defined]
            checkbox.value_type = "bool"  # type: ignore[attr-defined]
            checkbox.description = description  # type: ignore[attr-defined]
            checkbox._original_value = current_value  # type: ignore[attr-defined]
            checkbox.can_focus = True  # type: ignore[attr-defined]
            return checkbox
        except Exception as e:
            logger.debug("Error creating checkbox, falling back to input: %s", e)
            # Fallback to Input
            return ConfigValueEditor(
                option_key=option_key,
                current_value=current_value,
                value_type="bool",
                description=description,
                constraints=constraints,
                id=widget_id,
                *args,
                **kwargs,
            )
    
    elif enum_values:
        # Use Select for enum values
        try:
            # Convert enum values to strings for Select
            options_list = [(str(v), str(v)) for v in enum_values]
            current_str = str(current_value)
            
            # Find current value index
            current_index = 0
            for idx, (val, _) in enumerate(options_list):
                if val == current_str:
                    current_index = idx
                    break
            
            select = Select(
                options_list,
                value=current_index,
                id=widget_id,
                *args,
                **kwargs,
            )
            # Store metadata for value retrieval
            select.option_key = option_key  # type: ignore[attr-defined]
            select.value_type = value_type  # type: ignore[attr-defined]
            select.description = description  # type: ignore[attr-defined]
            select._original_value = current_value  # type: ignore[attr-defined]
            select._enum_values = enum_values  # type: ignore[attr-defined]
            select.can_focus = True  # type: ignore[attr-defined]
            return select
        except Exception as e:
            logger.debug("Error creating select, falling back to input: %s", e)
            # Fallback to Input
            return ConfigValueEditor(
                option_key=option_key,
                current_value=current_value,
                value_type=value_type,
                description=description,
                constraints=constraints,
                id=widget_id,
                *args,
                **kwargs,
            )
    
    else:
        # Use ConfigValueEditor (Input) for other types
        return ConfigValueEditor(
            option_key=option_key,
            current_value=current_value,
            value_type=value_type,
            description=description,
            constraints=constraints,
            id=widget_id,
            *args,
            **kwargs,
        )


def get_widget_value(widget: Any) -> Any:
    """Get the current value from a config widget.
    
    Args:
        widget: Widget instance (Checkbox, Select, or ConfigValueEditor)
    
    Returns:
        Parsed value from the widget
    """
    if hasattr(widget, "value_type"):
        widget_type = widget.value_type  # type: ignore[attr-defined]
    else:
        widget_type = "string"
    
    # Handle Checkbox
    if hasattr(widget, "value") and isinstance(widget.value, bool):
        return widget.value
    
    # Handle Select
    if hasattr(widget, "_enum_values"):
        enum_values = widget._enum_values  # type: ignore[attr-defined]
        if hasattr(widget, "value"):
            selected_value = widget.value  # type: ignore[attr-defined]
            # Select.value can be either an index (int) or the actual value
            if isinstance(selected_value, int) and 0 <= selected_value < len(enum_values):
                return enum_values[selected_value]
            # If it's already the value, return it
            if selected_value in enum_values:
                return selected_value
            # Try to get selected value from Select widget's internal state
            if hasattr(widget, "selected_value"):
                return widget.selected_value  # type: ignore[attr-defined]
            # Try to get from Select's options
            if hasattr(widget, "options") and hasattr(widget, "value"):
                try:
                    options = widget.options  # type: ignore[attr-defined]
                    if isinstance(options, list) and isinstance(selected_value, int):
                        if 0 <= selected_value < len(options):
                            option_tuple = options[selected_value]
                            if isinstance(option_tuple, tuple) and len(option_tuple) >= 2:
                                return option_tuple[1]  # Return the value (second element)
                except Exception:
                    pass
    
    # Handle ConfigValueEditor (Input)
    if hasattr(widget, "get_parsed_value"):
        return widget.get_parsed_value()
    
    # Fallback: try to get value directly
    if hasattr(widget, "value"):
        return widget.value  # type: ignore[attr-defined]
    
    return None


def validate_widget_value(widget: Any) -> tuple[bool, str]:
    """Validate a config widget's value.
    
    Args:
        widget: Widget instance
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Checkbox and Select are always valid (they can't have invalid states)
    if hasattr(widget, "value_type"):
        widget_type = widget.value_type  # type: ignore[attr-defined]
        if widget_type == "bool" or hasattr(widget, "_enum_values"):
            return True, ""
    
    # Use widget's validation if available
    if hasattr(widget, "validate_value"):
        return widget.validate_value()
    
    return True, ""

