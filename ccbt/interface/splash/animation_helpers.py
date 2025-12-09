"""Animation helper utilities for splash screen.

Provides frame rendering, colorization, and timing control for ASCII animations.
"""

from __future__ import annotations

import asyncio
import math
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Group
    from ccbt.interface.splash.animation_config import BackgroundConfig

if TYPE_CHECKING:
    from rich.console import Console
    from rich.text import Text
else:
    try:
        from rich.console import Console
        from rich.text import Text
    except ImportError:
        Console = None  # type: ignore[assignment, misc]
        Text = None  # type: ignore[assignment, misc]
    
    # Import BackgroundConfig at runtime
    try:
        from ccbt.interface.splash.animation_config import BackgroundConfig
    except ImportError:
        BackgroundConfig = Any  # type: ignore[assignment, misc]


class ColorPalette:
    """Ocean-themed color palette for animations."""

    # Ocean colors
    OCEAN_BLUE = "bright_blue"
    DEEP_BLUE = "blue"
    TURQUOISE = "cyan"
    WAVE_WHITE = "bright_white"

    # Tropical colors
    SUNSET_ORANGE = "bright_red"
    SUNSET_YELLOW = "yellow"
    TROPICAL_GREEN = "bright_green"
    PALM_GREEN = "green"

    # Pirate colors
    PIRATE_BLACK = "black"
    GOLD = "bright_yellow"
    SILVER = "white"
    BONE_WHITE = "bright_white"

    # Beach colors
    SAND = "yellow3"
    BEACH_TAN = "bright_yellow"
    CORAL = "bright_magenta"
    SHELL_PINK = "bright_white"

    # Holiday colors
    HOLIDAY_RED = "bright_red"
    HOLIDAY_GREEN = "bright_green"
    HOLIDAY_BLUE = "bright_blue"
    HOLIDAY_GOLD = "yellow"


class FrameRenderer:
    """Renders ASCII art frames with Rich styling."""

    def __init__(self, console: Console | None = None, splash_screen: Any = None) -> None:
        """Initialize frame renderer.
        
        Args:
            console: Optional Rich Console instance
            splash_screen: Optional SplashScreen instance for overlay integration

        """
        if console is None:
            try:
                from rich.console import Console
                self.console = Console()
            except ImportError:
                self.console = None  # type: ignore[assignment]
        else:
            self.console = console
        self.splash_screen = splash_screen  # Store reference to splash screen for overlay

    def render_frame(
        self,
        ascii_art: str,
        color: str = "white",
        center: bool = True,
        clear: bool = False,
    ) -> Any:
        """Render a single ASCII art frame.
        
        Args:
            ascii_art: ASCII art string to render
            color: Color style to apply
            center: Whether to center the frame
            clear: Whether to clear console before rendering

        Returns:
            Renderable object (Text or Group with overlay) for use with Live context
        """
        try:
            from rich.text import Text
            from rich.align import Align
            from rich.console import Group
            
            # Create base frame renderable
            text = Text(ascii_art, style=color)
            if center:
                frame_renderable = Align.center(text)
            else:
                frame_renderable = text
            
            # Store frame without overlay - overlay will be added later in a stable way
            # Don't add overlay here to avoid recursion
            
            # Store in splash screen for __rich__ method
            if self.splash_screen:
                self.splash_screen._current_frame = frame_renderable
            
            # If console is available and not in Live context, print directly
            if self.console is None:
                print(ascii_art)
                return frame_renderable

            if clear:
                self.console.clear()
            
            # Print if not in Live context (for backward compatibility)
            # When used with Live, the renderable will be returned and used
            self.console.print(frame_renderable)
            return frame_renderable
        except Exception:
            # Fallback to plain print
            print(ascii_art)

    def render_multi_color_frame(
        self,
        frame_data: list[tuple[str, str]],
        center: bool = True,
        clear: bool = False,
    ) -> None:
        """Render a frame with multiple colors.
        
        Args:
            frame_data: List of (text, color) tuples
            center: Whether to center the frame
            clear: Whether to clear console before rendering

        """
        if self.console is None:
            print("".join(text for text, _ in frame_data))
            return

        if clear:
            self.console.clear()

        try:
            from rich.text import Text
            text = Text()
            for segment, color_style in frame_data:
                text.append(segment, style=color_style)

            if center:
                self.console.print(text, justify="center")
            else:
                self.console.print(text)
        except Exception:
            # Fallback
            print("".join(text for text, _ in frame_data))


