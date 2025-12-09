"""Template system for managing ASCII art templates.

Provides a unified interface for loading, validating, and normalizing ASCII art templates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Template:
    """Represents an ASCII art template.
    
    Attributes:
        name: Template identifier
        content: Raw ASCII art content
        normalized_lines: Normalized lines for consistent rendering
        metadata: Additional template metadata
    """
    
    name: str
    content: str
    normalized_lines: list[str] | None = None
    metadata: dict[str, Any] | None = None
    
    def __post_init__(self) -> None:
        """Initialize template after creation."""
        if self.normalized_lines is None:
            self.normalized_lines = self.normalize()
        if self.metadata is None:
            self.metadata = {}
    
    def normalize(self) -> list[str]:
        """Normalize template lines for consistent alignment.
        
        This applies the same normalization logic used in rainbow animations
        to ensure consistent alignment across all animation types.
        
        Returns:
            List of normalized lines ready for centering
        """
        raw_lines = self.content.split("\n")
        lines = []
        
        # Find the minimum leading whitespace across all non-empty lines
        min_leading_spaces = float('inf')
        for line in raw_lines:
            stripped = line.rstrip()
            if stripped:  # Only consider non-empty lines
                leading_spaces = len(stripped) - len(stripped.lstrip())
                min_leading_spaces = min(min_leading_spaces, leading_spaces)
        
        # Normalize all lines to have the same leading whitespace (minimum found)
        for i, line in enumerate(raw_lines):
            if line.strip():  # Keep lines that have any content
                processed_line = line.rstrip()  # Only strip trailing whitespace
                
                # Ensure consistent leading whitespace for proper centering
                current_leading = len(processed_line) - len(processed_line.lstrip())
                if current_leading < min_leading_spaces:
                    # Add spaces to match minimum leading whitespace
                    processed_line = " " * (min_leading_spaces - current_leading) + processed_line
                
                # Apply specific corrections for LOGO_1 alignment
                if i == 0:
                    # Remove leading spaces from first row (move left)
                    if processed_line.startswith("    "):
                        processed_line = processed_line[4:]
                    elif processed_line.startswith("   "):
                        processed_line = processed_line[3:]
                    elif processed_line.startswith("  "):
                        processed_line = processed_line[2:]
                    elif processed_line.startswith(" "):
                        processed_line = processed_line[1:]
                elif i == 1:
                    processed_line = "  " + processed_line  # Add two leading spaces to second row
                
                lines.append(processed_line)
        
        return lines
    
    def validate(self) -> tuple[bool, str | None]:
        """Validate template content.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.content or not self.content.strip():
            return False, "Template content is empty"
        
        if not self.name:
            return False, "Template name is required"
        
        # Check for minimum content
        lines = [line for line in self.content.split("\n") if line.strip()]
        if len(lines) < 1:
            return False, "Template must have at least one non-empty line"
        
        return True, None
    
    def get_lines(self) -> list[str]:
        """Get normalized lines.
        
        Returns:
            List of normalized lines
        """
        if self.normalized_lines is None:
            self.normalized_lines = self.normalize()
        return self.normalized_lines
    
    def get_width(self) -> int:
        """Get maximum width of template.
        
        Returns:
            Maximum line width
        """
        lines = self.get_lines()
        return max(len(line) for line in lines) if lines else 0
    
    def get_height(self) -> int:
        """Get height of template.
        
        Returns:
            Number of lines
        """
        return len(self.get_lines())


class TemplateRegistry:
    """Registry for managing templates."""
    
    def __init__(self) -> None:
        """Initialize template registry."""
        self._templates: dict[str, Template] = {}
    
    def register(self, template: Template) -> None:
        """Register a template.
        
        Args:
            template: Template to register
        """
        is_valid, error = template.validate()
        if not is_valid:
            raise ValueError(f"Invalid template '{template.name}': {error}")
        
        self._templates[template.name] = template
    
    def get(self, name: str) -> Template | None:
        """Get a template by name.
        
        Args:
            name: Template name
            
        Returns:
            Template instance or None if not found
        """
        return self._templates.get(name)
    
    def list(self) -> list[str]:
        """List all registered template names.
        
        Returns:
            List of template names
        """
        return list(self._templates.keys())
    
    def load_from_module(self, module_name: str, template_name: str, content: str) -> Template:
        """Load template from module content.
        
        Args:
            module_name: Name of the module (e.g., 'logo_1')
            template_name: Name for the template
            content: ASCII art content
            
        Returns:
            Template instance
        """
        template = Template(
            name=template_name,
            content=content,
            metadata={"source_module": module_name}
        )
        self.register(template)
        return template


# Global template registry instance
_registry = TemplateRegistry()


def get_registry() -> TemplateRegistry:
    """Get the global template registry.
    
    Returns:
        TemplateRegistry instance
    """
    return _registry


def register_template(template: Template) -> None:
    """Register a template in the global registry.
    
    Args:
        template: Template to register
    """
    _registry.register(template)


def get_template(name: str) -> Template | None:
    """Get a template from the global registry.
    
    Args:
        name: Template name
        
    Returns:
        Template instance or None if not found
    """
    return _registry.get(name)


def load_default_templates() -> None:
    """Load default templates from ascii_art module."""
    try:
        from ccbt.interface.splash.ascii_art.logo_1 import LOGO_1
        from ccbt.interface.splash.ascii_art import (
            CCBT_TITLE,
            CCBT_TITLE_BLOCK,
            CCBT_TITLE_PIPE,
            CCBT_TITLE_SLASH,
            CCBT_TITLE_DASH,
            CCBT_TITLE_BACKSLASH,
            ROW_BOAT,
            NAUTICAL_SHIP,
            SAILING_SHIP_TRINIDAD,
        )
        
        # Register logo templates
        _registry.load_from_module("logo_1", "logo_1", LOGO_1)
        _registry.load_from_module("ascii_art", "ccbt_title", CCBT_TITLE)
        _registry.load_from_module("ascii_art", "ccbt_title_block", CCBT_TITLE_BLOCK)
        _registry.load_from_module("ascii_art", "ccbt_title_pipe", CCBT_TITLE_PIPE)
        _registry.load_from_module("ascii_art", "ccbt_title_slash", CCBT_TITLE_SLASH)
        _registry.load_from_module("ascii_art", "ccbt_title_dash", CCBT_TITLE_DASH)
        _registry.load_from_module("ascii_art", "ccbt_title_backslash", CCBT_TITLE_BACKSLASH)
        
        # Register ship templates
        _registry.load_from_module("ascii_art", "row_boat", ROW_BOAT)
        _registry.load_from_module("ascii_art", "nautical_ship", NAUTICAL_SHIP)
        _registry.load_from_module("ascii_art", "sailing_ship_trinidad", SAILING_SHIP_TRINIDAD)
        
    except ImportError as e:
        # Templates will be loaded lazily when needed
        pass














