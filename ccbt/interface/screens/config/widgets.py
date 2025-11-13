"""Configuration widgets for editing config values."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.widgets import Input, Static
else:
    try:
        from textual.widgets import Input, Static
    except ImportError:
        Input = None  # type: ignore[assignment, misc]
        Static = None  # type: ignore[assignment, misc]


class ConfigValueEditor(Input):  # type: ignore[misc]
    """Widget for editing a single configuration value with validation."""

    def __init__(
        self,
        option_key: str,
        current_value: Any,
        value_type: str = "string",
        description: str = "",
        constraints: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ):  # pragma: no cover
        """Initialize config value editor.

        Args:
            option_key: Configuration option key
            current_value: Current value
            value_type: Expected type (bool, int, float, str, list)
            description: Option description
            constraints: Validation constraints (min, max, etc.)
        """
        # Format initial value for display
        if value_type == "bool":
            initial_value = "true" if current_value else "false"
        elif value_type == "list":
            initial_value = (
                ",".join(str(v) for v in current_value)
                if isinstance(current_value, list)
                else str(current_value)
            )
        else:
            initial_value = str(current_value)

        super().__init__(value=initial_value, *args, **kwargs)
        self.option_key = option_key
        self.value_type = value_type
        self.description = description
        self.constraints = constraints or {}
        self._original_value = current_value
        self._validation_error: str | None = None
        # Don't set validators on Input - we'll validate manually
        self.validators = None

    def get_parsed_value(self) -> Any:  # pragma: no cover
        """Parse and return the current value."""
        value_str = self.value.strip()

        if self.value_type == "bool":
            low = value_str.lower()
            if low in ("true", "1", "yes", "on"):
                return True
            if low in ("false", "0", "no", "off"):
                return False
            raise ValueError(f"Invalid boolean value: {value_str}")

        if self.value_type == "int":
            value = int(value_str)
            if "minimum" in self.constraints and value < self.constraints["minimum"]:
                raise ValueError(f"Value must be >= {self.constraints['minimum']}")
            if "maximum" in self.constraints and value > self.constraints["maximum"]:
                raise ValueError(f"Value must be <= {self.constraints['maximum']}")
            return value

        if self.value_type == "number" or self.value_type == "float":
            value = float(value_str)
            if "minimum" in self.constraints and value < self.constraints["minimum"]:
                raise ValueError(f"Value must be >= {self.constraints['minimum']}")
            if "maximum" in self.constraints and value > self.constraints["maximum"]:
                raise ValueError(f"Value must be <= {self.constraints['maximum']}")
            return value

        if self.value_type == "list":
            if not value_str:
                return []
            return [item.strip() for item in value_str.split(",") if item.strip()]

        # string
        return value_str

    def validate_value(
        self, value: str | None = None
    ) -> tuple[bool, str]:  # pragma: no cover
        """Validate the current value or a provided value.

        Args:
            value: Optional value to validate. If None, validates self.value.
                  This allows compatibility with Textual's Input validation mechanism.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # If value is provided, temporarily use it for validation
            if value is not None:
                original_value = self.value
                self.value = value
                try:
                    parsed = self.get_parsed_value()
                    self.value = original_value
                    self._validation_error = None
                    return True, ""
                except Exception as e:
                    self.value = original_value
                    self._validation_error = str(e)
                    return False, str(e)
            else:
                # Validate current value
                parsed = self.get_parsed_value()
                self._validation_error = None
                return True, ""
        except ValueError as e:
            self._validation_error = str(e)
            return False, str(e)
        except Exception as e:
            self._validation_error = str(e)
            return False, f"Invalid {self.value_type}: {e}"


class ConfigSectionWidget(Static):  # type: ignore[misc]
    """Base widget for displaying/editing a configuration section."""

    def __init__(
        self, section_name: str, *args: Any, **kwargs: Any
    ):  # pragma: no cover
        """Initialize configuration section widget."""
        super().__init__(*args, **kwargs)
        self.section_name = section_name
        self._editors: dict[str, ConfigValueEditor] = {}
        self._values: dict[str, Any] = {}

    def update_from_config(self, config: Any) -> None:  # pragma: no cover
        """Update widget with configuration values."""
        # Subclasses should override this

    def get_values(self) -> dict[str, Any]:  # pragma: no cover
        """Get current values from editors."""
        values: dict[str, Any] = {}
        for key, editor in self._editors.items():
            try:
                values[key] = editor.get_parsed_value()
            except Exception:
                values[key] = self._values.get(key)
        return values

    def validate_all(self) -> tuple[bool, list[str]]:  # pragma: no cover
        """Validate all editors.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: list[str] = []
        for key, editor in self._editors.items():
            is_valid, error_msg = editor.validate_value()
            if not is_valid:
                errors.append(f"{key}: {error_msg}")
        return len(errors) == 0, errors