class BackgroundRenderer:
    """Renders animated backgrounds for splash screens."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize background renderer.
        
        Args:
            console: Optional Rich Console instance
        """
        if console is None:
            try:
                from rich.console import Console
                self.console = Console()
            except ImportError:
                self.console = None  # type: ignore[assignment]
        else:
            self.console = console

    def generate_background(
        self,
        width: int,
        height: int,
        bg_type: str = "none",
        bg_color: str | list[str] | None = None,
        bg_pattern_char: str = "·",
        bg_pattern_density: float = 0.1,
        bg_star_count: int = 50,
        bg_wave_char: str = "~",
        bg_wave_lines: int = 3,
        bg_flower_petals: int = 6,
        bg_flower_radius: float = 0.3,
        bg_flower_count: int = 1,
        bg_flower_rotation_speed: float = 1.0,
        bg_flower_movement_speed: float = 0.5,
        bg_direction: str = "left_to_right",
        time_offset: float = 0.0,
    ) -> list[str]:
        """Generate background lines.
        
        Args:
            width: Terminal width
            height: Terminal height
            bg_type: Background type (none, solid, gradient, pattern, stars, waves, particles)
            bg_color: Background color(s)
            bg_pattern_char: Character for pattern backgrounds
            bg_pattern_density: Density of pattern elements
            bg_star_count: Number of stars
            bg_wave_char: Character for waves
            bg_wave_lines: Number of wave lines
            time_offset: Time offset for animated backgrounds
            
        Returns:
            List of background lines
        """
        if bg_type == "none" or not bg_color:
            return [" " * width for _ in range(height)]

        lines = []
        
        if bg_type == "solid":
            # Solid color background (can be animated palette)
            # Color selection happens in render_with_background, not here
            for _ in range(height):
                lines.append(" " * width)

        elif bg_type == "gradient":
            # Gradient background - create gradient pattern
            import math
            if isinstance(bg_color, list) and len(bg_color) >= 2:
                start_color = bg_color[0]
                end_color = bg_color[1]
            else:
                start_color = bg_color if isinstance(bg_color, str) else "black"
                end_color = "blue"
            
            # Create gradient pattern (vertical gradient)
            for i in range(height):
                # Create gradient line with varying density
                line = ""
                gradient_progress = i / height if height > 0 else 0
                # Use gradient to create pattern density
                for x in range(width):
                    # Create gradient effect using density
                    if random.random() < (0.1 + gradient_progress * 0.2):
                        line += random.choice(['·', '░', '▒'])
                    else:
                        line += " "
                lines.append(line)

        elif bg_type == "pattern":
            # Pattern background (dots/stars)
            for _ in range(height):
                line = ""
                for _ in range(width):
                    if random.random() < bg_pattern_density:
                        line += bg_pattern_char
                    else:
                        line += " "
                lines.append(line)

        elif bg_type == "stars":
            # Star field background
            stars = []
            for _ in range(bg_star_count):
                stars.append({
                    'x': random.randint(0, width - 1),
                    'y': random.randint(0, height - 1),
                    'char': random.choice(['·', '*', '+', '.']),
                })
            
            for y in range(height):
                line = [" "] * width
                for star in stars:
                    if star['y'] == y:
                        line[star['x']] = star['char']
                lines.append("".join(line))

        elif bg_type == "waves":
            # Animated wave background - full column lengths (spans entire height)
            import math
            for y in range(height):
                line = ""
                wave_offset = int(time_offset * 2) % width
                for x in range(width):
                    # Create wave pattern that spans full width and height
                    # Each row gets a wave pattern across the full width
                    # Use sine wave for smooth horizontal waves
                    wave_period = width / max(bg_wave_lines, 1) if bg_wave_lines > 0 else width
                    wave_x = (x + wave_offset) % width
                    wave_phase = (wave_x / wave_period) * 2 * math.pi if wave_period > 0 else 0
                    
                    # Create multiple wave lines across the height
                    # Each wave line has its own vertical position
                    wave_y_phase = (y / height) * bg_wave_lines * 2 * math.pi if height > 0 else 0
                    combined_phase = wave_phase + wave_y_phase + time_offset
                    wave_value = math.sin(combined_phase)
                    
                    # Draw wave character when wave value is positive (upper half of wave)
                    if wave_value > 0:
                        line += bg_wave_char
                    else:
                        line += " "
                lines.append(line)

        elif bg_type == "particles":
            # Particle background
            for _ in range(height):
                line = ""
                for _ in range(width):
                    if random.random() < bg_pattern_density:
                        line += random.choice(['·', '*', '+', '×'])
                    else:
                        line += " "
                lines.append(line)

        elif bg_type == "flower":
            # Flower pattern background with support for multiple animated flowers
            import math
            normalized_direction = (bg_direction or "orbit").lower()
            rotation_modifier = -1.0 if normalized_direction in {"counter_clockwise", "anticlockwise", "reverse"} else 1.0
            
            # Determine flower size based on count
            if bg_flower_count == 1:
                # Single large flower - make it much larger (80% of screen)
                flower_radius_scale = 0.8
            else:
                # Multiple flowers - smaller individual size
                flower_radius_scale = bg_flower_radius
            
            # Create grid for multiple flowers or single centered flower
            if bg_flower_count == 1:
                # Single large flower centered
                flower_positions = [(width // 2, height // 2, flower_radius_scale)]
            else:
                # Multiple flowers distributed across screen with movement
                flower_positions = []
                grid_cols = int(math.ceil(math.sqrt(bg_flower_count)))
                grid_rows = int(math.ceil(bg_flower_count / grid_cols))
                
                for i in range(bg_flower_count):
                    col = i % grid_cols
                    row = i // grid_cols
                    
                    # Base position in grid
                    base_x = int((col + 0.5) * width / grid_cols)
                    base_y = int((row + 0.5) * height / grid_rows)
                    
                    # Add movement animation based on time_offset
                    movement_radius = min(width, height) * 0.15
                    phase = time_offset * bg_flower_movement_speed + i * 2 * math.pi / max(bg_flower_count, 1)
                    phase = phase % (2 * math.pi)
                    offset_x = 0
                    offset_y = 0
                    
                    if normalized_direction in {"left_to_right", "right_to_left"}:
                        offset_x = int(math.sin(phase) * movement_radius)
                        if normalized_direction == "right_to_left":
                            offset_x *= -1
                        offset_y = int(math.cos(phase) * movement_radius * 0.25)
                    elif normalized_direction in {"top_to_bottom", "bottom_to_top"}:
                        offset_y = int(math.sin(phase) * movement_radius)
                        if normalized_direction == "bottom_to_top":
                            offset_y *= -1
                        offset_x = int(math.cos(phase) * movement_radius * 0.25)
                    elif normalized_direction in {"diagonal_down", "diagonal_up"}:
                        diag_offset = int(math.sin(phase) * movement_radius)
                        offset_x = diag_offset
                        offset_y = diag_offset if normalized_direction == "diagonal_down" else -diag_offset
                    elif normalized_direction in {"spiral_in", "spiral_out"}:
                        normalized_phase = (phase % (2 * math.pi)) / (2 * math.pi)
                        if normalized_direction == "spiral_out":
                            current_radius = movement_radius * normalized_phase
                        else:
                            current_radius = movement_radius * (1 - normalized_phase)
                        offset_x = int(math.cos(phase) * current_radius)
                        offset_y = int(math.sin(phase) * current_radius)
                    else:
                        movement_angle = rotation_modifier * phase
                        offset_x = int(math.cos(movement_angle) * movement_radius)
                        offset_y = int(math.sin(movement_angle) * movement_radius)
                    
                    flower_x = base_x + offset_x
                    flower_y = base_y + offset_y
                    
                    # Keep flowers within bounds
                    flower_x = max(flower_radius_scale * min(width, height) / 2, 
                                  min(width - flower_radius_scale * min(width, height) / 2, flower_x))
                    flower_y = max(flower_radius_scale * min(width, height) / 2,
                                  min(height - flower_radius_scale * min(width, height) / 2, flower_y))
                    
                    flower_positions.append((flower_x, flower_y, flower_radius_scale))
            
            # Initialize empty grid
            grid = [[" " for _ in range(width)] for _ in range(height)]
            
            # Render each flower
            for flower_idx, (center_x, center_y, radius_scale) in enumerate(flower_positions):
                max_radius = min(width, height) * radius_scale / 2
                
                # Rotation angle for this flower (each flower rotates independently)
                rotation_angle = (
                    rotation_modifier * time_offset * bg_flower_rotation_speed
                    + flower_idx * math.pi / 3
                ) % (2 * math.pi)
                
                for y in range(height):
                    for x in range(width):
                        # Skip if already occupied by another flower (prioritize first flowers)
                        if grid[y][x] != " ":
                            continue
                        
                        # Calculate distance from flower center
                        dx = x - center_x
                        dy = y - center_y
                        distance = math.sqrt(dx * dx + dy * dy)
                        
                        if distance <= max_radius:
                            # Calculate angle relative to flower center
                            angle = math.atan2(dy, dx)
                            # Apply rotation
                            angle = (angle + rotation_angle) % (2 * math.pi)
                            # Normalize angle to 0-2π
                            if angle < 0:
                                angle += 2 * math.pi
                            
                            # Create petal pattern using sine wave
                            # Each petal is a sine wave peak
                            petal_angle = (angle * bg_flower_petals) % (2 * math.pi)
                            petal_value = math.sin(petal_angle)
                            
                            # Normalize distance to 0-1
                            normalized_dist = distance / max_radius if max_radius > 0 else 0
                            
                            # Create flower shape: petals fade from center
                            # Use petal_value to create petal shape, fade with distance
                            if petal_value > 0.3 and normalized_dist < 0.9:
                                # On petal: use flower character
                                grid[y][x] = random.choice(['*', '·', '+', '×', '●', '○'])
                            elif normalized_dist < 0.1:
                                # Center: always filled
                                grid[y][x] = '*'
                            # else: leave as space (already set)
            
            # Convert grid to lines
            for y in range(height):
                lines.append("".join(grid[y]))

        elif bg_type == "perspective_grid":
            lines = self._generate_perspective_grid(
                width=width,
                height=height,
                density=bg_pattern_density,
                vanishing_point=bg_wave_lines,
                time_offset=time_offset,
            )
        elif bg_type == "wireframe_tunnel":
            lines = self._generate_wireframe_tunnel(
                width=width,
                height=height,
                wave_lines=bg_wave_lines,
                time_offset=time_offset,
            )
        else:
            # Default: empty background
            lines = [" " * width for _ in range(height)]

        return lines

    def _generate_perspective_grid(
        self,
        width: int,
        height: int,
        density: float,
        vanishing_point: int | None,
        time_offset: float,
    ) -> list[str]:
        """Generate a faux 3D perspective grid background."""
        density = max(0.05, min(0.4, density))
        horizon = max(1, int(height * 0.35))
        vp = vanishing_point if vanishing_point not in (None, 0) else width // 2
        lines: list[str] = []
        vertical_gap_base = max(2, int(1 / density))
        motion_offset = int(time_offset * 3)

        for y in range(height):
            if y <= horizon:
                # Sky region above the horizon stays empty for contrast
                lines.append(" " * width if y < horizon else "_" * width)
                continue

            depth = y - horizon
            horizontal_spacing = max(1, int((depth + 1) * density * 4))
            vertical_gap = max(1, vertical_gap_base + depth // 3)
            row_chars: list[str] = []

            for x in range(width):
                rel_x = x - vp
                # Columns converge toward the vanishing point
                column_spacing = max(1, int(abs(rel_x) * density) + 1)
                show_vertical = (x + motion_offset) % (column_spacing + horizontal_spacing // 2) == 0
                show_horizontal = depth % vertical_gap == 0

                if show_horizontal:
                    row_chars.append("_")
                elif show_vertical:
                    row_chars.append("|")
                else:
                    row_chars.append(" ")

            lines.append("".join(row_chars))

        return lines

    def _generate_wireframe_tunnel(
        self,
        width: int,
        height: int,
        wave_lines: int,
        time_offset: float,
    ) -> list[str]:
        """Generate a wireframe tunnel background with radial spokes."""
        center_x = width / 2
        center_y = height / 2
        max_radius = max(1.0, min(width, height) / 2)
        ring_count = max(4, wave_lines * 2 if wave_lines > 0 else 8)
        rotation = time_offset * 1.2
        lines: list[str] = []

        for y in range(height):
            row_chars: list[str] = []
            for x in range(width):
                dx = x - center_x
                dy = y - center_y
                distance = math.hypot(dx, dy)
                normalized = distance / max_radius
                ring_index = int(normalized * ring_count)
                angle = math.atan2(dy, dx) + rotation
                # Convert angle to spokes
                spoke_index = int(((angle + math.pi) / (2 * math.pi)) * ring_count * 2)

                on_ring = ring_index < ring_count and ring_index % 2 == 0
                on_spoke = spoke_index % 3 == 0

                if on_ring:
                    row_chars.append("*")
                elif on_spoke:
                    row_chars.append("/")
                else:
                    row_chars.append(" ")

            lines.append("".join(row_chars))

        return lines


class AnimationController:
    """Controls animation timing and frame sequencing."""

    def __init__(
        self,
        frame_renderer: FrameRenderer | None = None,
        default_frame_duration: float = 0.016,  # 60 FPS for ultra-smooth animations
    ) -> None:
        """Initialize animation controller.
        
        Args:
            frame_renderer: Optional FrameRenderer instance
            default_frame_duration: Default duration per frame in seconds (0.033 = 30 FPS)

        """
        self.renderer = frame_renderer or FrameRenderer()
        self.background_renderer = BackgroundRenderer(self.renderer.console)
        self.default_duration = default_frame_duration
    
    def _calculate_frame_duration(self, total_duration: float, num_frames: int | None = None) -> float:
        """Calculate frame duration based on total animation duration.
        
        Args:
            total_duration: Total animation duration in seconds
            num_frames: Optional number of frames (uses default refresh rate if None)
            
        Returns:
            Frame duration in seconds
        """
        if num_frames is None:
            # Use refresh rate of 60 FPS as default for ultra-smooth animations
            num_frames = int(total_duration * 60)
        
        if num_frames <= 0:
            return 0.016  # Default 60 FPS for ultra-smooth animations
        
        frame_duration = total_duration / num_frames
        # Clamp between 0.008 (120 FPS max) and 0.033 (30 FPS min) for ultra-fluid animations
        return max(0.008, min(0.033, frame_duration))
    
    def _adapt_speed_to_duration(self, base_speed: float, duration: float, sequence_duration: float | None = None) -> float:
        """Adapt animation speed based on duration.
        
        Args:
            base_speed: Base speed value
            duration: Current animation duration
            sequence_duration: Total sequence duration (optional)
            
        Returns:
            Adapted speed value
        """
        if sequence_duration is None or sequence_duration <= 0:
            return base_speed
        
        # Scale speed inversely with duration ratio
        duration_ratio = duration / sequence_duration if sequence_duration > 0 else 1.0
        
        if duration_ratio < 0.1:
            # Very short segments: faster speed
            return base_speed * (0.1 / max(duration_ratio, 0.01))
        elif duration_ratio > 0.5:
            # Long segments: slower speed
            return base_speed * (0.5 / duration_ratio)
        else:
            # Normal segments: keep base speed
            return base_speed
    
    def normalize_logo_lines(self, logo_text: str) -> list[str]:
        """Normalize logo lines for proper alignment.
        
        This function applies the same normalization logic used in rainbow animations
        to ensure consistent alignment across all animation types.
        
        Args:
            logo_text: Raw logo text with potentially inconsistent leading whitespace
            
        Returns:
            List of normalized lines ready for centering
        """
        raw_lines = logo_text.split("\n")
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

    def render_with_background(
        self,
        logo_lines: list[Text],
        bg_config: Any,
        time_offset: float = 0.0,
        text_color: str | list[str] | None = None,
    ) -> Group:
        """Render logo lines with background.
        
        Args:
            logo_lines: List of Rich Text objects for logo
            bg_config: BackgroundConfig instance
            time_offset: Time offset for animated backgrounds
            text_color: Optional text color (overrides colors in logo_lines)
            
        Returns:
            Rich Group containing background and logo
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.text import Text
        except ImportError:
            return Group(*logo_lines)

        # Get terminal size
        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        # Ensure background is never "none" - always provide a default background
        if bg_config.bg_type == "none":
            bg_config.bg_type = "solid"
            if not bg_config.bg_color_start and not bg_config.bg_color_palette:
                bg_config.bg_color_palette = ["black", "dim white"]

        # Generate background
        bg_color = bg_config.bg_color_start or bg_config.bg_color_palette
        # Ensure bg_color is set - provide default if missing
        if not bg_color:
            bg_color = ["black", "dim white"]
            bg_config.bg_color_palette = bg_color
        bg_lines = self.background_renderer.generate_background(
            width=width,
            height=height,
            bg_type=bg_config.bg_type,
            bg_color=bg_color,
            bg_pattern_char=bg_config.bg_pattern_char,
            bg_pattern_density=bg_config.bg_pattern_density,
            bg_star_count=bg_config.bg_star_count,
            bg_wave_char=bg_config.bg_wave_char,
            bg_wave_lines=bg_config.bg_wave_lines,
            bg_flower_petals=bg_config.bg_flower_petals,
            bg_flower_radius=bg_config.bg_flower_radius,
            bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
            bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
            bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
            bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
            time_offset=time_offset,
        )

        # Combine background with logo
        combined_lines = []
        logo_height = len(logo_lines)
        logo_start_y = (height - logo_height) // 2

        for y, bg_line in enumerate(bg_lines):
            if logo_start_y <= y < logo_start_y + logo_height:
                # This row contains logo - combine background and logo
                logo_idx = y - logo_start_y
                logo_line = logo_lines[logo_idx]
                
                # Create combined line with background color
                combined_line = Text()
                
                # Add background with animated color
                if bg_config.bg_type in ["solid", "gradient"] and bg_color:
                    # Use animated background color helper with separate animation speed
                    bg_anim_speed = getattr(bg_config, 'bg_animation_speed', 1.0)
                    bg_color_str = self._get_background_color(
                        bg_color, (0, y), time_offset, bg_anim_speed, "dim white"
                    )
                    combined_line = Text(bg_line, style=bg_color_str)
                else:
                    combined_line = Text(bg_line, style="dim white")
                
                # Overlay logo on background (logo takes precedence)
                # Logo line already has its colors, just append it
                combined_lines.append(logo_line)
            else:
                # Pure background line with animated color
                if bg_config.bg_type in ["solid", "gradient"] and bg_color:
                    bg_anim_speed = getattr(bg_config, 'bg_animation_speed', 1.0)
                    bg_color_str = self._get_background_color(
                        bg_color, (0, y), time_offset, bg_anim_speed, "dim white"
                    )
                    combined_lines.append(Text(bg_line, style=bg_color_str))
                else:
                    combined_lines.append(Text(bg_line, style="dim white"))

        return Group(*combined_lines)

    def get_columns(self, lines: list[str]) -> list[list[str]]:
        """Extract columns from lines.
        
        Args:
            lines: List of text lines
            
        Returns:
            List of columns, where each column is a list of characters
        """
        if not lines:
            return []
        
        max_width = max(len(line) for line in lines)
        columns = []
        
        for col_idx in range(max_width):
            column = []
            for line in lines:
                if col_idx < len(line):
                    column.append(line[col_idx])
                else:
                    column.append(" ")
            columns.append(column)
        
        return columns

    def reconstruct_from_columns(self, columns: list[list[str]]) -> list[str]:
        """Reconstruct lines from columns.
        
        Args:
            columns: List of columns (each column is a list of characters)
            
        Returns:
            List of text lines
        """
        if not columns:
            return []
        
        height = len(columns[0]) if columns else 0
        lines = []
        
        for row_idx in range(height):
            line = ""
            for column in columns:
                if row_idx < len(column):
                    line += column[row_idx]
                else:
                    line += " "
            lines.append(line)
        
        return lines

    async def animate_columns_reveal(
        self,
        text: str,
        direction: str = "left_to_right",
        color: str = "white",
        steps: int = 30,
        column_groups: int = 1,
        duration: float | None = None,
    ) -> None:
        """Reveal text column by column or in column groups.
        
        Args:
            text: Text to reveal
            direction: Reveal direction ('left_to_right', 'right_to_left', 'center_out', 'center_in')
            color: Color style
            steps: Number of reveal steps
            column_groups: Number of columns to reveal at once
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        columns = self.get_columns(lines)
        num_columns = len(columns)
        
        # Calculate frame duration for smooth animation
        if duration is None:
            # Estimate duration based on steps and default frame rate
            estimated_duration = (steps + 1) * self.default_duration
        else:
            estimated_duration = duration
        frame_duration = self._calculate_frame_duration(estimated_duration, steps + 1)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                progress = step / steps
                revealed_columns = set()

                if direction == "left_to_right":
                    reveal_count = int(num_columns * progress)
                    revealed_columns = set(range(reveal_count))
                elif direction == "right_to_left":
                    reveal_count = int(num_columns * progress)
                    start_idx = num_columns - reveal_count
                    revealed_columns = set(range(start_idx, num_columns))
                elif direction == "center_out":
                    center = num_columns // 2
                    reveal_radius = int((num_columns / 2) * progress)
                    for i in range(num_columns):
                        if abs(i - center) <= reveal_radius:
                            revealed_columns.add(i)
                elif direction == "center_in":
                    center = num_columns // 2
                    reveal_radius = int((num_columns / 2) * (1 - progress))
                    for i in range(num_columns):
                        if abs(i - center) >= reveal_radius:
                            revealed_columns.add(i)

                # Build display columns
                display_columns = []
                for col_idx, column in enumerate(columns):
                    if col_idx in revealed_columns:
                        display_columns.append(column)
                    else:
                        display_columns.append([" "] * len(column))

                # Reconstruct lines
                display_lines = self.reconstruct_from_columns(display_columns)

                # Build Rich Text objects
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def animate_columns_color(
        self,
        text: str,
        direction: str = "left_to_right",
        color_palette: list[str] | None = None,
        speed: float = 8.0,
        duration: float = 3.0,
        column_groups: int = 1,
    ) -> None:
        """Animate colors on columns or column groups.
        
        Args:
            text: Text to animate
            direction: Color flow direction
            color_palette: List of color styles
            speed: Speed of color movement
            duration: Animation duration
            column_groups: Number of columns per group
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color="white")
            return

        if color_palette is None:
            color_palette = [
                "red", "orange_red1", "dark_orange", "orange1", "yellow",
                "chartreuse1", "green", "spring_green1", "cyan",
                "deep_sky_blue1", "blue", "blue_violet", "purple", "magenta", "hot_pink",
            ]

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        columns = self.get_columns(lines)
        num_columns = len(columns)
        num_groups = (num_columns + column_groups - 1) // column_groups
        num_colors = len(color_palette)

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                time_offset = int(elapsed * speed) % num_colors

                # Build display columns with colors
                display_columns = []
                for col_idx, column in enumerate(columns):
                    group_idx = col_idx // column_groups
                    
                    if direction == "left_to_right":
                        color_index = (group_idx + time_offset) % num_colors
                    elif direction == "right_to_left":
                        color_index = (group_idx - time_offset) % num_colors
                    elif direction == "center_out":
                        center = num_groups // 2
                        distance = abs(group_idx - center)
                        color_index = (distance + time_offset) % num_colors
                    elif direction == "center_in":
                        center = num_groups // 2
                        distance = abs(group_idx - center)
                        color_index = (num_groups - distance + time_offset) % num_colors
                    else:
                        color_index = 0

                    style = color_palette[color_index]
                    display_columns.append((column, style))

                # Reconstruct lines with colors
                height = len(columns[0]) if columns else 0
                logo_lines = []
                for row_idx in range(height):
                    text_line = Text()
                    for column, style in display_columns:
                        if row_idx < len(column):
                            char = column[row_idx]
                            if char == " ":
                                text_line.append(char)
                            else:
                                text_line.append(char, style=style)
                        else:
                            text_line.append(" ")
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def animate_columns_wave(
        self,
        text: str,
        color: str = "white",
        wave_speed: float = 2.0,
        wave_amplitude: float = 2.0,
        duration: float = 3.0,
    ) -> None:
        """Create wave effect on columns.
        
        Args:
            text: Text to animate
            color: Base color
            wave_speed: Speed of wave
            wave_amplitude: Amplitude of wave (in characters)
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        columns = self.get_columns(lines)
        num_columns = len(columns)
        height = len(columns[0]) if columns else 0

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time

                # Build display with wave effect
                logo_lines = []
                for row_idx in range(height):
                    text_line = Text()
                    for col_idx, column in enumerate(columns):
                        if row_idx < len(column):
                            char = column[row_idx]
                            
                            # Calculate wave offset for this column
                            wave_offset = int(
                                wave_amplitude * 
                                (col_idx / num_columns) * 
                                (1 + (elapsed * wave_speed) % 2 - 1)
                            )
                            
                            # Apply wave effect (shift characters vertically)
                            effective_row = (row_idx + wave_offset) % height
                            if effective_row < len(column):
                                display_char = column[effective_row]
                            else:
                                display_char = " "
                            
                            if display_char == " ":
                                text_line.append(display_char)
                            else:
                                text_line.append(display_char, style=color)
                        else:
                            text_line.append(" ")
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def animate_columns_scroll(
        self,
        text: str,
        direction: str = "up",
        color: str = "white",
        speed: float = 1.0,
        duration: float = 3.0,
    ) -> None:
        """Scroll columns vertically.
        
        Args:
            text: Text to animate
            direction: Scroll direction ('up', 'down')
            color: Color style
            speed: Scroll speed
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        columns = self.get_columns(lines)
        height = len(columns[0]) if columns else 0

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                scroll_offset = int(elapsed * speed * 10) % height

                # Build display with scroll effect
                logo_lines = []
                for row_idx in range(height):
                    text_line = Text()
                    for column in columns:
                        if direction == "up":
                            effective_idx = (row_idx + scroll_offset) % height
                        else:  # down
                            effective_idx = (row_idx - scroll_offset) % height
                        
                        if effective_idx < len(column):
                            char = column[effective_idx]
                        else:
                            char = " "
                        
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    def group_characters_by_spaces(self, line: str) -> list[tuple[int, int, str]]:
        """Group characters in a line by spaces (word boundaries).
        
        Args:
            line: Text line
            
        Returns:
            List of (start_idx, end_idx, group_text) tuples
        """
        groups = []
        start_idx = 0
        in_group = False
        
        for i, char in enumerate(line):
            if char != " " and not in_group:
                # Start of a new group
                start_idx = i
                in_group = True
            elif char == " " and in_group:
                # End of current group
                groups.append((start_idx, i, line[start_idx:i]))
                in_group = False
        
        # Handle group at end of line
        if in_group:
            groups.append((start_idx, len(line), line[start_idx:]))
        
        return groups

    def group_characters_custom(
        self,
        line: str,
        group_size: int = 1,
        separator: str = " ",
    ) -> list[tuple[int, int, str]]:
        """Group characters in a line with custom grouping.
        
        Args:
            line: Text line
            group_size: Number of characters per group (0 = group by separator)
            separator: Character to use as separator when group_size is 0
            
        Returns:
            List of (start_idx, end_idx, group_text) tuples
        """
        groups = []
        
        if group_size > 0:
            # Fixed-size groups
            for i in range(0, len(line), group_size):
                end_idx = min(i + group_size, len(line))
                groups.append((i, end_idx, line[i:end_idx]))
        else:
            # Group by separator
            start_idx = 0
            for i, char in enumerate(line):
                if char == separator:
                    if i > start_idx:
                        groups.append((start_idx, i, line[start_idx:i]))
                    start_idx = i + 1
            # Add remaining
            if start_idx < len(line):
                groups.append((start_idx, len(line), line[start_idx:]))
        
        return groups

    async def animate_row_groups_reveal(
        self,
        text: str,
        direction: str = "left_to_right",
        color: str = "white",
        steps: int = 30,
        group_by: str = "spaces",  # "spaces", "custom"
        group_size: int = 1,
    ) -> None:
        """Reveal text by animating groups of characters in rows.
        
        Args:
            text: Text to reveal
            direction: Reveal direction ('left_to_right', 'right_to_left', 'center_out', 'center_in')
            color: Color style
            steps: Number of reveal steps
            group_by: How to group characters ('spaces' for word boundaries, 'custom' for fixed size)
            group_size: Characters per group when group_by is 'custom'
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Group characters in each line
        line_groups = []
        for line in lines:
            if group_by == "spaces":
                groups = self.group_characters_by_spaces(line)
            else:
                groups = self.group_characters_custom(line, group_size=group_size)
            line_groups.append(groups)

        max_groups = max(len(groups) for groups in line_groups) if line_groups else 0

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                progress = step / steps
                display_lines = []

                for line_idx, groups in enumerate(line_groups):
                    if not groups:
                        # Empty line - preserve it
                        original_line = lines[line_idx]
                        display_lines.append(original_line)
                        continue

                    num_groups = len(groups)
                    revealed_groups = set()

                    if direction == "left_to_right":
                        reveal_count = int(num_groups * progress)
                        revealed_groups = set(range(reveal_count))
                    elif direction == "right_to_left":
                        reveal_count = int(num_groups * progress)
                        start_idx = num_groups - reveal_count
                        revealed_groups = set(range(start_idx, num_groups))
                    elif direction == "center_out":
                        center = num_groups // 2
                        reveal_radius = int((num_groups / 2) * progress)
                        for i in range(num_groups):
                            if abs(i - center) <= reveal_radius:
                                revealed_groups.add(i)
                    elif direction == "center_in":
                        center = num_groups // 2
                        reveal_radius = int((num_groups / 2) * (1 - progress))
                        for i in range(num_groups):
                            if abs(i - center) >= reveal_radius:
                                revealed_groups.add(i)

                    # Build display line preserving all spaces
                    original_line = lines[line_idx]
                    display_line = ""
                    current_pos = 0
                    
                    for group_idx, (start_idx, end_idx, group_text) in enumerate(groups):
                        # Add any spaces before this group
                        while current_pos < start_idx and current_pos < len(original_line):
                            display_line += original_line[current_pos]
                            current_pos += 1
                        
                        # Add group (revealed or hidden)
                        if group_idx in revealed_groups:
                            display_line += group_text
                        else:
                            display_line += " " * len(group_text)
                        
                        current_pos = end_idx
                    
                    # Add any remaining characters (spaces at end)
                    while current_pos < len(original_line):
                        display_line += original_line[current_pos]
                        current_pos += 1
                    
                    display_lines.append(display_line)

                # Build Rich Text objects
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    async def animate_row_groups_color(
        self,
        text: str,
        direction: str = "left_to_right",
        color_palette: list[str] | None = None,
        speed: float = 8.0,
        duration: float = 3.0,
        group_by: str = "spaces",
        group_size: int = 1,
    ) -> None:
        """Animate colors on groups of characters in rows.
        
        Args:
            text: Text to animate
            direction: Color flow direction
            color_palette: List of color styles
            speed: Speed of color movement
            duration: Animation duration
            group_by: How to group characters
            group_size: Characters per group when group_by is 'custom'
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color="white")
            return

        if color_palette is None:
            color_palette = [
                "red", "orange_red1", "dark_orange", "orange1", "yellow",
                "chartreuse1", "green", "spring_green1", "cyan",
                "deep_sky_blue1", "blue", "blue_violet", "purple", "magenta", "hot_pink",
            ]

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Group characters in each line
        line_groups = []
        for line in lines:
            if group_by == "spaces":
                groups = self.group_characters_by_spaces(line)
            else:
                groups = self.group_characters_custom(line, group_size=group_size)
            line_groups.append(groups)

        num_colors = len(color_palette)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        
        # Calculate adaptive frame duration based on total duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                # Adapt speed based on duration to ensure smooth animation
                adapted_speed = self._adapt_speed_to_duration(speed, duration)
                time_offset = int(elapsed * adapted_speed) % num_colors

                logo_lines = []
                for line_idx, groups in enumerate(line_groups):
                    text_line = Text()
                    
                    if not groups:
                        # Empty line - preserve it
                        original_line = lines[line_idx]
                        for char in original_line:
                            text_line.append(char)
                        logo_lines.append(text_line)
                        continue

                    # Reconstruct the full line preserving all spaces
                    original_line = lines[line_idx]
                    num_groups = len(groups)
                    current_pos = 0
                    
                    for group_idx, (start_idx, end_idx, group_text) in enumerate(groups):
                        # Add any spaces before this group
                        while current_pos < start_idx and current_pos < len(original_line):
                            text_line.append(original_line[current_pos])
                            current_pos += 1
                        
                        # Calculate color for this group
                        if direction == "left_to_right":
                            color_index = (group_idx + time_offset) % num_colors
                        elif direction == "right_to_left":
                            color_index = (group_idx - time_offset) % num_colors
                        elif direction == "center_out":
                            center = num_groups // 2
                            distance = abs(group_idx - center)
                            color_index = (distance + time_offset) % num_colors
                        elif direction == "center_in":
                            center = num_groups // 2
                            distance = abs(group_idx - center)
                            color_index = (num_groups - distance + time_offset) % num_colors
                        else:
                            color_index = 0

                        style = color_palette[color_index]
                        
                        # Add group characters with color
                        for char in group_text:
                            if char == " ":
                                text_line.append(char)
                            else:
                                text_line.append(char, style=style)
                        
                        current_pos = end_idx
                    
                    # Add any remaining characters (spaces at end)
                    while current_pos < len(original_line):
                        text_line.append(original_line[current_pos])
                        current_pos += 1
                    
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def animate_row_groups_wave(
        self,
        text: str,
        color: str = "white",
        wave_speed: float = 2.0,
        wave_amplitude: float = 1.0,
        duration: float = 3.0,
        group_by: str = "spaces",
        group_size: int = 1,
    ) -> None:
        """Create wave effect on groups of characters in rows.
        
        Args:
            text: Text to animate
            color: Base color
            wave_speed: Speed of wave
            wave_amplitude: Amplitude of wave (in groups)
            duration: Animation duration
            group_by: How to group characters
            group_size: Characters per group when group_by is 'custom'
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Group characters in each line
        line_groups = []
        for line in lines:
            if group_by == "spaces":
                groups = self.group_characters_by_spaces(line)
            else:
                groups = self.group_characters_custom(line, group_size=group_size)
            line_groups.append(groups)

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time

                logo_lines = []
                for line_idx, groups in enumerate(line_groups):
                    text_line = Text()
                    
                    if not groups:
                        # Empty line - preserve it
                        original_line = lines[line_idx]
                        for char in original_line:
                            text_line.append(char)
                        logo_lines.append(text_line)
                        continue

                    # Reconstruct the full line preserving all spaces
                    original_line = lines[line_idx]
                    num_groups = len(groups)
                    current_pos = 0
                    
                    for group_idx, (start_idx, end_idx, group_text) in enumerate(groups):
                        # Add any spaces before this group
                        while current_pos < start_idx and current_pos < len(original_line):
                            text_line.append(original_line[current_pos])
                            current_pos += 1
                        
                        # Calculate wave offset for this group
                        wave_offset = int(
                            wave_amplitude * 
                            (group_idx / num_groups) * 
                            (1 + (elapsed * wave_speed) % 2 - 1)
                        )
                        
                        # Apply wave effect (shift groups horizontally)
                        effective_group_idx = (group_idx + wave_offset) % num_groups
                        if 0 <= effective_group_idx < len(groups):
                            display_group = groups[effective_group_idx][2]
                        else:
                            display_group = " " * len(group_text)
                        
                        # Add group characters
                        for char in display_group:
                            if char == " ":
                                text_line.append(char)
                            else:
                                text_line.append(char, style=color)
                        
                        current_pos = end_idx
                    
                    # Add any remaining characters (spaces at end)
                    while current_pos < len(original_line):
                        text_line.append(original_line[current_pos])
                        current_pos += 1
                    
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def animate_row_groups_fade(
        self,
        text: str,
        direction: str = "left_to_right",
        color: str = "white",
        steps: int = 30,
        group_by: str = "spaces",
        group_size: int = 1,
    ) -> None:
        """Fade in/out groups of characters in rows.
        
        Args:
            text: Text to animate
            direction: Fade direction ('left_to_right', 'right_to_left', 'center_out', 'center_in')
            color: Base color
            steps: Number of fade steps
            group_by: How to group characters
            group_size: Characters per group when group_by is 'custom'
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Group characters in each line
        line_groups = []
        for line in lines:
            if group_by == "spaces":
                groups = self.group_characters_by_spaces(line)
            else:
                groups = self.group_characters_custom(line, group_size=group_size)
            line_groups.append(groups)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                progress = step / steps
                logo_lines = []

                for line_idx, groups in enumerate(line_groups):
                    text_line = Text()
                    
                    if not groups:
                        # Empty line - preserve it
                        original_line = lines[line_idx]
                        for char in original_line:
                            text_line.append(char)
                        logo_lines.append(text_line)
                        continue

                    # Reconstruct the full line preserving all spaces
                    original_line = lines[line_idx]
                    num_groups = len(groups)
                    current_pos = 0
                    
                    for group_idx, (start_idx, end_idx, group_text) in enumerate(groups):
                        # Add any spaces before this group
                        while current_pos < start_idx and current_pos < len(original_line):
                            text_line.append(original_line[current_pos])
                            current_pos += 1
                        
                        # Calculate fade alpha for this group
                        if direction == "left_to_right":
                            group_progress = (group_idx + 1) / num_groups
                            alpha = max(0, min(1, (progress - (group_progress - 1/num_groups)) * num_groups))
                        elif direction == "right_to_left":
                            group_progress = (num_groups - group_idx) / num_groups
                            alpha = max(0, min(1, (progress - (group_progress - 1/num_groups)) * num_groups))
                        elif direction == "center_out":
                            center = num_groups // 2
                            distance = abs(group_idx - center)
                            max_distance = num_groups // 2
                            group_progress = distance / max_distance if max_distance > 0 else 0
                            alpha = max(0, min(1, progress - group_progress + 0.5))
                        elif direction == "center_in":
                            center = num_groups // 2
                            distance = abs(group_idx - center)
                            max_distance = num_groups // 2
                            group_progress = 1 - (distance / max_distance if max_distance > 0 else 0)
                            alpha = max(0, min(1, progress - (1 - group_progress) + 0.5))
                        else:
                            alpha = progress

                        # Determine style based on alpha
                        if alpha < 0.3:
                            style = f"dim {color}"
                        elif alpha < 0.7:
                            style = color
                        else:
                            style = f"bold {color}"

                        # Add group characters with fade style
                        for char in group_text:
                            if char == " ":
                                text_line.append(char)
                            else:
                                text_line.append(char, style=style)
                        
                        current_pos = end_idx
                    
                    # Add any remaining characters (spaces at end)
                    while current_pos < len(original_line):
                        text_line.append(original_line[current_pos])
                        current_pos += 1
                    
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    async def animate_row_transition(
        self,
        text: str,
        direction: str = "left_to_right_top_bottom",
        color: str = "white",
        duration: float = 3.0,
    ) -> None:
        """Animate row transition from left/right top to bottom.
        
        Args:
            text: Text to animate
            direction: Transition direction ('left_to_right_top_bottom', 'right_to_left_top_bottom')
            color: Color style
            duration: Animation duration in seconds
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        height = len(lines)
        max_width = max(len(line) for line in lines)
        
        # Calculate frame duration
        frame_duration = self._calculate_frame_duration(duration)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                progress = min(1.0, elapsed / duration)
                
                logo_lines = []
                
                for row_idx, line in enumerate(lines):
                    # Calculate row progress (0.0 at top, 1.0 at bottom)
                    row_progress = row_idx / height if height > 0 else 0
                    
                    # Calculate when this row should start appearing
                    # Rows appear sequentially from top to bottom
                    row_start_time = row_progress * duration
                    row_end_time = row_start_time + (duration / height) if height > 0 else duration
                    
                    # Calculate row-specific progress
                    if elapsed < row_start_time:
                        # Row hasn't started yet
                        row_alpha = 0.0
                    elif elapsed >= row_end_time:
                        # Row is fully visible
                        row_alpha = 1.0
                    else:
                        # Row is transitioning
                        row_elapsed = elapsed - row_start_time
                        row_duration = row_end_time - row_start_time
                        row_alpha = row_elapsed / row_duration if row_duration > 0 else 1.0
                    
                    text_line = Text()
                    
                    if direction == "left_to_right_top_bottom":
                        # Reveal from left to right, rows from top to bottom
                        reveal_width = int(len(line) * row_alpha)
                        for char_idx, char in enumerate(line):
                            if char_idx < reveal_width:
                                if char == " ":
                                    text_line.append(char)
                                else:
                                    text_line.append(char, style=color)
                            else:
                                text_line.append(" ")
                    
                    elif direction == "right_to_left_top_bottom":
                        # Reveal from right to left, rows from top to bottom
                        reveal_width = int(len(line) * row_alpha)
                        start_idx = len(line) - reveal_width
                        for char_idx, char in enumerate(line):
                            if char_idx >= start_idx:
                                if char == " ":
                                    text_line.append(char)
                                else:
                                    text_line.append(char, style=color)
                            else:
                                text_line.append(" ")
                    else:
                        # Default: left to right
                        reveal_width = int(len(line) * row_alpha)
                        for char_idx, char in enumerate(line):
                            if char_idx < reveal_width:
                                if char == " ":
                                    text_line.append(char)
                                else:
                                    text_line.append(char, style=color)
                            else:
                                text_line.append(" ")
                    
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def play_frames(
        self,
        frames: list[str],
        frame_duration: float | None = None,
        color: str = "white",
        clear_between: bool = True,
    ) -> None:
        """Play a sequence of frames.
        
        Args:
            frames: List of ASCII art frames
            frame_duration: Duration per frame (uses default if None)
            color: Color style to apply
            clear_between: Whether to clear between frames

        """
        duration = frame_duration or self.default_duration

        for i, frame in enumerate(frames):
            self.renderer.render_frame(
                frame,
                color=color,
                clear=clear_between and i > 0,
            )
            await asyncio.sleep(duration)

    async def play_multi_color_frames(
        self,
        frames: list[list[tuple[str, str]]],
        frame_duration: float | None = None,
        clear_between: bool = True,
    ) -> None:
        """Play a sequence of multi-color frames.
        
        Args:
            frames: List of frame data (list of (text, color) tuples)
            frame_duration: Duration per frame (uses default if None)
            clear_between: Whether to clear between frames

        """
        duration = frame_duration or self.default_duration

        for i, frame_data in enumerate(frames):
            self.renderer.render_multi_color_frame(
                frame_data,
                clear=clear_between and i > 0,
            )
            await asyncio.sleep(duration)

    async def fade_in(
        self,
        text: str,
        steps: int = 10,
        color: str = "white",
    ) -> None:
        """Fade in text animation.
        
        Args:
            text: Text to fade in
            steps: Number of fade steps
            color: Base color style

        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            # Fallback to simple rendering
            for i in range(steps):
                alpha = i / steps
                if alpha < 0.3:
                    style = f"dim {color}"
                elif alpha < 0.7:
                    style = color
                else:
                    style = f"bold {color}"
                self.renderer.render_frame(text, color=style, clear=True)
                await asyncio.sleep(self.default_duration)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for i in range(steps):
                alpha = i / steps
                # Simple fade effect using brightness
                if alpha < 0.3:
                    style = f"dim {color}"
                elif alpha < 0.7:
                    style = color
                else:
                    style = f"bold {color}"

                # Build Rich Text objects character by character (like rainbow animation)
                # This preserves spaces exactly for proper alignment
                logo_lines = []
                for line in lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    async def fade_out(
        self,
        text: str,
        steps: int = 10,
        color: str = "white",
    ) -> None:
        """Fade out text animation.
        
        Args:
            text: Text to fade out
            steps: Number of fade steps
            color: Base color style

        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            # Fallback to simple rendering
            for i in range(steps, 0, -1):
                alpha = i / steps
                if alpha < 0.3:
                    style = f"dim {color}"
                elif alpha < 0.7:
                    style = color
                else:
                    style = f"bold {color}"
                self.renderer.render_frame(text, color=style, clear=True)
                await asyncio.sleep(self.default_duration)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for i in range(steps, 0, -1):
                alpha = i / steps
                if alpha < 0.3:
                    style = f"dim {color}"
                elif alpha < 0.7:
                    style = color
                else:
                    style = f"bold {color}"

                # Build Rich Text objects character by character (like rainbow animation)
                # This preserves spaces exactly for proper alignment
                logo_lines = []
                for line in lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    async def slide_in(
        self,
        text: str,
        direction: str = "left",
        steps: int = 20,
        color: str = "white",
    ) -> None:
        """Slide in text animation.
        
        Args:
            text: Text to slide in
            direction: Direction ('left', 'right', 'top', 'bottom')
            steps: Number of animation steps
            color: Color style

        """
        lines = text.split("\n")
        max_width = max(len(line) for line in lines if line.strip())
        height = len(lines)

        for step in range(steps):
            offset = int((step / steps) * max_width)

            if direction == "left":
                # Slide from right
                display_lines = []
                for line in lines:
                    if len(line) < max_width:
                        padding = " " * (max_width - len(line))
                        line = line + padding
                    display_lines.append(line[-max_width + offset:] + " " * offset)
                frame = "\n".join(display_lines)
            elif direction == "right":
                # Slide from left
                display_lines = []
                for line in lines:
                    if len(line) < max_width:
                        padding = " " * (max_width - len(line))
                        line = padding + line
                    display_lines.append(" " * (max_width - offset) + line[:offset])
                frame = "\n".join(display_lines)
            else:
                # For top/bottom, just show full text
                frame = text

            self.renderer.render_frame(frame, color=color, clear=True)
            await asyncio.sleep(0.03)

    async def animate_color_per_direction(
        self,
        text: str,
        direction: str = "left",
        color_palette: list[str] | None = None,
        speed: float = 8.0,
        duration: float = 3.0,
    ) -> None:
        """Animate colors moving in a specific direction.
        
        Args:
            text: Text to animate
            direction: Direction of color flow ('left', 'right', 'top', 'bottom', 'radiant')
            color_palette: List of color styles (uses default rainbow if None)
            speed: Speed of color movement
            duration: Animation duration in seconds
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            # Fallback to simple rendering
            self.renderer.render_frame(text, color="white")
            return

        if color_palette is None:
            color_palette = [
                "red", "orange_red1", "dark_orange", "orange1", "yellow",
                "chartreuse1", "green", "spring_green1", "cyan",
                "deep_sky_blue1", "blue", "blue_violet", "purple", "magenta", "hot_pink",
            ]

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        num_colors = len(color_palette)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        
        # Calculate adaptive frame duration based on total duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                # Adapt speed based on duration to ensure smooth animation
                adapted_speed = self._adapt_speed_to_duration(speed, duration)
                time_offset = int(elapsed * adapted_speed) % num_colors

                logo_lines = []
                for line_idx, line in enumerate(lines):
                    text_line = Text()
                    for char_idx, char in enumerate(line):
                        if char == " ":
                            text_line.append(char)
                        else:
                            if direction == "left" or direction == "right_to_left":
                                # Colors move from right to left
                                color_index = (char_idx + time_offset) % num_colors
                            elif direction == "right" or direction == "left_to_right":
                                # Colors move from left to right
                                color_index = (char_idx - time_offset) % num_colors
                            elif direction == "top" or direction == "bottom_to_top":
                                # Colors move from bottom to top
                                color_index = (line_idx + time_offset) % num_colors
                            elif direction == "bottom" or direction == "top_to_bottom":
                                # Colors move from top to bottom
                                color_index = (line_idx - time_offset) % num_colors
                            elif direction == "radiant" or direction == "radiant_center_out":
                                # Colors radiate from center outward
                                center_x = max_width // 2
                                center_y = len(lines) // 2
                                dist_x = abs(char_idx - center_x)
                                dist_y = abs(line_idx - center_y)
                                distance = int((dist_x + dist_y) / 2)
                                color_index = (distance + time_offset) % num_colors
                            elif direction == "radiant_center_in":
                                # Colors radiate from outside inward
                                center_x = max_width // 2
                                center_y = len(lines) // 2
                                dist_x = abs(char_idx - center_x)
                                dist_y = abs(line_idx - center_y)
                                max_dist = int(((max_width / 2) ** 2 + (len(lines) / 2) ** 2) ** 0.5)
                                distance = int((dist_x + dist_y) / 2)
                                color_index = (max_dist - distance + time_offset) % num_colors
                            else:
                                color_index = 0

                            style = color_palette[color_index]
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def reveal_animation(
        self,
        text: str,
        direction: str = "top_down",
        color: str = "white",
        steps: int = 30,
        reveal_char: str = "█",
        duration: float | None = None,
    ) -> None:
        """Reveal text animation from different directions.
        
        Args:
            text: Text to reveal
            direction: Reveal direction ('top_down', 'down_up', 'left_right', 'right_left', 'radiant')
            color: Color style
            steps: Number of reveal steps
            reveal_char: Character to use for unrevealed parts
            duration: Optional duration in seconds (if provided, steps will be calculated)
        """
        # If duration is provided, calculate steps based on duration
        if duration is not None and duration > 0:
            # Target 60 FPS for fast, complete reveal animations
            steps = max(30, int(duration * 60))
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            # Fallback to simple rendering
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        height = len(lines)
        
        # Calculate frame duration if duration is provided
        if duration is not None and duration > 0:
            frame_duration = duration / steps
        else:
            frame_duration = 0.05  # Default 20 FPS

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                # Ensure progress reaches exactly 1.0 on final step
                progress = 1.0 if step == steps else step / steps
                display_lines = []

                if direction == "top_down":
                    reveal_height = height if step == steps else int(height * progress)
                    for i, line in enumerate(lines):
                        if i < reveal_height:
                            display_lines.append(line)
                        else:
                            display_lines.append(reveal_char * len(line) if line else "")

                elif direction == "down_up":
                    reveal_height = height if step == steps else int(height * progress)
                    start_idx = height - reveal_height
                    for i, line in enumerate(lines):
                        if i >= start_idx:
                            display_lines.append(line)
                        else:
                            display_lines.append(reveal_char * len(line) if line else "")

                elif direction == "left_right":
                    reveal_width = max_width if step == steps else int(max_width * progress)
                    for line in lines:
                        if len(line) <= reveal_width:
                            display_lines.append(line)
                        else:
                            display_lines.append(line[:reveal_width] + reveal_char * (len(line) - reveal_width))

                elif direction == "right_left":
                    reveal_width = max_width if step == steps else int(max_width * progress)
                    for line in lines:
                        if len(line) <= reveal_width:
                            display_lines.append(line)
                        else:
                            padding = max_width - len(line)
                            display_lines.append(reveal_char * (len(line) - reveal_width + padding) + line[-reveal_width:])

                elif direction == "radiant":
                    center_x = max_width // 2
                    center_y = height // 2
                    max_dist = int(((max_width / 2) ** 2 + (height / 2) ** 2) ** 0.5)
                    reveal_dist = max_dist * 2 if step == steps else max_dist * progress

                    for i, line in enumerate(lines):
                        display_line = ""
                        for j, char in enumerate(line):
                            dist_x = abs(j - center_x)
                            dist_y = abs(i - center_y)
                            distance = (dist_x ** 2 + dist_y ** 2) ** 0.5
                            if distance <= reveal_dist:
                                display_line += char
                            else:
                                display_line += reveal_char
                        display_lines.append(display_line)

                # Build Rich Text objects character by character (like rainbow animation)
                # This preserves spaces exactly for proper alignment
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)
            
            # Ensure final frame always shows complete logo (progress = 1.0)
            final_lines = []
            for line in lines:
                final_lines.append(line)
            
            logo_lines = []
            for line in final_lines:
                text_line = Text()
                for char in line:
                    if char == " ":
                        text_line.append(char)
                    else:
                        text_line.append(char, style=color)
                logo_lines.append(text_line)
            
            centered = Align.center(Group(*logo_lines))
            live.update(centered)
            await asyncio.sleep(frame_duration)

    async def letter_by_letter_animation(
        self,
        text: str,
        direction: str = "top_down",
        color: str = "white",
        delay_per_letter: float = 0.02,
        group_letters: bool = False,
    ) -> None:
        """Animate text appearing letter by letter.
        
        Args:
            text: Text to animate
            direction: Animation direction ('top_down', 'down_up', 'left_right', 'right_left')
            color: Color style
            delay_per_letter: Delay between letters
            group_letters: If True, group by word/line instead of individual letters
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            # Fallback to simple rendering
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        if direction == "top_down":
            order = [(i, j) for i in range(len(lines)) for j in range(len(lines[i]))]
        elif direction == "down_up":
            order = [(i, j) for i in range(len(lines) - 1, -1, -1) for j in range(len(lines[i]))]
        elif direction == "left_right":
            max_width = max(len(line) for line in lines)
            order = [(i, j) for j in range(max_width) for i in range(len(lines)) if j < len(lines[i])]
        elif direction == "right_left":
            max_width = max(len(line) for line in lines)
            order = [(i, j) for j in range(max_width - 1, -1, -1) for i in range(len(lines)) if j < len(lines[i])]
        else:
            order = [(i, j) for i in range(len(lines)) for j in range(len(lines[i]))]

        revealed = set()
        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for pos in order:
                revealed.add(pos)
                display_lines = []
                for i, line in enumerate(lines):
                    display_line = ""
                    for j, char in enumerate(line):
                        if (i, j) in revealed:
                            display_line += char
                        else:
                            display_line += " "
                    display_lines.append(display_line)

                # Build Rich Text objects character by character (like rainbow animation)
                # This preserves spaces exactly for proper alignment
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(delay_per_letter)

    async def flag_effect(
        self,
        text: str,
        color_palette: list[str] | None = None,
        wave_speed: float = 2.0,
        wave_amplitude: float = 2.0,
        duration: float = 3.0,
    ) -> None:
        """Create a flag/wave effect on text.
        
        Args:
            text: Text to animate
            color_palette: Color palette (uses default if None)
            wave_speed: Speed of wave motion
            wave_amplitude: Amplitude of wave (in characters)
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color="white")
            return

        if color_palette is None:
            color_palette = ["blue", "white", "red"]

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                logo_lines = []

                for line_idx, line in enumerate(lines):
                    text_line = Text()
                    for char_idx, char in enumerate(line):
                        if char == " ":
                            text_line.append(char)
                        else:
                            # Calculate wave offset
                            wave_offset = int(wave_amplitude * (line_idx / len(lines)) * 
                                            (1 + (elapsed * wave_speed) % 2 - 1))
                            # Alternate colors for flag effect
                            color_idx = (char_idx + wave_offset) % len(color_palette)
                            style = color_palette[color_idx]
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def particle_effect(
        self,
        text: str,
        base_color: str = "white",
        particle_chars: str = "·*+×",
        density: float = 0.1,
        speed: float = 1.0,
        duration: float = 3.0,
    ) -> None:
        """Add particle effects around text.
        
        Args:
            text: Base text
            base_color: Base text color
            particle_chars: Characters to use for particles
            density: Particle density (0.0-1.0)
            speed: Particle movement speed
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=base_color)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        height = len(lines)

        # Generate particle positions
        particles = []
        num_particles = int(max_width * height * density)
        for _ in range(num_particles):
            particles.append({
                'x': random.uniform(0, max_width),
                'y': random.uniform(0, height),
                'char': random.choice(particle_chars),
                'vx': random.uniform(-speed, speed),
                'vy': random.uniform(-speed, speed),
            })

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time

                # Update particles
                for p in particles:
                    p['x'] += p['vx'] * 0.1
                    p['y'] += p['vy'] * 0.1
                    # Wrap around
                    if p['x'] < 0:
                        p['x'] = max_width
                    if p['x'] > max_width:
                        p['x'] = 0
                    if p['y'] < 0:
                        p['y'] = height
                    if p['y'] > height:
                        p['y'] = 0

                # Build display
                display_grid = [[' ' for _ in range(max_width)] for _ in range(height + 5)]
                
                # Draw text
                for i, line in enumerate(lines):
                    for j, char in enumerate(line):
                        if 0 <= i < len(display_grid) and 0 <= j < len(display_grid[i]):
                            display_grid[i][j] = char

                # Draw particles
                for p in particles:
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= py < len(display_grid) and 0 <= px < len(display_grid[py]):
                        if display_grid[py][px] == ' ':
                            display_grid[py][px] = p['char']

                # Render
                logo_lines = []
                for row in display_grid:
                    text_line = Text()
                    for char in row:
                        if char in particle_chars:
                            text_line.append(char, style="bright_white dim")
                        else:
                            text_line.append(char, style=base_color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def glitch_effect(
        self,
        text: str,
        base_color: str = "white",
        glitch_chars: str = "█▓▒░",
        intensity: float = 0.1,
        duration: float = 2.0,
    ) -> None:
        """Apply glitch effect to text.
        
        Args:
            text: Text to glitch
            base_color: Base color
            glitch_chars: Characters for glitch effect
            intensity: Glitch intensity (0.0-1.0)
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=base_color)
            return

        # Use normalized lines for proper alignment
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                logo_lines = []
                for line in lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            # Random glitch
                            if random.random() < intensity:
                                glitch_char = random.choice(glitch_chars)
                                text_line.append(glitch_char, style="bright_red")
                            else:
                                text_line.append(char, style=base_color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    # ============================================================================
    # Color Helper Functions
    # ============================================================================

    def _get_color_from_palette(
        self,
        color_input: str | list[str] | None,
        position: int = 0,
        total_positions: int = 1,
        default: str = "white",
    ) -> str:
        """Get a color from a palette or single color.
        
        Args:
            color_input: Single color string or list of colors (palette)
            position: Position index for palette selection
            total_positions: Total number of positions (for interpolation)
            default: Default color if input is None
            
        Returns:
            Color string
        """
        if color_input is None:
            return default
        
        if isinstance(color_input, str):
            return color_input
        
        if isinstance(color_input, list) and len(color_input) > 0:
            # Use position to select from palette
            if total_positions > 1:
                palette_index = int((position / total_positions) * len(color_input))
                palette_index = min(palette_index, len(color_input) - 1)
            else:
                palette_index = position % len(color_input)
            return color_input[palette_index]
        
        return default

    def _get_color_at_position(
        self,
        color_input: str | list[str] | None,
        char_idx: int,
        line_idx: int,
        max_width: int,
        max_height: int,
        default: str = "white",
    ) -> str:
        """Get color from palette based on character position.
        
        Args:
            color_input: Single color or palette
            char_idx: Character column index
            line_idx: Line row index
            max_width: Maximum width
            max_height: Maximum height
            default: Default color
            
        Returns:
            Color string
        """
        if color_input is None:
            return default
        
        if isinstance(color_input, str):
            return color_input
        
        if isinstance(color_input, list) and len(color_input) > 0:
            # Use position to cycle through palette
            position = (char_idx + line_idx) % len(color_input)
            return color_input[position]
        
        return default

    # ============================================================================
    # Color Transition Animations
    # ============================================================================

    async def rainbow_to_color(
        self,
        text: str,
        target_color: str | list[str],
        color_palette: list[str] | None = None,
        duration: float = 3.0,
    ) -> None:
        """Transition from rainbow colors to a single target color.
        
        Args:
            text: Text to animate
            target_color: Target color to transition to
            color_palette: Starting rainbow palette
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=target_color)
            return

        if color_palette is None:
            color_palette = [
                "red", "orange_red1", "dark_orange", "orange1", "yellow",
                "chartreuse1", "green", "spring_green1", "cyan",
                "deep_sky_blue1", "blue", "blue_violet", "purple", "magenta", "hot_pink",
            ]

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        num_colors = len(color_palette)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                progress = min(1.0, elapsed / duration)
                
                # Interpolate between rainbow and target color
                # Progress 0 = full rainbow, Progress 1 = full target color
                rainbow_weight = 1.0 - progress
                target_weight = progress

                logo_lines = []
                for line_idx, line in enumerate(lines):
                    text_line = Text()
                    for char_idx, char in enumerate(line):
                        if char == " ":
                            text_line.append(char)
                        else:
                            # Start with rainbow color
                            color_index = (char_idx + line_idx) % num_colors
                            rainbow_color = color_palette[color_index]
                            
                            # Get target color (handle palette)
                            if isinstance(target_color, list) and len(target_color) > 0:
                                target_idx = (char_idx + line_idx) % len(target_color)
                                final_target = target_color[target_idx]
                            else:
                                final_target = target_color if isinstance(target_color, str) else "white"
                            
                            # Blend between rainbow and target
                            if progress < 0.5:
                                # More rainbow
                                style = rainbow_color
                            elif progress < 0.75:
                                # Transitioning
                                style = f"{rainbow_color} dim" if random.random() < target_weight else final_target
                            else:
                                # Mostly target
                                style = final_target
                            
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def column_swipe(
        self,
        text: str,
        direction: str = "left_to_right",
        color_start: str | list[str] = "white",
        color_finish: str | list[str] = "cyan",
        duration: float = 3.0,
    ) -> None:
        """Swipe color across columns.
        
        Args:
            text: Text to animate
            direction: Swipe direction
            color_start: Starting color
            color_finish: Finishing color
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color_start)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        columns = self.get_columns(lines)
        num_columns = len(columns)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                progress = min(1.0, elapsed / duration)

                logo_lines = []
                height = len(columns[0]) if columns else 0
                
                for row_idx in range(height):
                    text_line = Text()
                    for col_idx, column in enumerate(columns):
                        if row_idx < len(column):
                            char = column[row_idx]
                        else:
                            char = " "
                        
                        if char == " ":
                            text_line.append(char)
                        else:
                            # Calculate swipe position
                            use_finish = False
                            if direction == "left_to_right":
                                col_progress = col_idx / num_columns
                                use_finish = progress >= col_progress
                            elif direction == "right_to_left":
                                col_progress = (num_columns - col_idx) / num_columns
                                use_finish = progress >= col_progress
                            elif direction == "center_out":
                                center = num_columns // 2
                                distance = abs(col_idx - center)
                                max_dist = num_columns // 2
                                col_progress = distance / max_dist if max_dist > 0 else 0
                                use_finish = progress >= col_progress
                            
                            # Get color from palette or single color
                            if use_finish:
                                style = self._get_color_at_position(
                                    color_finish, col_idx, row_idx, num_columns, height, "cyan"
                                )
                            else:
                                style = self._get_color_at_position(
                                    color_start, col_idx, row_idx, num_columns, height, "white"
                                )
                            
                            text_line.append(char, style=style)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def arc_reveal(
        self,
        text: str,
        direction: str = "top_down",
        color: str = "white",
        steps: int = 30,
        arc_center_x: int | None = None,
        arc_center_y: int | None = None,
    ) -> None:
        """Reveal text in an arc pattern.
        
        Args:
            text: Text to reveal
            direction: Arc direction ('top_down', 'down_up', 'left_right', 'right_left')
            color: Color style
            steps: Number of reveal steps
            arc_center_x: Arc center X (None = auto)
            arc_center_y: Arc center Y (None = auto)
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        height = len(lines)
        center_x = arc_center_x if arc_center_x is not None else max_width // 2
        center_y = arc_center_y if arc_center_y is not None else height // 2

        import math

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                progress = step / steps
                display_lines = []

                for line_idx, line in enumerate(lines):
                    display_line = ""
                    for char_idx, char in enumerate(line):
                        # Calculate angle from center
                        dist_x = char_idx - center_x
                        dist_y = line_idx - center_y
                        
                        # Calculate angle in degrees (0-360, where 0 is right, 90 is down)
                        if dist_x == 0 and dist_y == 0:
                            angle_deg = 0
                        else:
                            angle_rad = math.atan2(dist_y, dist_x)
                            angle_deg = math.degrees(angle_rad)
                            # Normalize to 0-360
                            angle_deg = (angle_deg + 360) % 360
                        
                        # Determine if revealed based on direction and progress
                        revealed = False
                        if direction == "top_down":
                            # Start at top (270°), sweep clockwise to bottom (90°)
                            # Progress 0 = 270°, Progress 1 = 90° (full 360° sweep)
                            start_angle = 270.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle + sweep_angle) % 360
                            
                            # Check if angle is in the swept range
                            if sweep_angle >= 360:
                                revealed = True
                            elif start_angle <= end_angle:
                                revealed = (angle_deg >= start_angle and angle_deg <= end_angle)
                            else:  # Wraps around 360/0
                                revealed = (angle_deg >= start_angle or angle_deg <= end_angle)
                                
                        elif direction == "down_up":
                            # Start at bottom (90°), sweep counter-clockwise to top (270°)
                            start_angle = 90.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle - sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                revealed = True
                            elif end_angle <= start_angle:
                                revealed = (angle_deg >= end_angle and angle_deg <= start_angle)
                            else:  # Wraps around
                                revealed = (angle_deg >= end_angle or angle_deg <= start_angle)
                                
                        elif direction == "left_right":
                            # Start at left (180°), sweep clockwise to right (0°/360°)
                            start_angle = 180.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle + sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                revealed = True
                            elif start_angle <= end_angle:
                                revealed = (angle_deg >= start_angle and angle_deg <= end_angle)
                            else:
                                revealed = (angle_deg >= start_angle or angle_deg <= end_angle)
                                
                        elif direction == "right_left":
                            # Start at right (0°/360°), sweep counter-clockwise to left (180°)
                            start_angle = 0.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle - sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                revealed = True
                            elif end_angle <= start_angle:
                                revealed = (angle_deg >= end_angle and angle_deg <= start_angle)
                            else:
                                revealed = (angle_deg >= end_angle or angle_deg <= start_angle)
                        else:
                            revealed = True
                        
                        if revealed:
                            display_line += char
                        else:
                            display_line += " "
                    display_lines.append(display_line)

                # Build Rich Text objects
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    async def arc_disappear(
        self,
        text: str,
        direction: str = "top_down",
        color: str = "white",
        steps: int = 30,
    ) -> None:
        """Disappear text in an arc pattern (reverse of arc_reveal)."""
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        max_width = max(len(line) for line in lines)
        height = len(lines)
        center_x = max_width // 2
        center_y = height // 2

        import math

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                progress = step / steps  # 0 = all visible, 1 = all hidden
                display_lines = []

                for line_idx, line in enumerate(lines):
                    display_line = ""
                    for char_idx, char in enumerate(line):
                        # Calculate angle from center
                        dist_x = char_idx - center_x
                        dist_y = line_idx - center_y
                        
                        if dist_x == 0 and dist_y == 0:
                            angle_deg = 0
                        else:
                            angle_rad = math.atan2(dist_y, dist_x)
                            angle_deg = math.degrees(angle_rad)
                            angle_deg = (angle_deg + 360) % 360
                        
                        # Determine if hidden based on direction and progress (reverse of reveal)
                        hidden = False
                        if direction == "top_down":
                            start_angle = 270.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle + sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                hidden = True
                            elif start_angle <= end_angle:
                                hidden = (angle_deg >= start_angle and angle_deg <= end_angle)
                            else:
                                hidden = (angle_deg >= start_angle or angle_deg <= end_angle)
                        elif direction == "down_up":
                            start_angle = 90.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle - sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                hidden = True
                            elif end_angle <= start_angle:
                                hidden = (angle_deg >= end_angle and angle_deg <= start_angle)
                            else:
                                hidden = (angle_deg >= end_angle or angle_deg <= start_angle)
                        elif direction == "left_right":
                            start_angle = 180.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle + sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                hidden = True
                            elif start_angle <= end_angle:
                                hidden = (angle_deg >= start_angle and angle_deg <= end_angle)
                            else:
                                hidden = (angle_deg >= start_angle or angle_deg <= end_angle)
                        elif direction == "right_left":
                            start_angle = 0.0
                            sweep_angle = 360.0 * progress
                            end_angle = (start_angle - sweep_angle) % 360
                            
                            if sweep_angle >= 360:
                                hidden = True
                            elif end_angle <= start_angle:
                                hidden = (angle_deg >= end_angle and angle_deg <= start_angle)
                            else:
                                hidden = (angle_deg >= end_angle or angle_deg <= start_angle)
                        
                        if hidden:
                            display_line += " "
                        else:
                            display_line += char
                    display_lines.append(display_line)

                # Build Rich Text objects
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    async def snake_reveal(
        self,
        text: str,
        direction: str = "left_to_right",
        color: str = "white",
        snake_length: int = 10,
        snake_thickness: int = 1,
        speed: float = 1.0,
        duration: float = 3.0,
    ) -> None:
        """Reveal text in a snake pattern.
        
        Args:
            text: Text to reveal
            direction: Snake direction
            snake_length: Length of snake (in positions)
            snake_thickness: Thickness of snake (perpendicular to direction)
            speed: Snake speed multiplier
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Create position order based on direction
        positions = []
        if direction == "left_to_right":
            for line_idx in range(len(lines)):
                for char_idx in range(len(lines[line_idx])):
                    positions.append((line_idx, char_idx))
        elif direction == "right_to_left":
            for line_idx in range(len(lines)):
                for char_idx in range(len(lines[line_idx]) - 1, -1, -1):
                    positions.append((line_idx, char_idx))
        elif direction == "top_to_bottom":
            max_width = max(len(line) for line in lines)
            for char_idx in range(max_width):
                for line_idx in range(len(lines)):
                    if char_idx < len(lines[line_idx]):
                        positions.append((line_idx, char_idx))
        elif direction == "bottom_to_top":
            max_width = max(len(line) for line in lines)
            for char_idx in range(max_width):
                for line_idx in range(len(lines) - 1, -1, -1):
                    if char_idx < len(lines[line_idx]):
                        positions.append((line_idx, char_idx))
        else:
            # Default: left to right
            for line_idx in range(len(lines)):
                for char_idx in range(len(lines[line_idx])):
                    positions.append((line_idx, char_idx))

        total_positions = len(positions)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                progress = min(1.0, elapsed / duration)
                
                # Calculate snake head position based on progress
                # Progress 0 = nothing revealed, Progress 1 = all revealed
                snake_head_pos = int(progress * total_positions)
                
                revealed = set()
                # Reveal all positions from start up to snake head
                # Also include snake_length positions after head for the "tail" effect
                for pos_idx in range(snake_head_pos + 1):  # +1 to include head position
                    if 0 <= pos_idx < total_positions:
                        line_idx, char_idx = positions[pos_idx]
                        # Add thickness perpendicular to direction
                        if snake_thickness > 1:
                            if direction in ["left_to_right", "right_to_left"]:
                                # Thickness in vertical direction
                                for t in range(-(snake_thickness // 2), (snake_thickness + 1) // 2):
                                    thick_line = line_idx + t
                                    if 0 <= thick_line < len(lines) and char_idx < len(lines[thick_line]):
                                        revealed.add((thick_line, char_idx))
                            else:
                                # Thickness in horizontal direction
                                for t in range(-(snake_thickness // 2), (snake_thickness + 1) // 2):
                                    thick_col = char_idx + t
                                    if 0 <= thick_col < len(lines[line_idx]):
                                        revealed.add((line_idx, thick_col))
                        else:
                            revealed.add((line_idx, char_idx))
                
                # Add tail effect - fade out the last snake_length positions
                # (optional: can be removed if not desired)
                tail_start = max(0, snake_head_pos - snake_length)
                for pos_idx in range(tail_start, snake_head_pos + 1):
                    if 0 <= pos_idx < total_positions:
                        line_idx, char_idx = positions[pos_idx]
                        revealed.add((line_idx, char_idx))

                # Build display
                logo_lines = []
                for line_idx, line in enumerate(lines):
                    text_line = Text()
                    for char_idx, char in enumerate(line):
                        if (line_idx, char_idx) in revealed:
                            if char == " ":
                                text_line.append(char)
                            else:
                                text_line.append(char, style=color)
                        else:
                            text_line.append(" ")
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)
            
            # Ensure final frame always shows complete logo (progress = 1.0)
            final_revealed = set()
            for pos_idx in range(total_positions):
                line_idx, char_idx = positions[pos_idx]
                final_revealed.add((line_idx, char_idx))
            
            logo_lines = []
            for line_idx, line in enumerate(lines):
                text_line = Text()
                for char_idx, char in enumerate(line):
                    if (line_idx, char_idx) in final_revealed:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    else:
                        text_line.append(" ")
                logo_lines.append(text_line)
            
            centered = Align.center(Group(*logo_lines))
            live.update(centered)
            await asyncio.sleep(frame_duration)

    async def snake_disappear(
        self,
        text: str,
        direction: str = "left_to_right",
        color: str = "white",
        snake_length: int = 10,
        snake_thickness: int = 1,
        speed: float = 1.0,
        duration: float = 3.0,
    ) -> None:
        """Disappear text in a snake pattern (reverse of snake_reveal)."""
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Create position order
        positions = []
        if direction == "left_to_right":
            for line_idx in range(len(lines)):
                for char_idx in range(len(lines[line_idx])):
                    positions.append((line_idx, char_idx))
        elif direction == "right_to_left":
            for line_idx in range(len(lines)):
                for char_idx in range(len(lines[line_idx]) - 1, -1, -1):
                    positions.append((line_idx, char_idx))
        elif direction == "top_to_bottom":
            max_width = max(len(line) for line in lines)
            for char_idx in range(max_width):
                for line_idx in range(len(lines)):
                    if char_idx < len(lines[line_idx]):
                        positions.append((line_idx, char_idx))
        elif direction == "bottom_to_top":
            max_width = max(len(line) for line in lines)
            for char_idx in range(max_width):
                for line_idx in range(len(lines) - 1, -1, -1):
                    if char_idx < len(lines[line_idx]):
                        positions.append((line_idx, char_idx))
        else:
            for line_idx in range(len(lines)):
                for char_idx in range(len(lines[line_idx])):
                    positions.append((line_idx, char_idx))

        total_positions = len(positions)
        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                progress = min(1.0, elapsed / duration)
                
                # Calculate snake head position (progress 1 = all hidden)
                # Progress 0 = nothing hidden, Progress 1 = all hidden
                snake_head_pos = int(progress * total_positions)
                
                hidden = set()
                # Hide all positions from start up to snake head
                for pos_idx in range(snake_head_pos + 1):  # +1 to include head position
                    if 0 <= pos_idx < total_positions:
                        line_idx, char_idx = positions[pos_idx]
                        # Add thickness perpendicular to direction
                        if snake_thickness > 1:
                            if direction in ["left_to_right", "right_to_left"]:
                                # Thickness in vertical direction
                                for t in range(-(snake_thickness // 2), (snake_thickness + 1) // 2):
                                    thick_line = line_idx + t
                                    if 0 <= thick_line < len(lines) and char_idx < len(lines[thick_line]):
                                        hidden.add((thick_line, char_idx))
                            else:
                                # Thickness in horizontal direction
                                for t in range(-(snake_thickness // 2), (snake_thickness + 1) // 2):
                                    thick_col = char_idx + t
                                    if 0 <= thick_col < len(lines[line_idx]):
                                        hidden.add((line_idx, thick_col))
                        else:
                            hidden.add((line_idx, char_idx))

                # Build display
                logo_lines = []
                for line_idx, line in enumerate(lines):
                    text_line = Text()
                    for char_idx, char in enumerate(line):
                        if (line_idx, char_idx) in hidden:
                            text_line.append(" ")
                        else:
                            if char == " ":
                                text_line.append(char)
                            else:
                                text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(frame_duration)

    async def letter_slide_in(
        self,
        text: str,
        direction: str = "left",
        color: str = "white",
        delay_per_letter: float = 0.1,
    ) -> None:
        """Slide in letters one by one.
        
        Args:
            text: Text to animate
            direction: Slide direction ('left', 'right', 'top', 'bottom')
            color: Color style
            delay_per_letter: Delay between letters
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Parse letters based on spacing
        from ccbt.interface.splash.character_modifier import CharacterModifier
        letter_data = CharacterModifier.parse_letters_by_width('\n'.join(lines))

        max_width = max(len(line) for line in lines)
        height = len(lines)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for letter_idx, letter in enumerate(letter_data):
                start_col = letter['start_col']
                width = letter['width']
                letter_columns = letter.get('columns', [])
                
                # Build display showing letters up to this one
                logo_lines = []
                for display_line_idx in range(height):
                    text_line = Text()
                    for display_col_idx in range(max_width):
                        # Check if this character should be shown
                        should_show = False
                        char_to_show = " "
                        
                        # Check if this is the current letter
                        if start_col <= display_col_idx < start_col + width:
                            if display_line_idx < len(letter_columns):
                                col_idx_in_letter = display_col_idx - start_col
                                if col_idx_in_letter < len(letter_columns[display_line_idx]):
                                    should_show = True
                                    char_to_show = letter_columns[display_line_idx][col_idx_in_letter]
                        
                        # Check if this is a previous letter
                        if not should_show:
                            for prev_letter in letter_data[:letter_idx]:
                                prev_col = prev_letter['start_col']
                                prev_width = prev_letter['width']
                                prev_columns = prev_letter.get('columns', [])
                                if prev_col <= display_col_idx < prev_col + prev_width:
                                    if display_line_idx < len(prev_columns):
                                        col_idx_in_prev = display_col_idx - prev_col
                                        if col_idx_in_prev < len(prev_columns[display_line_idx]):
                                            should_show = True
                                            char_to_show = prev_columns[display_line_idx][col_idx_in_prev]
                                            break
                        
                        if should_show:
                            if char_to_show == " ":
                                text_line.append(" ")
                            else:
                                text_line.append(char_to_show, style=color)
                        else:
                            text_line.append(" ")
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(delay_per_letter)

    async def letter_reveal_by_position(
        self,
        text: str,
        direction: str = "odd_up_even_down",
        color: str = "white",
        steps: int = 30,
    ) -> None:
        """Reveal letters based on column/row positions with specific letter widths.
        
        Args:
            text: Text to reveal
            direction: Reveal pattern ('odd_up_even_down', 'odd_down_even_up', 'left_to_right', etc.)
            color: Color style
            steps: Number of reveal steps
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        from ccbt.interface.splash.character_modifier import CharacterModifier
        
        # Parse letters based on spacing (entire letters, not individual characters)
        letter_data = CharacterModifier.parse_letters_by_width('\n'.join(lines))
        
        # Add index to each letter
        for idx, letter in enumerate(letter_data):
            letter['index'] = idx

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            for step in range(steps + 1):
                progress = step / steps
                revealed_letters = set()

                for letter in letter_data:
                    letter_idx = letter['index']
                    letter_columns = letter.get('columns', [])
                    max_height = len(lines)
                    
                    # Find the topmost line where this letter has content
                    top_line_idx = max_height
                    for line_idx, column_seg in enumerate(letter_columns):
                        if column_seg.strip():  # Has non-space content
                            top_line_idx = min(top_line_idx, line_idx)
                    
                    # If no content found, use reference line
                    if top_line_idx == max_height:
                        top_line_idx = letter.get('line_idx', 0)
                    
                    if direction == "odd_up_even_down":
                        # Odd letters (1-indexed, so index 1, 3, 5...) reveal upward
                        # Even letters (0-indexed, so index 0, 2, 4...) reveal downward
                        if letter_idx % 2 == 0:  # Even (0-indexed: 0, 2, 4...)
                            # Reveal downward from top
                            # Progress based on letter position in sequence
                            letter_progress = letter_idx / len(letter_data)
                            if progress >= letter_progress:
                                revealed_letters.add(letter_idx)
                        else:  # Odd (1-indexed: 1, 3, 5...)
                            # Reveal upward from bottom
                            # Reverse order: last odd letter reveals first
                            reverse_idx = len(letter_data) - 1 - letter_idx
                            letter_progress = reverse_idx / len(letter_data)
                            if progress >= letter_progress:
                                revealed_letters.add(letter_idx)
                    elif direction == "odd_down_even_up":
                        # Odd letters reveal downward, even upward
                        if letter_idx % 2 == 0:  # Even
                            # Reveal upward from bottom
                            reverse_idx = len(letter_data) - 1 - letter_idx
                            letter_progress = reverse_idx / len(letter_data)
                            if progress >= letter_progress:
                                revealed_letters.add(letter_idx)
                        else:  # Odd
                            # Reveal downward from top
                            letter_progress = letter_idx / len(letter_data)
                            if progress >= letter_progress:
                                revealed_letters.add(letter_idx)
                    elif direction == "top_to_bottom":
                        # Reveal letters from top to bottom based on their vertical position
                        # Letters higher up (lower line_idx) reveal first
                        line_progress = top_line_idx / max_height if max_height > 0 else 0
                        if progress >= line_progress:
                            revealed_letters.add(letter_idx)
                    elif direction == "bottom_to_top":
                        # Reveal letters from bottom to top
                        # Letters lower down (higher line_idx) reveal first
                        reverse_line_idx = max_height - 1 - top_line_idx
                        line_progress = reverse_line_idx / max_height if max_height > 0 else 0
                        if progress >= line_progress:
                            revealed_letters.add(letter_idx)
                    elif direction == "left_to_right":
                        reveal_progress = letter_idx / len(letter_data)
                        if progress >= reveal_progress:
                            revealed_letters.add(letter_idx)
                    elif direction == "right_to_left":
                        reveal_progress = (len(letter_data) - letter_idx) / len(letter_data)
                        if progress >= reveal_progress:
                            revealed_letters.add(letter_idx)

                # Build display - copy entire column groups for revealed letters
                max_width = max(len(line) for line in lines)
                display_lines = [[" "] * max_width for _ in range(len(lines))]
                
                for letter in letter_data:
                    if letter['index'] in revealed_letters:
                        start_col = letter['start_col']
                        width = letter['width']
                        letter_columns = letter.get('columns', [])
                        
                        # Copy entire column group (all lines) for this letter
                        for line_idx, column_seg in enumerate(letter_columns):
                            if line_idx < len(display_lines):
                                for i, char in enumerate(column_seg):
                                    col_idx = start_col + i
                                    if col_idx < max_width and i < width:
                                        display_lines[line_idx][col_idx] = char

                # Build Rich Text objects
                logo_lines = []
                for line in display_lines:
                    text_line = Text()
                    for char in line:
                        if char == " ":
                            text_line.append(char)
                        else:
                            text_line.append(char, style=color)
                    logo_lines.append(text_line)

                centered = Align.center(Group(*logo_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)

    def _get_background_color(
        self,
        bg_color_input: str | list[str] | None,
        position: tuple[int, int] | None = None,
        time_offset: float = 0.0,
        animation_speed: float = 1.0,
        default: str = "dim white",
    ) -> str:
        """Get background color from palette or single color with animation support.
        
        Args:
            bg_color_input: Single color string or list of colors (palette)
            position: Optional (x, y) position for palette selection
            time_offset: Time offset for animated palettes (cycles through colors)
            animation_speed: Speed multiplier for color animation
            default: Default color if input is None
            
        Returns:
            Color string
        """
        if bg_color_input is None:
            return default
        
        if isinstance(bg_color_input, str):
            return bg_color_input
        
        if isinstance(bg_color_input, list) and len(bg_color_input) > 0:
            # Calculate palette index based on position and/or time
            if position:
                x, y = position
                # Combine position and time for animated palette
                position_index = (x + y) % len(bg_color_input)
                time_index = int(time_offset * animation_speed) % len(bg_color_input)
                # Blend position and time-based selection
                palette_index = (position_index + time_index) % len(bg_color_input)
            else:
                # Time-based only
                palette_index = int(time_offset * animation_speed) % len(bg_color_input)
            return bg_color_input[palette_index]
        
        return default

    async def whitespace_background_animation(
        self,
        text: str,
        pattern: str = "|/—\\",
        bg_color: str | list[str] = "dim white",
        text_color: str = "white",
        duration: float = 3.0,
        animation_speed: float = 2.0,
    ) -> None:
        """Animate text with animated whitespace background pattern.
        
        Args:
            text: Text to display
            pattern: Pattern characters to cycle (e.g., "|/—\\")
            bg_color: Background pattern color
            text_color: Text color
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=text_color)
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        from ccbt.interface.splash.character_modifier import CharacterModifier

        # Get terminal size
        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                
                # Generate background
                bg_lines = CharacterModifier.create_whitespace_background(
                    width, height, pattern, elapsed
                )

                # Combine background with logo
                logo_height = len(lines)
                logo_start_y = (height - logo_height) // 2
                max_width = max(len(line) for line in lines)
                logo_start_x = (width - max_width) // 2

                combined_lines = []
                for y, bg_line in enumerate(bg_lines):
                    text_line = Text()
                    for x in range(width):
                        if logo_start_y <= y < logo_start_y + logo_height:
                            logo_y = y - logo_start_y
                            if logo_start_x <= x < logo_start_x + max_width:
                                logo_x = x - logo_start_x
                                if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                    char = lines[logo_y][logo_x]
                                    if char == " ":
                                        # Use background pattern with animated color
                                        bg_char = bg_line[x] if x < len(bg_line) else " "
                                        bg_color_style = self._get_background_color(
                                            bg_color, (x, y), elapsed, animation_speed, "dim white"
                                        )
                                        text_line.append(bg_char, style=bg_color_style)
                                    else:
                                        # Use logo character
                                        text_line.append(char, style=text_color)
                                else:
                                    bg_char = bg_line[x] if x < len(bg_line) else " "
                                    bg_color_style = self._get_background_color(
                                        bg_color, (x, y), elapsed, 2.0, "dim white"
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = bg_line[x] if x < len(bg_line) else " "
                                bg_color_style = self._get_background_color(
                                    bg_color, (x, y), elapsed, 2.0, "dim white"
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = bg_line[x] if x < len(bg_line) else " "
                            bg_color_style = self._get_background_color(
                                bg_color, (x, y), elapsed, 2.0, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    combined_lines.append(text_line)

                centered = Align.center(Group(*combined_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)  # Faster refresh (20 fps instead of 12 fps)

    # ============================================================================
    # Background Animation Helpers
    # ============================================================================

    async def animate_background_with_logo(
        self,
        text: str,
        bg_config: BackgroundConfig,
        logo_animation_style: str = "rainbow",
        logo_color_start: str | list[str] | None = None,
        logo_color_finish: str | list[str] | None = None,
        duration: float = 5.0,
    ) -> None:
        """Animate background with logo using specified animation style.
        
        Args:
            text: Logo text
            bg_config: Background configuration
            logo_animation_style: Animation style for logo (rainbow, fade, static)
            logo_color_start: Logo starting color or palette
            logo_color_finish: Logo finishing color or palette
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=logo_color_start or "white")
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Get terminal size
        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                
                # Generate animated background
                bg_color = bg_config.bg_color_start or bg_config.bg_color_palette
                bg_lines = self.background_renderer.generate_background(
                    width=width,
                    height=height,
                    bg_type=bg_config.bg_type,
                    bg_color=bg_color,
                    bg_pattern_char=bg_config.bg_pattern_char,
                    bg_pattern_density=bg_config.bg_pattern_density,
                    bg_star_count=bg_config.bg_star_count,
                    bg_wave_char=bg_config.bg_wave_char,
                    bg_wave_lines=bg_config.bg_wave_lines,
                    bg_flower_petals=bg_config.bg_flower_petals,
                    bg_flower_radius=bg_config.bg_flower_radius,
                    bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                    bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                    bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                    time_offset=elapsed * bg_config.bg_speed if bg_config.bg_animate else 0.0,
                )

                # Build logo with animation
                max_width = max(len(line) for line in lines)
                logo_height = len(lines)
                logo_start_y = (height - logo_height) // 2
                logo_start_x = (width - max_width) // 2

                # Apply logo animation style
                logo_color_map = {}  # Map (line_idx, char_idx) -> color
                
                if logo_animation_style == "rainbow":
                    # Rainbow animation on logo
                    from ccbt.interface.splash.animation_config import RAINBOW_PALETTE
                    color_palette = logo_color_start if isinstance(logo_color_start, list) else RAINBOW_PALETTE
                    if isinstance(logo_color_start, str):
                        color_palette = [logo_color_start]
                    
                    for line_idx, line in enumerate(lines):
                        for char_idx, char in enumerate(line):
                            if char != " ":
                                color_index = (char_idx + line_idx + int(elapsed * 8)) % len(color_palette)
                                logo_color_map[(line_idx, char_idx)] = color_palette[color_index]
                
                elif logo_animation_style == "fade":
                    # Fade animation
                    fade_color = logo_color_start if isinstance(logo_color_start, str) else (logo_color_start[0] if isinstance(logo_color_start, list) and logo_color_start else "white")
                    progress = (elapsed / duration) % 1.0
                    alpha = abs(1.0 - 2 * progress)  # Fade in and out
                    style = fade_color if alpha > 0.5 else f"{fade_color} dim"
                    
                    for line_idx, line in enumerate(lines):
                        for char_idx, char in enumerate(line):
                            if char != " ":
                                logo_color_map[(line_idx, char_idx)] = style
                
                else:
                    # Default: static color
                    logo_color = logo_color_start if isinstance(logo_color_start, str) else (logo_color_start[0] if isinstance(logo_color_start, list) and logo_color_start else "white")
                    for line_idx, line in enumerate(lines):
                        for char_idx, char in enumerate(line):
                            if char != " ":
                                logo_color_map[(line_idx, char_idx)] = logo_color

                # Combine background and logo
                combined_lines = []
                for y in range(height):
                    text_line = Text()
                    for x in range(width):
                        if logo_start_y <= y < logo_start_y + logo_height:
                            logo_y = y - logo_start_y
                            if logo_start_x <= x < logo_start_x + max_width:
                                logo_x = x - logo_start_x
                                if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                    char = lines[logo_y][logo_x]
                                    if char == " ":
                                        # Use background
                                        bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                        bg_color_style = self._get_background_color(
                                            bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                        )
                                        text_line.append(bg_char, style=bg_color_style)
                                    else:
                                        # Use logo character with animated color
                                        logo_color_style = logo_color_map.get((logo_y, logo_x), logo_color_start or "white")
                                        text_line.append(char, style=logo_color_style)
                                else:
                                    bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                    bg_color_style = self._get_background_color(
                                        bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                bg_color_style = self._get_background_color(
                                    bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                            bg_color_style = self._get_background_color(
                                bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    combined_lines.append(text_line)

                centered = Align.center(Group(*combined_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)  # Faster refresh (20 fps instead of 12 fps)

    async def animate_color_transition(
        self,
        text: str,
        bg_config: BackgroundConfig,
        logo_color_start: str | list[str],
        logo_color_finish: str | list[str],
        bg_color_start: str | list[str] | None = None,
        bg_color_finish: str | list[str] | None = None,
        duration: float = 6.0,
    ) -> None:
        """Animate color transition for both background and logo.
        
        Background transitions from bg_color_start to bg_color_finish.
        Logo transitions from logo_color_start to logo_color_finish.
        
        Args:
            text: Logo text
            bg_config: Background configuration
            logo_color_start: Logo starting color or palette
            logo_color_finish: Logo finishing color or palette
            bg_color_start: Background starting color or palette (uses bg_config if None)
            bg_color_finish: Background finishing color or palette (uses bg_config if None)
            duration: Animation duration
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=logo_color_start if isinstance(logo_color_start, str) else logo_color_start[0] if isinstance(logo_color_start, list) else "white")
            return

        # Use normalized lines
        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        # Get terminal size
        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        # Use bg_config colors if not specified
        bg_start = bg_color_start or bg_config.bg_color_start or bg_config.bg_color_palette or "dim white"
        bg_finish = bg_color_finish or bg_config.bg_color_finish or bg_config.bg_color_palette or "dim white"

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration

        # Use faster refresh rate for smoother transitions
        with Live(console=self.renderer.console, refresh_per_second=60, transient=False) as live:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                raw_progress = min(1.0, elapsed / duration)
                
                # Apply easing function for varied transitions
                # Use ease-in-out-cubic for smooth transitions
                if raw_progress < 0.5:
                    progress = 4 * raw_progress ** 3
                else:
                    progress = 1 - pow(-2 * raw_progress + 2, 3) / 2
                
                # Generate animated background with transition
                # Interpolate between bg_start and bg_finish
                current_bg_color = self._interpolate_color_palette(
                    bg_start, bg_finish, progress
                )
                
                # Generate background with transition
                # Ensure background is never "none" - default to solid with colors
                if bg_config.bg_type == "none":
                    bg_type = "solid"
                    # Ensure colors are set
                    if not bg_config.bg_color_start and not bg_config.bg_color_palette:
                        bg_color = ["black", "dim white"]
                    else:
                        bg_color = bg_config.bg_color_start or bg_config.bg_color_palette
                else:
                    bg_type = bg_config.bg_type
                    bg_color = bg_config.bg_color_start or bg_config.bg_color_palette
                
                # Final safety check: ensure bg_color is never None
                if not bg_color:
                    bg_color = ["black", "dim white"]
                bg_lines = self.background_renderer.generate_background(
                    width=width,
                    height=height,
                    bg_type=bg_type,
                    bg_color=current_bg_color,
                    bg_pattern_char=bg_config.bg_pattern_char,
                    bg_pattern_density=bg_config.bg_pattern_density,
                    bg_star_count=bg_config.bg_star_count,
                    bg_wave_char=bg_config.bg_wave_char,
                    bg_wave_lines=bg_config.bg_wave_lines,
                    bg_flower_petals=bg_config.bg_flower_petals,
                    bg_flower_radius=bg_config.bg_flower_radius,
                    bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                    bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                    bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                    time_offset=elapsed * bg_config.bg_speed if bg_config.bg_animate else 0.0,
                )

                # Interpolate logo colors - complete transition over full duration
                # Logo color transitions smoothly from start to finish
                current_logo_color = self._interpolate_color_palette(
                    logo_color_start, logo_color_finish, progress
                )

                # Build logo with interpolated colors and fade in/out
                max_width = max(len(line) for line in lines)
                logo_height = len(lines)
                logo_start_y = (height - logo_height) // 2
                logo_start_x = (width - max_width) // 2

                # Calculate logo fade with cycle: empty -> full -> empty -> full
                # Cycle pattern: 0-0.25 fade in, 0.25-0.5 full, 0.5-0.75 fade out, 0.75-1.0 fade in again
                cycle_progress = progress % 1.0
                if cycle_progress < 0.25:
                    # Fade in (0 -> 1)
                    logo_alpha = cycle_progress / 0.25
                elif cycle_progress < 0.5:
                    # Full visibility
                    logo_alpha = 1.0
                elif cycle_progress < 0.75:
                    # Fade out (1 -> 0)
                    logo_alpha = 1.0 - ((cycle_progress - 0.5) / 0.25)
                else:
                    # Fade in again (0 -> 1)
                    logo_alpha = (cycle_progress - 0.75) / 0.25

                # Build logo color map with faster animation
                logo_color_map = {}
                if isinstance(current_logo_color, list):
                    # Palette - use position-based selection with faster cycling
                    for line_idx, line in enumerate(lines):
                        for char_idx, char in enumerate(line):
                            if char != " ":
                                color_index = (char_idx + line_idx + int(elapsed * 20)) % len(current_logo_color)  # Increased to 20 for faster
                                base_color = current_logo_color[color_index]
                                # Apply fade effect with cycle
                                if logo_alpha < 0.1:
                                    # Completely invisible
                                    logo_color_map[(line_idx, char_idx)] = "black"
                                elif logo_alpha < 0.5:
                                    # Fading in/out
                                    logo_color_map[(line_idx, char_idx)] = f"dim {base_color}"
                                elif logo_alpha < 0.8:
                                    # Getting brighter
                                    logo_color_map[(line_idx, char_idx)] = base_color
                                else:
                                    # Full brightness
                                    logo_color_map[(line_idx, char_idx)] = f"bright {base_color}"
                else:
                    # Single color with fade
                    for line_idx, line in enumerate(lines):
                        for char_idx, char in enumerate(line):
                            if char != " ":
                                # Apply fade effect with cycle
                                if logo_alpha < 0.1:
                                    # Completely invisible
                                    logo_color_map[(line_idx, char_idx)] = "black"
                                elif logo_alpha < 0.5:
                                    # Fading in/out
                                    logo_color_map[(line_idx, char_idx)] = f"dim {current_logo_color}"
                                elif logo_alpha < 0.8:
                                    # Getting brighter
                                    logo_color_map[(line_idx, char_idx)] = current_logo_color
                                else:
                                    # Full brightness
                                    logo_color_map[(line_idx, char_idx)] = f"bright {current_logo_color}"

                # Combine background and logo
                combined_lines = []
                for y in range(height):
                    text_line = Text()
                    for x in range(width):
                        if logo_start_y <= y < logo_start_y + logo_height:
                            logo_y = y - logo_start_y
                            if logo_start_x <= x < logo_start_x + max_width:
                                logo_x = x - logo_start_x
                                if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                    char = lines[logo_y][logo_x]
                                    if char == " ":
                                        # Use background
                                        bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                        bg_color_style = self._get_background_color(
                                            current_bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                        )
                                        text_line.append(bg_char, style=bg_color_style)
                                    else:
                                        # Use logo character with interpolated color
                                        logo_color_style = logo_color_map.get((logo_y, logo_x), "white")
                                        text_line.append(char, style=logo_color_style)
                                else:
                                    bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                    bg_color_style = self._get_background_color(
                                        current_bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                bg_color_style = self._get_background_color(
                                    current_bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                            bg_color_style = self._get_background_color(
                                current_bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    combined_lines.append(text_line)

                centered = Align.center(Group(*combined_lines))
                # Always add overlay to ensure it persists across all frames
                live.update(centered)
                await asyncio.sleep(self.default_duration)  # Faster refresh (20 fps instead of 12 fps)

    def _interpolate_color_palette(
        self,
        color_start: str | list[str],
        color_finish: str | list[str],
        progress: float,
    ) -> str | list[str]:
        """Interpolate between two color palettes.
        
        Args:
            color_start: Starting color or palette
            color_finish: Finishing color or palette
            progress: Progress (0.0 = start, 1.0 = finish)
            
        Returns:
            Interpolated color or palette
        """
        # If both are strings, return finish when progress > 0.5
        if isinstance(color_start, str) and isinstance(color_finish, str):
            return color_finish if progress >= 0.5 else color_start
        
        # If one is string and one is list, convert string to single-item list
        start_palette = color_start if isinstance(color_start, list) else [color_start]
        finish_palette = color_finish if isinstance(color_finish, list) else [color_finish]
        
        # Interpolate palette lengths
        max_len = max(len(start_palette), len(finish_palette))
        result_palette = []
        
        for i in range(max_len):
            start_idx = i % len(start_palette)
            finish_idx = i % len(finish_palette)
            
            if progress < 0.5:
                # More start
                result_palette.append(start_palette[start_idx])
            else:
                # More finish
                result_palette.append(finish_palette[finish_idx])
        
        return result_palette

    @staticmethod
    def _progress_threshold(size: int, progress: float) -> int:
        """Return the number of units that should be revealed for progress."""
        if size <= 0:
            return 0
        clamped = max(0.0, min(1.0, progress))
        if clamped == 0.0:
            return 0
        if clamped == 1.0:
            return size
        return min(size, max(1, math.ceil(size * clamped)))

    def _should_reveal_position(
        self,
        direction: str,
        progress: float,
        logo_x: int,
        logo_y: int,
        logo_width: int,
        logo_height: int,
    ) -> bool:
        """Determine whether a position should be revealed for the given progress."""
        progress = max(0.0, min(1.0, progress))
        if logo_width <= 0 or logo_height <= 0:
            return False

        normalized_direction = (direction or "left_right").lower()
        if normalized_direction in {"top_down", "down_top", "top_to_bottom"}:
            threshold = self._progress_threshold(logo_height, progress)
            return logo_y < threshold
        if normalized_direction in {"down_up", "bottom_top", "bottom_to_top"}:
            threshold = self._progress_threshold(logo_height, progress)
            return logo_y >= logo_height - threshold
        if normalized_direction in {"left_right", "left_to_right"}:
            threshold = self._progress_threshold(logo_width, progress)
            return logo_x < threshold
        if normalized_direction in {"right_left", "right_to_left"}:
            threshold = self._progress_threshold(logo_width, progress)
            return logo_x >= logo_width - threshold
        if normalized_direction in {"radiant", "radiant_center_out", "center_out"}:
            # Expand radius slightly so the outer edge is always included
            center_x = (logo_width - 1) / 2
            center_y = (logo_height - 1) / 2
            dist = math.hypot(logo_x - center_x, logo_y - center_y)
            max_dist = math.hypot(max(logo_width - 1, 1) / 2, max(logo_height - 1, 1) / 2)
            radial_limit = max_dist * progress + 0.5
            return dist <= radial_limit
        if normalized_direction in {"radiant_center_in", "center_in"}:
            center_x = (logo_width - 1) / 2
            center_y = (logo_height - 1) / 2
            dist = math.hypot(logo_x - center_x, logo_y - center_y)
            max_dist = math.hypot(max(logo_width - 1, 1) / 2, max(logo_height - 1, 1) / 2)
            inverse_progress = 1.0 - progress
            radial_limit = max_dist * inverse_progress - 0.5
            return dist >= max(0.0, radial_limit)
        # Default / left-to-right fallback
        threshold = self._progress_threshold(logo_width, progress)
        return logo_x < threshold

    async def animate_background_with_reveal(
        self,
        text: str,
        bg_config: BackgroundConfig,
        logo_color: str | list[str] = "white",
        direction: str = "top_down",
        reveal_type: str = "reveal",  # "reveal" or "disappear"
        duration: float = 4.0,
        update_callback: Any | None = None,
    ) -> None:
        """Animate background with logo reveal/disappear effect.
        
        Args:
            text: Logo text
            bg_config: Background configuration
            logo_color: Logo color or palette
            direction: Reveal direction (top_down, down_up, left_right, right_left, radiant)
            reveal_type: "reveal" or "disappear"
            duration: Animation duration
            update_callback: Optional callback for Textual widgets
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=logo_color if isinstance(logo_color, str) else logo_color[0] if isinstance(logo_color, list) else "white")
            return

        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        max_width = max(len(line) for line in lines)
        logo_height = len(lines)
        logo_start_y = (height - logo_height) // 2
        logo_start_x = (width - max_width) // 2

        base_area = 80 * 24 or 1
        work_ratio = max(1.0, (width * height) / base_area)
        area_penalty = work_ratio ** 0.5
        adaptive_fps = max(20.0, min(60.0, 60.0 / area_penalty))
        steps = max(1, int(duration * adaptive_fps))
        frame_duration = self._calculate_frame_duration(duration, num_frames=steps)

        static_bg_lines: list[str] | None = None
        if not bg_config.bg_animate:
            bg_color_base = (
                bg_config.bg_color_palette
                or bg_config.bg_color_start
                or ["dim white"]
            )
            sample_color = self._get_background_color(
                bg_color_base,
                (0, 0),
                0.0,
                bg_config.bg_animation_speed,
                "dim white",
            )
            static_bg_lines = self.background_renderer.generate_background(
                width=width,
                height=height,
                bg_type=bg_config.bg_type,
                bg_color=sample_color,
                bg_pattern_char=bg_config.bg_pattern_char,
                bg_pattern_density=bg_config.bg_pattern_density,
                bg_star_count=bg_config.bg_star_count,
                bg_wave_char=bg_config.bg_wave_char,
                bg_wave_lines=bg_config.bg_wave_lines,
                bg_flower_petals=bg_config.bg_flower_petals,
                bg_flower_radius=bg_config.bg_flower_radius,
                bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                time_offset=0.0,
            )

        async def render_frame(elapsed: float, progress: float) -> None:
            elapsed = max(0.0, min(duration, elapsed))
            bg_color_input = bg_config.bg_color_palette
            if bg_config.bg_color_start and bg_config.bg_color_finish:
                bg_progress = (elapsed / duration) % 1.0 if duration > 0 else 0.0
                bg_color_input = self._interpolate_color_palette(
                    bg_config.bg_color_start, bg_config.bg_color_finish, bg_progress
                )
            elif not bg_color_input:
                bg_color_input = bg_config.bg_color_start or "dim white"

            bg_color = self._get_background_color(
                bg_color_input, (0, 0), elapsed, bg_config.bg_animation_speed, "dim white"
            )

            if bg_config.bg_animate:
                bg_lines = self.background_renderer.generate_background(
                    width=width,
                    height=height,
                    bg_type=bg_config.bg_type,
                    bg_color=bg_color,
                    bg_pattern_char=bg_config.bg_pattern_char,
                    bg_pattern_density=bg_config.bg_pattern_density,
                    bg_star_count=bg_config.bg_star_count,
                    bg_wave_char=bg_config.bg_wave_char,
                    bg_wave_lines=bg_config.bg_wave_lines,
                    bg_flower_petals=bg_config.bg_flower_petals,
                    bg_flower_radius=bg_config.bg_flower_radius,
                    bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                    bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                    bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                    time_offset=elapsed * bg_config.bg_speed,
                )
            else:
                bg_lines = static_bg_lines or [" " * width for _ in range(height)]

            combined_lines = []
            for y in range(height):
                text_line = Text()
                for x in range(width):
                    if logo_start_y <= y < logo_start_y + logo_height:
                        logo_y = y - logo_start_y
                        if logo_start_x <= x < logo_start_x + max_width:
                            logo_x = x - logo_start_x
                            if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                char = lines[logo_y][logo_x]
                                should_reveal = self._should_reveal_position(
                                    direction,
                                    progress,
                                    logo_x,
                                    logo_y,
                                    max_width,
                                    logo_height,
                                )

                                if should_reveal and char != " ":
                                    if isinstance(logo_color, list):
                                        color_index = (
                                            logo_x + logo_y + int(elapsed * 25)
                                        ) % len(logo_color)
                                        logo_color_style = logo_color[color_index]
                                    else:
                                        logo_color_style = logo_color
                                    text_line.append(char, style=logo_color_style)
                                elif char == " ":
                                    bg_char = (
                                        bg_lines[y][x]
                                        if y < len(bg_lines) and x < len(bg_lines[y])
                                        else " "
                                    )
                                    bg_color_style = self._get_background_color(
                                        bg_color,
                                        (x, y),
                                        elapsed,
                                        bg_config.bg_animation_speed,
                                        "dim white",
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                                else:
                                    bg_char = (
                                        bg_lines[y][x]
                                        if y < len(bg_lines) and x < len(bg_lines[y])
                                        else " "
                                    )
                                    bg_color_style = self._get_background_color(
                                        bg_color,
                                        (x, y),
                                        elapsed,
                                        bg_config.bg_animation_speed,
                                        "dim white",
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = (
                                    bg_lines[y][x]
                                    if y < len(bg_lines) and x < len(bg_lines[y])
                                    else " "
                                )
                                bg_color_style = self._get_background_color(
                                    bg_color,
                                    (x, y),
                                    elapsed,
                                    bg_config.bg_animation_speed,
                                    "dim white",
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = (
                                bg_lines[y][x]
                                if y < len(bg_lines) and x < len(bg_lines[y])
                                else " "
                            )
                            bg_color_style = self._get_background_color(
                                bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    else:
                        bg_char = (
                            bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                        )
                        bg_color_style = self._get_background_color(
                            bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                        )
                        text_line.append(bg_char, style=bg_color_style)
                combined_lines.append(text_line)

            centered = Align.center(Group(*combined_lines))
            if update_callback:
                update_callback(centered)
            elif live:
                live.update(centered)

        start_time = asyncio.get_event_loop().time()

        if update_callback:
            live = None
        else:
            live = Live(console=self.renderer.console, refresh_per_second=60, transient=False)
            live.__enter__()
        
        last_progress = None
        try:
            for step in range(steps + 1):
                elapsed = asyncio.get_event_loop().time() - start_time
                elapsed = max(0.0, min(duration, elapsed))
                progress = elapsed / duration if duration > 0 else 1.0
                if reveal_type == "disappear":
                    progress = 1.0 - progress

                await render_frame(elapsed, progress)
                last_progress = progress
                await asyncio.sleep(frame_duration)

            final_progress = 0.0 if reveal_type == "disappear" else 1.0
            if last_progress is None or abs(final_progress - last_progress) > 1e-6:
                await render_frame(duration, final_progress)
        finally:
            if live:
                live.__exit__(None, None, None)

    async def animate_background_with_fade(
        self,
        text: str,
        bg_config: BackgroundConfig,
        logo_color: str | list[str] = "white",
        fade_type: str = "fade_in",  # "fade_in" or "fade_out"
        duration: float = 3.0,
        update_callback: Any | None = None,
    ) -> None:
        """Animate background with logo fade in/out effect.
        
        Args:
            text: Logo text
            bg_config: Background configuration
            logo_color: Logo color or palette
            fade_type: "fade_in" or "fade_out"
            duration: Animation duration
            update_callback: Optional callback for Textual widgets
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=logo_color if isinstance(logo_color, str) else logo_color[0] if isinstance(logo_color, list) else "white")
            return

        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        if update_callback:
            live = None
        else:
            live = Live(console=self.renderer.console, refresh_per_second=60, transient=False)
            live.__enter__()
        
        try:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                raw_progress = min(1.0, elapsed / duration)
                
                # Calculate logo fade with cycle: empty -> full -> empty -> full
                # Cycle pattern: 0-0.25 fade in, 0.25-0.5 full, 0.5-0.75 fade out, 0.75-1.0 fade in again
                cycle_progress = raw_progress % 1.0
                if cycle_progress < 0.25:
                    # Fade in (0 -> 1)
                    logo_alpha = cycle_progress / 0.25
                elif cycle_progress < 0.5:
                    # Full visibility
                    logo_alpha = 1.0
                elif cycle_progress < 0.75:
                    # Fade out (1 -> 0)
                    logo_alpha = 1.0 - ((cycle_progress - 0.5) / 0.25)
                else:
                    # Fade in again (0 -> 1)
                    logo_alpha = (cycle_progress - 0.75) / 0.25
                
                progress = raw_progress

                # Generate animated background with color transitions
                bg_color_input = bg_config.bg_color_palette
                if bg_config.bg_color_start and bg_config.bg_color_finish:
                    # Interpolate between start and finish for background
                    bg_progress = (elapsed / duration) % 1.0 if duration > 0 else 0.0
                    bg_color_input = self._interpolate_color_palette(
                        bg_config.bg_color_start, bg_config.bg_color_finish, bg_progress
                    )
                elif not bg_color_input:
                    bg_color_input = bg_config.bg_color_start or "dim white"
                
                bg_color = self._get_background_color(
                    bg_color_input, (0, 0), elapsed, bg_config.bg_animation_speed, "dim white"
                )
                
                bg_lines = self.background_renderer.generate_background(
                    width=width,
                    height=height,
                    bg_type=bg_config.bg_type,
                    bg_color=bg_color,
                    bg_pattern_char=bg_config.bg_pattern_char,
                    bg_pattern_density=bg_config.bg_pattern_density,
                    bg_star_count=bg_config.bg_star_count,
                    bg_wave_char=bg_config.bg_wave_char,
                    bg_wave_lines=bg_config.bg_wave_lines,
                    bg_flower_petals=bg_config.bg_flower_petals,
                    bg_flower_radius=bg_config.bg_flower_radius,
                    bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                    bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                    bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                    time_offset=elapsed * bg_config.bg_speed if bg_config.bg_animate else 0.0,
                )

                # Build logo with fade effect - faster animation
                max_width = max(len(line) for line in lines)
                logo_height = len(lines)
                logo_start_y = (height - logo_height) // 2
                logo_start_x = (width - max_width) // 2

                combined_lines = []
                for y in range(height):
                    text_line = Text()
                    for x in range(width):
                        if logo_start_y <= y < logo_start_y + logo_height:
                            logo_y = y - logo_start_y
                            if logo_start_x <= x < logo_start_x + max_width:
                                logo_x = x - logo_start_x
                                if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                    char = lines[logo_y][logo_x]
                                    if char != " ":
                                        # Apply fade effect with cycle - handle palette or single color
                                        if isinstance(logo_color, list):
                                            color_index = (logo_x + logo_y + int(elapsed * 25)) % len(logo_color)
                                            base_color = logo_color[color_index]
                                        else:
                                            base_color = logo_color
                                        
                                        # Apply alpha-based fade with cycle
                                        if logo_alpha < 0.1:
                                            logo_color_style = "black"
                                        elif logo_alpha < 0.5:
                                            logo_color_style = f"dim {base_color}"
                                        elif logo_alpha < 0.8:
                                            logo_color_style = base_color
                                        else:
                                            logo_color_style = f"bright {base_color}"
                                        text_line.append(char, style=logo_color_style)
                                    else:
                                        # Use background
                                        bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                        bg_color_style = self._get_background_color(
                                            bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                        )
                                        text_line.append(bg_char, style=bg_color_style)
                                else:
                                    bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                    bg_color_style = self._get_background_color(
                                        bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                bg_color_style = self._get_background_color(
                                    bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                            bg_color_style = self._get_background_color(
                                bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    combined_lines.append(text_line)

                centered = Align.center(Group(*combined_lines))
                if update_callback:
                    update_callback(centered)
                elif live:
                    # Always add overlay to ensure it persists across all frames
                    live.update(centered)
                
                await asyncio.sleep(frame_duration)
        finally:
            if live:
                live.__exit__(None, None, None)

    async def animate_background_with_glitch(
        self,
        text: str,
        bg_config: BackgroundConfig,
        logo_color: str | list[str] = "white",
        glitch_intensity: float = 0.15,
        duration: float = 3.0,
        update_callback: Any | None = None,
    ) -> None:
        """Animate background with logo glitch effect.
        
        Args:
            text: Logo text
            bg_config: Background configuration
            logo_color: Logo color or palette
            glitch_intensity: Glitch intensity (0.0-1.0)
            duration: Animation duration
            update_callback: Optional callback for Textual widgets
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=logo_color if isinstance(logo_color, str) else logo_color[0] if isinstance(logo_color, list) else "white")
            return

        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        glitch_chars = "█▓▒░"

        if update_callback:
            live = None
        else:
            live = Live(console=self.renderer.console, refresh_per_second=20, transient=False)
            live.__enter__()
        
        try:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time

                # Generate animated background with color transitions
                bg_color_input = bg_config.bg_color_palette
                if bg_config.bg_color_start and bg_config.bg_color_finish:
                    # Interpolate between start and finish for background transition
                    bg_progress = (elapsed / duration) % 1.0 if duration > 0 else 0.0
                    bg_color_input = self._interpolate_color_palette(
                        bg_config.bg_color_start, bg_config.bg_color_finish, bg_progress
                    )
                elif not bg_color_input:
                    bg_color_input = bg_config.bg_color_start or "dim white"
                
                bg_color = self._get_background_color(
                    bg_color_input, (0, 0), elapsed, bg_config.bg_animation_speed, "dim white"
                )
                
                bg_lines = self.background_renderer.generate_background(
                    width=width,
                    height=height,
                    bg_type=bg_config.bg_type,
                    bg_color=bg_color,
                    bg_pattern_char=bg_config.bg_pattern_char,
                    bg_pattern_density=bg_config.bg_pattern_density,
                    bg_star_count=bg_config.bg_star_count,
                    bg_wave_char=bg_config.bg_wave_char,
                    bg_wave_lines=bg_config.bg_wave_lines,
                    bg_flower_petals=bg_config.bg_flower_petals,
                    bg_flower_radius=bg_config.bg_flower_radius,
                    bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                    bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                    bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                    time_offset=elapsed * bg_config.bg_speed if bg_config.bg_animate else 0.0,
                )

                # Build logo with glitch effect
                max_width = max(len(line) for line in lines)
                logo_height = len(lines)
                logo_start_y = (height - logo_height) // 2
                logo_start_x = (width - max_width) // 2

                combined_lines = []
                for y in range(height):
                    text_line = Text()
                    for x in range(width):
                        if logo_start_y <= y < logo_start_y + logo_height:
                            logo_y = y - logo_start_y
                            if logo_start_x <= x < logo_start_x + max_width:
                                logo_x = x - logo_start_x
                                if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                    char = lines[logo_y][logo_x]
                                    if char != " ":
                                        # Apply glitch effect - handle palette or single color - faster animation
                                        if random.random() < glitch_intensity:
                                            glitch_char = random.choice(glitch_chars)
                                            text_line.append(glitch_char, style="bright_red")
                                        else:
                                            if isinstance(logo_color, list):
                                                color_index = (logo_x + logo_y + int(elapsed * 25)) % len(logo_color)  # Increased to 25 for very fast
                                                logo_color_style = logo_color[color_index]
                                            else:
                                                logo_color_style = logo_color
                                            text_line.append(char, style=logo_color_style)
                                    else:
                                        # Use background
                                        bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                        bg_color_style = self._get_background_color(
                                            bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                        )
                                        text_line.append(bg_char, style=bg_color_style)
                                else:
                                    bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                    bg_color_style = self._get_background_color(
                                        bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                bg_color_style = self._get_background_color(
                                    bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                            bg_color_style = self._get_background_color(
                                bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    combined_lines.append(text_line)

                centered = Align.center(Group(*combined_lines))
                if update_callback:
                    update_callback(centered)
                elif live:
                    # Always add overlay to ensure it persists across all frames
                    live.update(centered)
                
                await asyncio.sleep(self.default_duration)
        finally:
            if live:
                live.__exit__(None, None, None)

    async def animate_background_with_rainbow(
        self,
        text: str,
        bg_config: BackgroundConfig,
        logo_color_palette: list[str],
        bg_color_palette: list[str] | None = None,
        direction: str = "left_to_right",
        duration: float = 4.0,
        update_callback: Any | None = None,
    ) -> None:
        """Animate background with rainbow logo effect.
        
        Args:
            text: Logo text
            bg_config: Background configuration
            logo_color_palette: Logo color palette
            bg_color_palette: Background color palette (uses bg_config if None)
            direction: Rainbow direction
            duration: Animation duration
            update_callback: Optional callback for Textual widgets
        """
        try:
            from rich.align import Align
            from rich.console import Group
            from rich.live import Live
            from rich.text import Text
        except ImportError:
            self.renderer.render_frame(text, color=logo_color_palette[0] if logo_color_palette else "white")
            return

        lines = self.normalize_logo_lines(text)
        if not lines:
            return

        try:
            if self.renderer.console:
                width = self.renderer.console.width or 80
                height = self.renderer.console.height or 24
            else:
                width, height = 80, 24
        except Exception:
            width, height = 80, 24

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + duration
        frame_duration = self._calculate_frame_duration(duration)

        if update_callback:
            live = None
        else:
            live = Live(console=self.renderer.console, refresh_per_second=60, transient=False)
            live.__enter__()
        
        try:
            while asyncio.get_event_loop().time() < end_time:
                elapsed = asyncio.get_event_loop().time() - start_time
                time_offset = int(elapsed * 12)  # Increased from 8 to 12 for faster animation

                # Generate animated background with rainbow and color transitions
                bg_palette = bg_color_palette or bg_config.bg_color_palette
                if bg_config.bg_color_start and bg_config.bg_color_finish:
                    # Interpolate between start and finish for background transition
                    bg_progress = (elapsed / duration) % 1.0 if duration > 0 else 0.0
                    bg_palette = self._interpolate_color_palette(
                        bg_config.bg_color_start, bg_config.bg_color_finish, bg_progress
                    )
                elif not bg_palette:
                    bg_palette = bg_config.bg_color_start or ["dim white"]
                
                bg_color = self._get_background_color(
                    bg_palette, (0, 0), elapsed, bg_config.bg_animation_speed, "dim white"
                )
                
                bg_lines = self.background_renderer.generate_background(
                    width=width,
                    height=height,
                    bg_type=bg_config.bg_type,
                    bg_color=bg_color,
                    bg_pattern_char=bg_config.bg_pattern_char,
                    bg_pattern_density=bg_config.bg_pattern_density,
                    bg_star_count=bg_config.bg_star_count,
                    bg_wave_char=bg_config.bg_wave_char,
                    bg_wave_lines=bg_config.bg_wave_lines,
                    bg_flower_petals=bg_config.bg_flower_petals,
                    bg_flower_radius=bg_config.bg_flower_radius,
                    bg_flower_count=getattr(bg_config, 'bg_flower_count', 1),
                    bg_flower_rotation_speed=getattr(bg_config, 'bg_flower_rotation_speed', 1.0),
                    bg_flower_movement_speed=getattr(bg_config, 'bg_flower_movement_speed', 0.5),
                bg_direction=getattr(bg_config, 'bg_direction', "left_to_right"),
                    time_offset=elapsed * bg_config.bg_speed if bg_config.bg_animate else 0.0,
                )

                # Build logo with rainbow effect
                max_width = max(len(line) for line in lines)
                logo_height = len(lines)
                logo_start_y = (height - logo_height) // 2
                logo_start_x = (width - max_width) // 2

                combined_lines = []
                for y in range(height):
                    text_line = Text()
                    for x in range(width):
                        if logo_start_y <= y < logo_start_y + logo_height:
                            logo_y = y - logo_start_y
                            if logo_start_x <= x < logo_start_x + max_width:
                                logo_x = x - logo_start_x
                                if logo_y < len(lines) and logo_x < len(lines[logo_y]):
                                    char = lines[logo_y][logo_x]
                                    if char != " ":
                                        # Apply rainbow effect based on direction
                                        if direction == "left_to_right":
                                            color_index = (logo_x - time_offset) % len(logo_color_palette)
                                        elif direction == "right_to_left":
                                            color_index = (logo_x + time_offset) % len(logo_color_palette)
                                        elif direction == "top_to_bottom":
                                            color_index = (logo_y - time_offset) % len(logo_color_palette)
                                        elif direction == "bottom_to_top":
                                            color_index = (logo_y + time_offset) % len(logo_color_palette)
                                        elif direction == "radiant_center_out":
                                            center_x = max_width // 2
                                            center_y = logo_height // 2
                                            dist = int(((logo_x - center_x) ** 2 + (logo_y - center_y) ** 2) ** 0.5)
                                            color_index = (dist + time_offset) % len(logo_color_palette)
                                        elif direction == "radiant_center_in":
                                            center_x = max_width // 2
                                            center_y = logo_height // 2
                                            dist = int(((logo_x - center_x) ** 2 + (logo_y - center_y) ** 2) ** 0.5)
                                            max_dist = int(((max_width / 2) ** 2 + (logo_height / 2) ** 2) ** 0.5)
                                            color_index = ((max_dist - dist) + time_offset) % len(logo_color_palette)
                                        else:
                                            color_index = (logo_x + logo_y + time_offset) % len(logo_color_palette)
                                        
                                        text_line.append(char, style=logo_color_palette[color_index])
                                    else:
                                        # Use background
                                        bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                        bg_color_style = self._get_background_color(
                                            bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                        )
                                        text_line.append(bg_char, style=bg_color_style)
                                else:
                                    bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                    bg_color_style = self._get_background_color(
                                        bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                    )
                                    text_line.append(bg_char, style=bg_color_style)
                            else:
                                bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                                bg_color_style = self._get_background_color(
                                    bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                                )
                                text_line.append(bg_char, style=bg_color_style)
                        else:
                            bg_char = bg_lines[y][x] if y < len(bg_lines) and x < len(bg_lines[y]) else " "
                            bg_color_style = self._get_background_color(
                                bg_color, (x, y), elapsed, bg_config.bg_animation_speed, "dim white"
                            )
                            text_line.append(bg_char, style=bg_color_style)
                    combined_lines.append(text_line)

                centered = Align.center(Group(*combined_lines))
                if update_callback:
                    update_callback(centered)
                elif live:
                    # Always add overlay to ensure it persists across all frames
                    live.update(centered)
                
                await asyncio.sleep(frame_duration)
        finally:
            if live:
                live.__exit__(None, None, None)

