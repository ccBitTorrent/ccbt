## Splash Screen

Created a splash screen system with:

### 1. **SplashScreen Class** (`splash_screen.py`)
   - Works with Rich Console (CLI) and Textual widgets (interface)
   - 90+ second animation sequence
   - 15 background patterns cycling through:
     - Solid backgrounds
     - Stars (various densities: 100, 120, 150, 200)
     - Waves (various characters: `~`, `─`, `═`)
     - Patterns (various characters: `·`, `░`, `▒`)
     - Particles (various densities: 0.1, 0.15, 0.2, 0.25, 0.3)

### 2. **Color Transitions**
   - Background transitions: Rainbow ↔ Ocean ↔ Sunset
   - Logo transitions: Opposite direction (Ocean ↔ Rainbow ↔ Sunset)
   - Fast speeds: 2.0-4.5 for background movement, 0.5-1.0 for color cycling

### 3. **Compatibility**
   - Rich Console: Uses `Live` context manager
   - Textual: Uses callback mechanism for widget updates
   - Both modes supported via the same `SplashScreen` class

### 4. **Animation Sequence**
   - 15 segments × 6 seconds = 90 seconds total
   - Each segment uses different:
     - Background type and configuration
     - Color palette transitions
     - Animation speeds
     - Pattern densities/characters

### 5. **Demo Script** (`splash_demo.py`)
   - Standalone demo to test the splash screen
   - Shows Rich Console integration

### Usage Examples:

**Rich Console (CLI):**
```python
from rich.console import Console
from rich.live import Live
from ccbt.interface.splash import SplashScreen

console = Console()
splash = SplashScreen(console=console, duration=90.0)

with Live(splash, console=console, refresh_per_second=12):
    await splash.run()
```

**Textual Widget:**
```python
from textual.widgets import Static
from ccbt.interface.splash import SplashScreen

splash_widget = Static()
splash = SplashScreen(textual_widget=splash_widget, duration=90.0)
await splash.run()
```

The splash screen is ready to use in CLI and interface loading screens. Run the demo with:
```bash
python -m ccbt.interface.splash.splash_demo
```